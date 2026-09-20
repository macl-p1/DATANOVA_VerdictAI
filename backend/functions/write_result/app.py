import boto3, os
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
TABLE = os.environ["CASES_TABLE"]

def lambda_handler(event, context):
    table = dynamodb.Table(TABLE)
    case_id = event.get("caseId", "unknown")

    if "flag" in event:
        item_update = {
            "status": "PROCESSED",
            "flag": event.get("flag", "NEEDS_REVIEW"),
            "daysOverdue": event.get("days_overdue") or 0,
            "ruleFired": event.get("rule_fired", ""),
            "explanation": event.get("explanation", ""),
            "arrestDate": event.get("arrest_date") or "",
            "sections": event.get("sections") or [],
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    else:
        item_update = {
            "status": "FAILED",
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

    table.update_item(
        Key={"caseId": case_id},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in item_update),
        ExpressionAttributeNames={f"#{k}": k for k in item_update},
        ExpressionAttributeValues={f":{k}": v for k, v in item_update.items()},
    )

    return {"statusCode": 200}