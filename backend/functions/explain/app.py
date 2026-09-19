import json

def lambda_handler(event, context):
    # TODO: replace with real Bedrock call once account verification clears
    return {
        "statusCode": 200,
        "body": json.dumps({
            "explanation": "This person has been in custody for 2,600+ days, well past the maximum sentence of 3 years for theft under IPC 379. They are entitled to immediate release under Section 479 BNSS."
        })
    }