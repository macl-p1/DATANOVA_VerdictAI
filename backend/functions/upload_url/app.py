import json, os, uuid, boto3
from datetime import datetime, timezone

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET = os.environ["UPLOAD_BUCKET"]
TABLE = os.environ["CASES_TABLE"]

def lambda_handler(event, context):
    case_id = str(uuid.uuid4())
    s3_key = f"uploads/{case_id}.pdf"

    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": s3_key, "ContentType": "application/pdf"},
        ExpiresIn=300,
    )

    table = dynamodb.Table(TABLE)
    table.put_item(Item={
        "caseId": case_id,
        "status": "UPLOADED",
        "s3Key": s3_key,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"caseId": case_id, "uploadUrl": presigned_url}),
    }