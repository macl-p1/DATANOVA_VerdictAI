import json
from shared.schemas import Extracted, Field

def lambda_handler(event, context):
    # TODO: replace with real Bedrock call once account verification clears
    fake = Extracted(
        sections=["IPC#379"],
        arrest_date="2019-01-01",
        in_custody=True,
        release_date=None,
        first_time_offender=True,
        other_pending_cases=False,
        evidence={
            "arrest_date": Field(value="2019-01-01", source_quote="arrested on 01/01/2019", confidence=0.95)
        }
    )
    return {"statusCode": 200, "body": fake.model_dump_json()}