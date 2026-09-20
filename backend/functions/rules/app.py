import boto3, os
from datetime import date
from schemas import Extracted, RuleResult

dynamodb = boto3.resource("dynamodb")
STATUTES_TABLE = os.environ["STATUTES_TABLE"]

_statutes_cache = None

def load_statutes():
    global _statutes_cache
    if _statutes_cache is not None:
        return _statutes_cache

    table = dynamodb.Table(STATUTES_TABLE)
    resp = table.scan()
    items = resp.get("Items", [])

    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))

    _statutes_cache = {
        item["code"]: {
            "maxYears": float(item["maxYears"]),
            "lifeOrDeath": bool(item["lifeOrDeath"]),
        }
        for item in items
    }
    return _statutes_cache


def evaluate(e: Extracted, statutes: dict[str, dict], today: date) -> RuleResult:
    if not e.arrest_date or not e.sections:
        return RuleResult(
            flag="NEEDS_REVIEW", days_in_custody=None, days_overdue=None,
            rule_fired="Missing arrest date or charged sections"
        )

    unknown = [s for s in e.sections if s not in statutes]
    if unknown:
        return RuleResult(
            flag="NEEDS_REVIEW", days_in_custody=None, days_overdue=None,
            rule_fired=f"Unknown section(s): {unknown}"
        )

    if any(statutes[s]["lifeOrDeath"] for s in e.sections):
        return RuleResult(
            flag="NOT_ELIGIBLE", days_in_custody=None, days_overdue=None,
            rule_fired="Offence punishable with death or life imprisonment"
        )

    if e.other_pending_cases:
        return RuleResult(
            flag="NOT_ELIGIBLE", days_in_custody=None, days_overdue=None,
            rule_fired="Other cases pending against the accused"
        )

    end_date = e.release_date or today
    days_in_custody = (end_date - e.arrest_date).days

    max_years = max(statutes[s]["maxYears"] for s in e.sections)
    max_days = max_years * 365

    if days_in_custody >= max_days:
        return RuleResult(
            flag="PAST_MAX", days_in_custody=days_in_custody,
            days_overdue=days_in_custody - max_days,
            rule_fired=f"Served {days_in_custody}d, exceeds max sentence of {max_days:.0f}d"
        )

    if days_in_custody >= max_days // 2:
        return RuleResult(
            flag="PAST_HALF", days_in_custody=days_in_custody,
            days_overdue=days_in_custody - max_days // 2,
            rule_fired=f"Served over half the max sentence ({max_days // 2:.0f}d)"
        )

    if e.first_time_offender and days_in_custody >= max_days // 3:
        return RuleResult(
            flag="PAST_THIRD", days_in_custody=days_in_custody,
            days_overdue=days_in_custody - max_days // 3,
            rule_fired="First-time offender past one-third threshold"
        )

    return RuleResult(
        flag="NOT_YET", days_in_custody=days_in_custody,
        days_overdue=None, rule_fired="Below all thresholds"
    )


def lambda_handler(event, context):
    case_id = event.pop("caseId", None)
    extracted = Extracted(**event)

    statutes = load_statutes()

    result = evaluate(extracted, statutes, today=date.today())
    output = result.model_dump(mode="json")
    output["caseId"] = case_id
    return output