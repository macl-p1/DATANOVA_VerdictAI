import boto3, re, time

s3 = boto3.client("s3")
textract = boto3.client("textract")

KEY_PATTERN = re.compile(r"uploads/([^/.]+)\.(txt|pdf)$")

POLL_SECONDS = 3
MAX_POLLS = 40  # ~2 minutes; the Lambda timeout must stay above this


def extract_pdf_text(bucket: str, key: str) -> str:
    """Run Textract over a PDF. The asynchronous API is used because the
    synchronous one does not accept multi-page PDFs, and chargesheets rarely
    fit on one page."""
    job = textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    job_id = job["JobId"]

    for _ in range(MAX_POLLS):
        time.sleep(POLL_SECONDS)
        status_resp = textract.get_document_text_detection(JobId=job_id, MaxResults=1)
        status = status_resp["JobStatus"]
        if status == "SUCCEEDED":
            break
        if status == "FAILED":
            raise RuntimeError(f"Textract could not read the document: {status_resp.get('StatusMessage')}")
    else:
        raise TimeoutError("Textract did not finish within the allowed time")

    lines, next_token = [], None
    while True:
        kwargs = {"JobId": job_id}
        if next_token:
            kwargs["NextToken"] = next_token
        page = textract.get_document_text_detection(**kwargs)
        lines.extend(block["Text"] for block in page["Blocks"] if block["BlockType"] == "LINE")
        next_token = page.get("NextToken")
        if not next_token:
            break

    return "\n".join(lines)


def lambda_handler(event, context):
    detail = event["detail"]
    bucket = detail["bucket"]["name"]
    key = detail["object"]["key"]

    match = KEY_PATTERN.search(key)
    case_id = match.group(1) if match else None
    extension = match.group(2) if match else "pdf"

    if extension == "txt":
        obj = s3.get_object(Bucket=bucket, Key=key)
        document_text = obj["Body"].read().decode("utf-8", errors="replace")
    else:
        document_text = extract_pdf_text(bucket, key)

    if not document_text.strip():
        raise ValueError("No text could be read from the uploaded document")

    return {"documentText": document_text, "caseId": case_id}
