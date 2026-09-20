import boto3, json, os, re
from decimal import Decimal
from datetime import datetime, timezone
from retention import expires_at

dynamodb = boto3.resource("dynamodb")
TABLE = os.environ["CASES_TABLE"]

# Any extension. Restricting this to txt|pdf meant an unexpected upload could
# not be traced back to its case and was orphaned in UPLOADED for ever.
KEY_PATTERN = re.compile(r"uploads/([^/.]+)\.[A-Za-z0-9]+$")

# textract_extract raises this with wording already meant for a human, so its
# message is used verbatim rather than being re-described here.
READABLE_ERRORS = {"DocumentUnreadable"}


def resolve_case_id(event):
    """The MarkFailed branch of the state machine is reached from RunTextract's
    Catch, whose input is still the raw EventBridge event — it has no caseId.
    Falling back to "unknown" there meant every failed upload overwrote one
    shared row while the real case sat in UPLOADED for ever, so the caseId is
    recovered from the S3 key instead."""
    case_id = event.get("caseId")
    if case_id:
        return case_id
    key = ((event.get("detail") or {}).get("object") or {}).get("key", "")
    match = KEY_PATTERN.search(key)
    return match.group(1) if match else None


def failure_reason(event):
    """Surface the real cause so the case register explains itself.

    A Lambda task failure arrives with Cause as a JSON document carrying
    errorType and errorMessage, so the handler's own wording can be lifted out
    exactly instead of being guessed at from a substring of a stack trace.
    """
    error = event.get("error") or {}
    cause = str(error.get("Cause") or error.get("Error") or "").strip()

    error_type, message = "", ""
    try:
        parsed = json.loads(cause)
        if isinstance(parsed, dict):
            error_type = str(parsed.get("errorType") or "")
            message = str(parsed.get("errorMessage") or "").strip()
    except (TypeError, ValueError):
        pass

    if error_type in READABLE_ERRORS and message:
        return message[:600]

    # Older executions, and failures raised outside our own handlers, still
    # arrive as a bare stack trace.
    haystack = message or cause
    if "SubscriptionRequiredException" in haystack:
        return ("The document could not be read: Amazon Textract is not enabled for this AWS "
                "account. Upload the case as a .txt file, or enable Textract, then re-upload.")
    if "Textract" in haystack or "TimeoutError" in haystack:
        return f"The document could not be read by Textract. {haystack[:300]}"
    if haystack:
        return f"Processing failed before the rule engine could run. {haystack[:300]}"
    return "Processing failed before the rule engine could run. Re-upload the document or verify it manually."


def to_dynamo(value):
    """DynamoDB rejects Python floats, and the evidence blob is full of them
    (every confidence score). Convert on the way in rather than losing the
    scores or rounding them to ints."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    return value


def lambda_handler(event, context):
    table = dynamodb.Table(TABLE)
    case_id = resolve_case_id(event)
    if not case_id:
        # Better to fail the execution loudly than to write a junk row that
        # hides which upload actually broke.
        raise ValueError("No caseId could be resolved from the event or the S3 key")

    if "flag" in event:
        item_update = {
            "status": "PROCESSED",
            "flag": event.get("flag", "NEEDS_REVIEW"),
            # The GSI range key is numeric and cannot be null, so "no overdue
            # figure" is stored as 0 and distinguished by the flag.
            "daysOverdue": event.get("days_overdue") or 0,
            "daysInCustody": event.get("days_in_custody"),
            "ruleFired": event.get("rule_fired", ""),
            "explanation": event.get("explanation", ""),
            "accusedName": event.get("accused_name") or "",
            "arrestDate": event.get("arrest_date") or "",
            "releaseDate": event.get("release_date") or "",
            "inCustody": event.get("in_custody"),
            "firstTimeOffender": event.get("first_time_offender"),
            "otherPendingCases": event.get("other_pending_cases"),
            "sections": event.get("sections") or [],
            "evidence": event.get("evidence") or {},
            "maxDays": event.get("max_days"),
            "halfDays": event.get("half_days"),
            "thirdDays": event.get("third_days"),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    else:
        item_update = {
            "status": "FAILED",
            "flag": "NEEDS_REVIEW",
            "daysOverdue": 0,
            "ruleFired": failure_reason(event),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

    # Refreshed on every write, so the window runs from the last time the case
    # was actually touched rather than from upload.
    item_update["expiresAt"] = expires_at()

    item_update = to_dynamo(item_update)

    table.update_item(
        Key={"caseId": case_id},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in item_update),
        ExpressionAttributeNames={f"#{k}": k for k in item_update},
        ExpressionAttributeValues={f":{k}": v for k, v in item_update.items()},
    )

    return {"statusCode": 200}
