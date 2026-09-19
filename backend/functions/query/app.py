# backend/functions/query/app.py
import json, os, boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
TABLE = os.environ["CASES_TABLE"]

def lambda_handler(event, context):
    table = dynamodb.Table(TABLE)
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    if path_params.get("caseId"):
        resp = table.get_item(Key={"caseId": path_params["caseId"]})
        item = resp.get("Item")
        if not item:
            return {"statusCode": 404, "body": json.dumps({"error": "Case not found"})}
        return {"statusCode": 200, "body": json.dumps(item, default=str)}

    flag = query_params.get("flag")
    if flag:
        resp = table.query(
            IndexName="flag-daysOverdue-index",
            KeyConditionExpression=Key("flag").eq(flag),
            ScanIndexForward=False,
        )
    else:
        resp = table.scan()

    return {"statusCode": 200, "body": json.dumps(resp.get("Items", []), default=str)}