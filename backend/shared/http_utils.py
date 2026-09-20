"""Shared HTTP response helpers for the API-facing Lambdas.

API Gateway's Cors block only answers the OPTIONS preflight. With a Lambda
proxy integration the actual 200/4xx response still has to carry the
Access-Control-Allow-Origin header itself, or the browser discards it.
"""
import json
from decimal import Decimal

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB hands back every number as Decimal. Emit whole numbers as ints
    and confidence scores as floats, so the UI does not have to parse strings."""

    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        return super().default(o)


def respond(status_code: int, body) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, cls=DecimalEncoder),
    }
