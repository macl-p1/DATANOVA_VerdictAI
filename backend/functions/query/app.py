# backend/functions/query/app.py
import os

import boto3
from boto3.dynamodb.conditions import Key
from http_utils import respond

dynamodb = boto3.resource("dynamodb")
TABLE = os.environ["CASES_TABLE"]

# A single scan/query returns at most 1MB and then stops, so the register was
# silently truncated once the table outgrew that. Pages are now followed, but
# with a ceiling — returning an unbounded register to the browser would only
# move the problem. Raise with ?limit=, up to MAX_LIMIT.
DEFAULT_LIMIT = 500
MAX_LIMIT = 2000


def parse_limit(query_params):
    raw = (query_params or {}).get("limit")
    if raw is None:
        return DEFAULT_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def collect(table, limit, **kwargs):
    """Follow pages until the limit is reached or the table is exhausted."""
    items = []
    while True:
        resp = table.query(**kwargs) if "KeyConditionExpression" in kwargs else table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        key = resp.get("LastEvaluatedKey")
        if not key or len(items) >= limit:
            break
        kwargs["ExclusiveStartKey"] = key
    return items[:limit]


def lambda_handler(event, context):
    table = dynamodb.Table(TABLE)
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    if path_params.get("caseId"):
        resp = table.get_item(Key={"caseId": path_params["caseId"]})
        item = resp.get("Item")
        if not item:
            return respond(404, {"error": "Case not found"})
        return respond(200, item)

    limit = parse_limit(query_params)
    flag = query_params.get("flag")

    if flag:
        items = collect(
            table, limit,
            IndexName="flag-daysOverdue-index",
            KeyConditionExpression=Key("flag").eq(flag),
            ScanIndexForward=False,
        )
    else:
        items = collect(table, limit)

    return respond(200, items)
