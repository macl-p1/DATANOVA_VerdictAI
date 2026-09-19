import boto3, json

bedrock = boto3.client("bedrock-runtime")
MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"

EXPLANATION_SYSTEM_PROMPT = """You explain legal eligibility decisions in plain, clear English for lawyers and court staff. You are given a decision that has ALREADY been made by a rule-based system — you do not make legal judgments yourself, you only explain the given result clearly.

Return ONLY a valid JSON object with one field: "explanation" (a string, 2-4 sentences).

Do not change, question, or second-guess the flag or reasoning you are given — only explain it clearly in plain English, referencing the specific facts (dates, sections, days in custody) provided.
"""

def build_explanation_messages(rule_result: dict) -> list:
    context = (
        f"Flag: {rule_result['flag']}\n"
        f"Days in custody: {rule_result.get('days_in_custody')}\n"
        f"Days overdue: {rule_result.get('days_overdue')}\n"
        f"Rule fired: {rule_result['rule_fired']}"
    )
    return [{"role": "user", "content": [{"text": f"Explain this result:\n\n{context}"}]}]

def lambda_handler(event, context):
    rule_result = event["ruleResult"]

    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": EXPLANATION_SYSTEM_PROMPT}],
        messages=build_explanation_messages(rule_result),
        inferenceConfig={"temperature": 0.3, "maxTokens": 300},
    )

    raw = resp["output"]["message"]["content"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw)
        return {"statusCode": 200, "body": json.dumps({"explanation": parsed["explanation"]})}
    except Exception:
        return {"statusCode": 200, "body": json.dumps({"explanation": rule_result["rule_fired"]})}
