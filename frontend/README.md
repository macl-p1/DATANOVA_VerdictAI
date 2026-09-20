# VerdictAI frontend

Static pages (no build step, no framework) that read the SAM backend in
[`../backend`](../backend). Every eligibility decision is made by the rules
Lambda; this app renders the result and never re-derives it.

## Point it at a backend

[`js/config.js`](js/config.js) already carries the deployed stack's `ApiUrl`,
`UserPoolId` and `UserPoolClientId`. None of the three is a secret: the client
has no secret because a browser cannot keep one, and the API is protected by the
Cognito authorizer rather than by its URL being hard to guess.

To point the app at a different stack, take those values from `sam deploy` and
either edit the fallbacks in `config.js`, or override them per-machine:

```js
localStorage.setItem("verdictai-api-base", "https://xxxx.execute-api.us-east-1.amazonaws.com/prod")
localStorage.setItem("verdictai-user-pool-id", "us-east-1_xxxxxxxxx")
localStorage.setItem("verdictai-client-id", "xxxxxxxxxxxxxxxxxxxxxxxxxx")
```

## Signing in

Every `/cases` endpoint sits behind a Cognito authorizer. An unauthenticated
request is rejected by API Gateway with 401 before any Lambda runs, so the case
register cannot be read or written without an account.

There is **no public sign-up** — this is a register of people in detention, not
a consumer app. An administrator creates each account:

```bash
POOL=us-east-1_agAuQxfKR   # UserPoolId from the stack outputs

aws cognito-idp admin-create-user \
  --user-pool-id $POOL \
  --username person@example.org \
  --user-attributes Name=email,Value=person@example.org Name=email_verified,Value=true \
  --temporary-password 'SomethingTemporary-2026!' \
  --message-action SUPPRESS      # drop this to have Cognito email the invite
```

The account starts in `FORCE_CHANGE_PASSWORD`: on first sign-in the login screen
asks for a new password before issuing any token. Passwords must be at least 12
characters with upper and lower case, a number and a symbol.

`js/auth.js` talks to Cognito's `InitiateAuth` JSON endpoint with plain `fetch`,
so no AWS SDK is bundled. Tokens are held in `sessionStorage` — per tab, cleared
when the tab closes. The ID token lasts 60 minutes and is refreshed
automatically; the refresh token lasts a day. A 401 from the API signs the user
out rather than leaving stale data on screen.

## Run locally

Serve over HTTP rather than opening the files directly — a `file://` page has a
null origin, which S3 rejects on the presigned upload.

```bash
cd frontend
python -m http.server 8000
# then open http://localhost:8000/
```

## Layout

```
index.html        redirect to pages/login.html
pages/            login, dashboard, upload, case-detail
css/              common.css holds the design tokens and flag colours
js/config.js      where the API base URL comes from
js/api.js         the only module that calls the backend
js/common.js      formatting, theme, session, flag -> colour mapping
```

## Where each screen gets its data

| Screen | Backend call |
|---|---|
| `pages/upload.html` | `POST /cases/upload-url`, then `PUT` to the presigned S3 URL, then polls `GET /cases/{caseId}` until the record is `PROCESSED` or `FAILED` |
| `pages/dashboard.html` | `GET /cases`, or `GET /cases?flag=…` when a flag chip is active so the `flag-daysOverdue` index does the filtering |
| `pages/case-detail.html` | `GET /cases/{caseId}`, and `POST /cases/{caseId}/bail-draft` when the draft button is pressed |

Free-text search filters in the browser, on top of whatever the flag chip
fetched.

## Flag mapping

The backend flag is authoritative. `js/common.js` maps it to a colour and label,
mirroring `FLAG_TO_STATUS` in [`../backend/shared/schemas.py`](../backend/shared/schemas.py).

| Backend flag | UI status | Label |
|---|---|---|
| `PAST_MAX` | `red` | Past full term |
| `PAST_HALF` | `amber` | Past half term |
| `PAST_THIRD` | `yellow` | First-time, past third |
| `NOT_ELIGIBLE` | `barred` | Barred by law |
| `NOT_YET` | `gray` | Not yet eligible |
| `NEEDS_REVIEW` | `review` | Needs review |

`status` is checked before `flag`: while a case is still `UPLOADED` it renders
as `pending` ("Processing"), because its stored flag is only a placeholder that
keeps the record present in the flag index.

`daysOverdue` carries its meaning in the sign — positive is days past the
threshold, negative is days still to serve.

## Flags are re-checked daily

Eligibility under s.479 arrives with time served, so a flag computed once at
upload goes stale. The `reevaluate` Lambda runs every night at 01:30 UTC over
cases flagged `NOT_YET`, `PAST_THIRD` or `PAST_HALF` and re-runs the rule engine
against today's date, escalating them as thresholds are crossed. `PAST_MAX`,
`NOT_ELIGIBLE` and `NEEDS_REVIEW` are left alone — the first is the end of the
scale, the second turns on a bar time does not lift, and the third needs a
human. It re-uses the stored facts, so no document is re-read; the plain-English
explanation is regenerated only when the flag actually changes. The case detail
page shows `Last re-checked against today`.

## When the engine refuses to decide

The rule engine returns `NEEDS_REVIEW` rather than a flag when it cannot stand
behind the answer:

- **Low confidence.** Any fact the decision rests on scoring below
  `ConfidenceThreshold` (default 0.90). The extraction model is badly
  calibrated — it scored an arrest date 0.7–0.8 on a document that said in terms
  the date was unconfirmed — so the threshold is deliberately high and is a
  deploy parameter.
- **No evidence recorded** for a fact the decision rests on.
- **Impossible dates**: an arrest date in the future, a release date before the
  arrest, or a span implying over 100 years in custody (a misread year).

## Upload formats

How a document is read is decided by its **bytes**, not its extension:

| What you upload | Route | Needs Textract |
|---|---|---|
| `.txt`, `.text`, `.md` | decoded directly | no |
| anything that decodes as UTF-8 text, whatever it is named | decoded directly | no |
| a real PDF | Amazon Textract | yes |

The text route has no dependency on Textract at all, so it keeps working when
Textract is disabled, throttled, or the account has not been approved for it.
A text file uploaded with a `.pdf` name still goes through fine.

**PDFs need Textract enabled on the AWS account.** It is a per-account opt-in
service; until it is approved every call fails with
`SubscriptionRequiredException`. Nothing needs changing in this repo when it is
switched on — the code path is already deployed and will simply start
succeeding. Until then a PDF upload is marked `FAILED` within seconds and the
register explains why:

> This looks like a scanned PDF, which needs Amazon Textract to read, and
> Textract is not available to this AWS account yet. Upload the case as a .txt
> file instead, or enable Textract and re-upload.

There is deliberately **no home-grown PDF parser**. Pulling bytes out of PDF
content streams without a real library produces mangled text, and the pipeline
would then hand that to a model and record whatever facts it invented. For a
tool that decides how long someone has been in custody, failing with a clear
reason beats guessing.

Transient Textract failures (throttling, `InternalServerError`) are retried
with backoff. A missing subscription or a corrupt document is reported
immediately — retrying cannot fix either, and doing so would burn the Lambda
timeout.

## Known gaps

- **Tokens are readable by any script on the page.** `sessionStorage` is not
  protected from XSS. The exposure is bounded by the 60-minute token and the
  one-day refresh token, but a stricter design would keep the refresh token in
  an HttpOnly cookie behind a small token endpoint.
- **No MFA, and no roles.** Every account sees every case. Cognito supports both;
  neither is configured.
- **The statute values have not been checked by a lawyer.** They were compiled
  with model assistance from the sources in each row's `sourceUrl`, and
  `BNS#305`, `BNS#310(2)` and `BNS#109(1)` are the least certain. They decide
  who is flagged as over-detained, so verify every `maxYears` and `lifeOrDeath`
  against the bare acts before real use.
- **One accused per document.** The extractor takes the first name it finds, so
  co-accused in the same chargesheet are invisible.
- **No duplicate detection.** Re-uploading the same document creates a second
  case.
- **Statute coverage is 12 offences.** Anything else resolves to `NEEDS_REVIEW`.
