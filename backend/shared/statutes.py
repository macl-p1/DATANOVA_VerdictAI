"""Statute table loader, shared by the Lambdas that run the rule engine.

Cached per container: the table is small, read-only at runtime, and re-scanning
it on every invocation would dominate the cost of evaluating a case.
"""
import os

import boto3

dynamodb = boto3.resource("dynamodb")

_cache = None


def load_statutes(table_name: str | None = None) -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache

    table = dynamodb.Table(table_name or os.environ["STATUTES_TABLE"])
    resp = table.scan()
    items = resp.get("Items", [])

    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))

    _cache = {
        item["code"]: {
            "maxYears": float(item["maxYears"]),
            "lifeOrDeath": bool(item["lifeOrDeath"]),
            "title": item.get("title", ""),
        }
        for item in items
    }
    return _cache
