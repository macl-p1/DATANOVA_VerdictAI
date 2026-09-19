from datetime import date
from schemas import Extracted, RuleResult


def evaluate(e: Extracted, statutes: dict[str, dict], today: date) -> RuleResult:
    # Missing the basics -> can't compute anything, don't guess
    if not e.arrest_date or not e.sections:
        return RuleResult(
            flag="NEEDS_REVIEW", days_in_custody=None, days_overdue=None,
            rule_fired="Missing arrest date or charged sections"
        )

    # Any section not in our verified table -> don't silently ignore it
    unknown = [s for s in e.sections if s not in statutes]
    if unknown:
        return RuleResult(
            flag="NEEDS_REVIEW", days_in_custody=None, days_overdue=None,
            rule_fired=f"Unknown section(s): {unknown}"
        )

    # Life/death offences are outside Section 479 BNSS entirely
    if any(statutes[s]["lifeOrDeath"] for s in e.sections):
        return RuleResult(
            flag="NOT_ELIGIBLE", days_in_custody=None, days_overdue=None,
            rule_fired="Offence punishable with death or life imprisonment"
        )

    # Other pending cases bar release under this provision
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
            rule_fired=f"Served {days_in_custody}d, exceeds max sentence of {max_days}d"
        )

    if days_in_custody >= max_days // 2:
        return RuleResult(
            flag="PAST_HALF", days_in_custody=days_in_custody,
            days_overdue=days_in_custody - max_days // 2,
            rule_fired=f"Served over half the max sentence ({max_days // 2}d)"
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
    extracted = Extracted(**event)

    # TODO: replace with a real DynamoDB read from the Statutes table
    statutes = {
        "IPC#379": {"maxYears": 3, "lifeOrDeath": False},
        "IPC#302": {"maxYears": 0, "lifeOrDeath": True},
    }

    result = evaluate(extracted, statutes, today=date.today())

    return {"statusCode": 200, "body": result.model_dump_json()}