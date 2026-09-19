import boto3, json
from schemas import Extracted

bedrock = boto3.client("bedrock-runtime")
MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"

EXTRACTION_SYSTEM_PROMPT = """You are a legal document analysis assistant. You extract structured facts from Indian criminal case documents (chargesheets, FIRs). You do not interpret the law or make legal judgments — you only extract what is stated in the text.

Return ONLY a valid JSON object. No explanation, no markdown formatting, no text before or after the JSON.

Extract these fields:
- sections: array of charged legal sections, in the EXACT format "PREFIX#NUMBER" (e.g. "IPC#379", "BNS#303"). Use IPC for Indian Penal Code references, BNS for Bharatiya Nyaya Sanhita references. Do not write "Section 379" or "IPC Section 379" — only "IPC#379".
- arrest_date: the date of arrest, in YYYY-MM-DD format. If not stated, use null.
- in_custody: true if the person is currently in judicial custody, false if released, based on the text.
- release_date: if the person has been released, the release date in YYYY-MM-DD format. Otherwise null.
- first_time_offender: true if the text states this is their first offence, false if prior convictions are mentioned, null if not stated.
- other_pending_cases: true if the text mentions other pending cases against this person, false if it explicitly says there are none, null if not mentioned at all.
- evidence: for each field above, an object with:
  - value: the extracted value as a string
  - source_quote: the exact sentence or phrase from the text that supports this value
  - confidence: a number 0.0 to 1.0 for how certain you are

If a fact is not stated in the text, use null for that field's value and set confidence to 0.0. Do not guess or infer beyond what the text says.

Example output:
{"sections": ["IPC#379"], "arrest_date": "2019-03-15", "in_custody": true, "release_date": null, "first_time_offender": true, "other_pending_cases": false, "evidence": {"arrest_date": {"value": "2019-03-15", "source_quote": "arrested on 15th March 2019", "confidence": 0.95}}}
"""

def build_extraction_messages(document_text: str) -> list:
    return [
        {
            "role": "user",
            "content": [{"text": f"Extract facts from this document:\n\n{document_text}"}]
        }
    ]

def lambda_handler(event, context):
    document_text = event["documentText"]

    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": EXTRACTION_SYSTEM_PROMPT}],
        messages=build_extraction_messages(document_text),
        inferenceConfig={"temperature": 0, "maxTokens": 1000},
    )

    raw = resp["output"]["message"]["content"][0]["text"].strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        extracted = Extracted.model_validate_json(raw)
        return {"statusCode": 200, "body": extracted.model_dump_json()}
    except Exception as e:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "flag": "NEEDS_REVIEW",
                "rule_fired": f"Extraction failed validation: {str(e)}"
            })
        }