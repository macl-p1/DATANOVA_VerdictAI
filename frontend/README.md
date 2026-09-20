# VerdictAI frontend

Static pages (no build step, no framework) that read the SAM backend in
[`../backend`](../backend). Every eligibility decision is made by the rules
Lambda; this app renders the result and never re-derives it.

## Point it at a backend

After `sam deploy`, copy the `ApiUrl` stack output and either set it once in the
browser:

```js
localStorage.setItem("verdictai-api-base", "https://xxxx.execute-api.us-east-1.amazonaws.com/prod")
```

or paste it into `FALLBACK` in [`js/config.js`](js/config.js) to bake it in.

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

`.txt` works end to end today. **PDF does not**, because Amazon Textract is not
enabled on the AWS account the stack is deployed to — `StartDocumentTextDetection`
returns `SubscriptionRequiredException`. The pipeline handles this correctly: the
case is marked `FAILED` within seconds and the register shows

> The document could not be read: Amazon Textract is not enabled for this AWS
> account. Upload the case as a .txt file, or enable Textract, then re-upload.

Enable Textract in the account (it is a per-account service activation, not an
IAM change — the Lambda already holds the right permissions) and PDFs will work
with no code change.

## Data retention

Case rows hold the accused's name, charges and arrest date. The table has TTL
enabled on `expiresAt`, set from `CaseRetentionDays` (default 90) and refreshed
on every write. DynamoDB removes expired items within roughly 48 hours of the
timestamp, so treat it as a retention policy rather than a guarantee. Rows
written before this existed have no `expiresAt` and will not expire on their own.

## Known gaps

- **Sign-in is cosmetic, and the API is unauthenticated.** It gates the screens
  from `sessionStorage` only. The API Gateway stage has no authorizer, so anyone
  with the URL can read every case record and create new ones. This is the
  largest outstanding problem and needs a real authorizer.
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
