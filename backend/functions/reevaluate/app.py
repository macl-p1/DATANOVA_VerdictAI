"""Re-runs the rule engine on open cases as custody lengthens.

The flag written when a case is first processed is a snapshot: it was computed
against that day's date and then frozen in DynamoDB. But the whole point of
Section 479 is that eligibility arrives with the passage of time — a case below
every threshold today crosses the one-third line, then the half line, then the
full term, purely because nobody released the person. Without this sweep a case
flagged NOT_YET stayed NOT_YET for ever and the register quietly went stale.

Runs on a schedule. It re-evaluates from the facts already stored, so it costs
no Bedrock extraction; the plain-English explanation is only regenerated when
the flag actually changes.
"""
import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal

import boto3

from schemas import Extracted
from statutes import load_statutes
from rules_engine import evaluate
from retention import expires_at

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

CASES_TABLE = os.environ["CASES_TABLE"]
EXPLAIN_FUNCTION = os.environ.get("EXPLAIN_FUNCTION_NAME", "")

# Flags worth revisiting. PAST_MAX is already the end of the scale; NOT_ELIGIBLE
# turns on a statutory bar that time does not lift; NEEDS_REVIEW needs a human,
# not another pass of the same logic.
OPEN_FLAGS = {"NOT_YET", "PAST_THIRD", "PAST_HALF"}


def to_float(value):
    return float(value) if isinstance(value, Decimal) else value


def to_dynamo(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    return value


def rebuild_extracted(record) -> Extracted | None:
    """Reconstruct the engine's input from the stored case. Returns None when
    the record predates evidence capture and cannot be re-evaluated safely."""
    evidence = {}
    for name, item in (record.get("evidence") or {}).items():
        if not isinstance(item, dict):
            continue
        evidence[name] = {
            "value": item.get("value"),
            "source_quote": item.get("source_quote"),
            "confidence": to_float(item.get("confidence")) or 0.0,
        }
    if not evidence:
        return None

    try:
        return Extracted(
            accused_name=record.get("accusedName") or None,
            sections=list(record.get("sections") or []),
            arrest_date=record.get("arrestDate") or None,
            in_custody=bool(record.get("inCustody", True)),
            release_date=record.get("releaseDate") or None,
            first_time_offender=record.get("firstTimeOffender"),
            other_pending_cases=record.get("otherPendingCases"),
            evidence=evidence,
        )
    except Exception:
        return None


def regenerate_explanation(result_dict):
    """Ask the explain Lambda for fresh wording. A failure here must not lose
    the recomputed flag, so the old explanation is kept instead."""
    if not EXPLAIN_FUNCTION:
        return None
    try:
        resp = lambda_client.invoke(
            FunctionName=EXPLAIN_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps(result_dict).encode(),
        )
        body = json.loads(resp["Payload"].read() or b"{}")
        return body.get("explanation")
    except Exception:
        return None


def scan_open_cases(table):
    kwargs = {}
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            if item.get("status") == "PROCESSED" and item.get("flag") in OPEN_FLAGS:
                yield item
        key = resp.get("LastEvaluatedKey")
        if not key:
            return
        kwargs["ExclusiveStartKey"] = key


def lambda_handler(event, context):
    table = dynamodb.Table(CASES_TABLE)
    statutes = load_statutes()
    today = date.today()

    examined = changed = flag_changes = skipped = 0

    for record in scan_open_cases(table):
        examined += 1
        extracted = rebuild_extracted(record)
        if extracted is None:
            skipped += 1
            continue

        result = evaluate(extracted, statutes, today=today)

        old_flag = record.get("flag")
        old_overdue = to_float(record.get("daysOverdue"))
        new_overdue = result.days_overdue or 0
        if result.flag == old_flag and new_overdue == old_overdue:
            continue

        update = {
            "flag": result.flag,
            "daysOverdue": new_overdue,
            "daysInCustody": result.days_in_custody,
            "ruleFired": result.rule_fired,
            "maxDays": result.max_days,
            "halfDays": result.half_days,
            "thirdDays": result.third_days,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "reevaluatedAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": expires_at(),
        }

        if result.flag != old_flag:
            flag_changes += 1
            fresh = regenerate_explanation({
                "flag": result.flag,
                "days_in_custody": result.days_in_custody,
                "days_overdue": result.days_overdue,
                "rule_fired": result.rule_fired,
            })
            if fresh:
                update["explanation"] = fresh

        update = to_dynamo(update)
        table.update_item(
            Key={"caseId": record["caseId"]},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in update),
            ExpressionAttributeNames={f"#{k}": k for k in update},
            ExpressionAttributeValues={f":{k}": v for k, v in update.items()},
        )
        changed += 1

    summary = {
        "examined": examined,
        "updated": changed,
        "flagChanges": flag_changes,
        "skippedWithoutEvidence": skipped,
    }
    print(json.dumps(summary))
    return summary
