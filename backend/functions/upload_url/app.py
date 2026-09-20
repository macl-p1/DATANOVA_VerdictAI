import json, os, re, uuid, boto3
from datetime import datetime, timezone
from http_utils import respond
from retention import expires_at

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET = os.environ["UPLOAD_BUCKET"]
TABLE = os.environ["CASES_TABLE"]

# Only used to sign the upload with a sensible Content-Type. It does not decide
# how the document is read: textract_extract sniffs the bytes, so a text file
# named .pdf still takes the text route and never needs Textract.
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "text": "text/plain",
    "md": "text/markdown",
}


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (TypeError, ValueError):
        body = {}

    filename = str(body.get("filename") or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
    if extension not in CONTENT_TYPES:
        extension = "pdf"

    case_id = str(uuid.uuid4())
    s3_key = f"uploads/{case_id}.{extension}"

    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": s3_key, "ContentType": CONTENT_TYPES[extension]},
        ExpiresIn=300,
    )

    # Keep the original filename so the register can show what was uploaded
    # before the pipeline has produced an accused name.
    safe_name = re.sub(r"[^\w.\- ]", "", filename)[:200]

    table = dynamodb.Table(TABLE)
    table.put_item(Item={
        "caseId": case_id,
        "status": "UPLOADED",
        "flag": "NEEDS_REVIEW",
        "daysOverdue": 0,
        "s3Key": s3_key,
        "sourceFilename": safe_name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "expiresAt": expires_at(),
    })

    return respond(200, {
        "caseId": case_id,
        "uploadUrl": presigned_url,
        "contentType": CONTENT_TYPES[extension],
    })
