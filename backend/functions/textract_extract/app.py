"""Turns an uploaded document into plain text for the extraction step.

Two routes in, and the file's own bytes decide which — not its extension, and
not what the uploader claimed the content type was:

  * Anything that decodes as text is used directly. This route has no
    dependency on Textract at all, so a .txt upload keeps working when Textract
    is disabled, throttled, or the account has never been approved for it.
  * Anything else is treated as a scanned document and sent to Textract.

Trying the text route first is both cheaper and more robust: a PDF never
decodes as text, so nothing is mis-routed, while a text file that was uploaded
with a .pdf name still goes through fine.

A genuine PDF cannot be read without Textract. There is deliberately no
home-grown PDF parser here: pulling bytes out of PDF content streams without a
real library produces mangled text, and this pipeline would then hand that to a
model and record whatever facts it invented. Failing with a clear reason is the
safer outcome for a tool that decides how long someone has been in custody.
"""
import re
import time

import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
textract = boto3.client("textract")

# Any extension — the case id must resolve even for a file we did not expect,
# or the upload is orphaned in UPLOADED for ever with nothing pointing at it.
KEY_PATTERN = re.compile(r"uploads/([^/.]+)\.[A-Za-z0-9]+$")

PDF_MAGIC = b"%PDF-"
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")

POLL_SECONDS = 3
MAX_POLLS = 40  # ~2 minutes; the Lambda timeout must stay above this
RETRY_BACKOFF = (2, 5, 10)

# Textract is a per-account opt-in service. Until it is approved every call
# fails this way, which is not a fault of the document.
UNAVAILABLE_CODES = {
    "SubscriptionRequiredException",
    "AccessDeniedException",
    "AccessDeniedError",
    "UnrecognizedClientException",
    "InvalidSignatureException",
    "OptInRequired",
}
DOCUMENT_CODES = {
    "UnsupportedDocumentException",
    "InvalidS3ObjectException",
    "DocumentTooLargeException",
    "BadDocumentException",
    "InvalidParameterException",
    "InvalidDocumentException",
}
RETRYABLE_CODES = {
    "ThrottlingException",
    "ThrottledException",
    "ProvisionedThroughputExceededException",
    "LimitExceededException",
    "InternalServerError",
    "ServiceUnavailable",
}


class DocumentUnreadable(Exception):
    """Carries a message meant for a human reading the case register.

    write_result reads this off the Step Functions error and stores it as the
    case's reason, so the wording here is what a lawyer ends up seeing.
    """


def decode_if_text(body):
    """The document's text if these bytes are already plain text, else None.

    Deliberately strict. Guessing wrong in the permissive direction would feed
    decoded binary noise to the extraction model, so anything uncertain is sent
    to Textract instead.
    """
    if not body or body.startswith(PDF_MAGIC):
        return None

    encodings = ["utf-8-sig"]
    if body.startswith(UTF16_BOMS):
        encodings.append("utf-16")

    for encoding in encodings:
        try:
            text = body.decode(encoding)
        except (UnicodeDecodeError, UnicodeError, LookupError):
            continue
        if looks_like_text(text):
            return text
    return None


def looks_like_text(text):
    """Strict UTF-8 already rejects most binary; this catches the rest."""
    if not text.strip() or "\x00" in text:
        return False
    control = sum(1 for ch in text if ord(ch) < 32 and ch not in "\t\n\r\f\v")
    return control / len(text) < 0.01


def classify(error, operation_name):
    code = error.response.get("Error", {}).get("Code", "")
    if code in UNAVAILABLE_CODES:
        return DocumentUnreadable(
            "This looks like a scanned PDF, which needs Amazon Textract to read, and Textract "
            "is not available to this AWS account yet. Upload the case as a .txt file instead, "
            "or enable Textract and re-upload. "
            "(Textract reported " + code + " on " + operation_name + ".)"
        )
    if code in DOCUMENT_CODES:
        return DocumentUnreadable(
            "Amazon Textract could not read this document. It may be corrupt, password "
            "protected, or larger than Textract accepts. Check that it opens normally, or paste "
            "its text into a .txt file and upload that instead. "
            "(Textract reported " + code + ".)"
        )
    return error


def call_with_retry(operation, **kwargs):
    """Retries only the transient Textract failures. A missing subscription or
    an unreadable document is reported immediately — retrying cannot fix it."""
    last = None
    for attempt in range(len(RETRY_BACKOFF) + 1):
        try:
            return operation(**kwargs)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code not in RETRYABLE_CODES or attempt == len(RETRY_BACKOFF):
                raise classify(error, getattr(operation, "__name__", "Textract"))
            last = error
            time.sleep(RETRY_BACKOFF[attempt])
    raise last


def extract_pdf_text(bucket, key):
    """Run Textract over a PDF. The asynchronous API is used because the
    synchronous one does not accept multi-page PDFs, and chargesheets rarely
    fit on one page."""
    job = call_with_retry(
        textract.start_document_text_detection,
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}},
    )
    job_id = job["JobId"]

    for _ in range(MAX_POLLS):
        time.sleep(POLL_SECONDS)
        status_resp = call_with_retry(
            textract.get_document_text_detection, JobId=job_id, MaxResults=1
        )
        status = status_resp["JobStatus"]
        if status == "SUCCEEDED":
            break
        if status == "FAILED":
            raise DocumentUnreadable(
                "Amazon Textract could not read this document: "
                + str(status_resp.get("StatusMessage") or "no reason given")
                + ". Upload the case as a .txt file instead."
            )
    else:
        raise DocumentUnreadable(
            "Amazon Textract did not finish reading this document in time. It may be very long. "
            "Try a smaller file, or upload the case as a .txt file instead."
        )

    lines, next_token = [], None
    while True:
        kwargs = {"JobId": job_id}
        if next_token:
            kwargs["NextToken"] = next_token
        page = call_with_retry(textract.get_document_text_detection, **kwargs)
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

    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()

    # Text first: this route works whether or not Textract is reachable.
    document_text = decode_if_text(body)
    source = "text"

    if document_text is None:
        document_text = extract_pdf_text(bucket, key)
        source = "textract"

    if not document_text.strip():
        raise DocumentUnreadable(
            "No text could be read from the uploaded document. If it is a scan it may be blank "
            "or too faint; if it is a text file it may be empty."
        )

    return {"documentText": document_text, "caseId": case_id, "textSource": source}
