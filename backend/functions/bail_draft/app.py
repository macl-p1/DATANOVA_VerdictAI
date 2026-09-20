import boto3, json, os
from http_utils import respond

bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"

ELIGIBLE_FLAGS = {"PAST_MAX", "PAST_HALF", "PAST_THIRD"}

BAIL_DRAFT_SYSTEM_PROMPT = """You draft bail/release applications under Section 479 BNSS (undertrial detention exceeding statutory limits) for Indian courts. You are given a case's facts and the rule that determined eligibility — you do not make legal judgments, only draft the application text using the facts and reasoning provided.

Return ONLY a valid JSON object with one field: "draft" (a string containing the full application text).

Structure the draft as a formal court application with these sections:
1. Title: "APPLICATION FOR RELEASE UNDER SECTION 479 OF THE BHARATIYA NAGARIK SURAKSHA SANHITA, 2023"
2. To: [placeholder for the court name]
3. In the matter of: [case reference placeholder]
4. Facts: state the accused's name, arrest date, charged section(s), and days in custody, using the exact figures given
5. Grounds: cite the specific rule that was triggered (e.g. "the accused has served in excess of the maximum period of imprisonment prescribed for the said offence")
6. Prayer: request for immediate release
7. Signature block: "[Advocate Name]\\nCounsel for the Accused\\n[Bar Registration Number]\\n[Date]"

Use placeholders in [brackets] for anything not provided in the facts (court name, case number, advocate details). Do not invent specific facts not given. Keep the tone formal and legally appropriate."""


def build_bail_draft_messages(case_data: dict) -> list:
    context = (
        f"Case ID: {case_data.get('caseId')}\n"
        f"Accused name: {case_data.get('accusedName') or 'not recorded'}\n"
        f"Flag: {case_data.get('flag')}\n"
        f"Days in custody: {case_data.get('daysInCustody') or 'not recorded'}\n"
        f"Days overdue: {case_data.get('daysOverdue')}\n"
        f"Rule fired: {case_data.get('ruleFired')}\n"
        f"Arrest date: {case_data.get('arrestDate') or 'not recorded'}\n"
        f"Charged sections: {', '.join(case_data.get('sections', [])) or 'not recorded'}\n"
    )
    return [{"role": "user", "content": [{"text": f"Draft a bail application for this case:\n\n{context}"}]}]


def lambda_handler(event, context):
    path_params = event.get("pathParameters") or {}
    case_id = path_params.get("caseId")

    if not case_id:
        return respond(400, {"error": "caseId required"})

    table = dynamodb.Table(os.environ["CASES_TABLE"])
    resp = table.get_item(Key={"caseId": case_id})
    case_data = resp.get("Item")

    if not case_data:
        return respond(404, {"error": "Case not found"})

    if case_data.get("status") != "PROCESSED" or case_data.get("flag") not in ELIGIBLE_FLAGS:
        return respond(400, {
            "error": "Case is not eligible for a bail draft — flag must be PAST_MAX, PAST_HALF, or PAST_THIRD"
        })

    bedrock_resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": BAIL_DRAFT_SYSTEM_PROMPT}],
        messages=build_bail_draft_messages(case_data),
        inferenceConfig={"temperature": 0.3, "maxTokens": 1500},
    )

    raw = bedrock_resp["output"]["message"]["content"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw)
        draft = parsed["draft"]
    except Exception:
        draft = raw  # fall back to raw text if JSON parsing fails, still useful

    return respond(200, {"caseId": case_id, "draft": draft})
