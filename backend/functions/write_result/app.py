import boto3, os, re
from decimal import Decimal
from datetime import datetime, timezone
from retention import expires_at

dynamodb = boto3.resource("dynamodb")
TABLE = os.environ["CASES_TABLE"]

KEY_PATTERN = re.compile(r"uploads/([^/.]+)\.(?:txt|pdf)$")


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
    """Surface the real cause so the case register explains itself."""
    error = event.get("error") or {}
    cause = str(error.get("Cause") or error.get("Error") or "").strip()
    if "SubscriptionRequiredException" in cause:
        return ("The document could not be read: Amazon Textract is not enabled for this AWS "
                "account. Upload the case as a .txt file, or enable Textract, then re-upload.")
    if "Textract" in cause or "TimeoutError" in cause:
        return f"The document could not be read by Textract. {cause[:300]}"
    if cause:
        return f"Processing failed before the rule engine could run. {cause[:300]}"
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
