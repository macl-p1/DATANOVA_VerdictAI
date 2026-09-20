import boto3, re

s3 = boto3.client("s3")

def lambda_handler(event, context):
    detail = event["detail"]
    bucket = detail["bucket"]["name"]
    key = detail["object"]["key"]

    match = re.search(r"uploads/([^/.]+)\.(txt|pdf)$", key)
    case_id = match.group(1) if match else None

    obj = s3.get_object(Bucket=bucket, Key=key)
    document_text = obj["Body"].read().decode("utf-8")

    return {"documentText": document_text, "caseId": case_id}