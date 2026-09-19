"""Example deterministic evaluator. It receives validated facts, never logits."""
from __future__ import annotations

from datetime import date

from verdictai.schemas import ExtractionResult, RuleResult


def evaluate(extracted: ExtractionResult, statutes: dict[str, int], today: date | None = None) -> RuleResult:
    today = today or date.today()
    values = {entity.type: entity.normalized_value or entity.value for entity in extracted.entities}
    if extracted.needs_review:
        return RuleResult(flag="NEEDS_REVIEW", rule_fired="extraction_requires_review")
    arrest, section = values.get("ARREST_DATE"), values.get("LEGAL_SECTION")
    if not arrest or not section or section not in statutes:
        return RuleResult(flag="NEEDS_REVIEW", rule_fired="required_fact_missing_or_unknown_statute")
    try:
        custody_days = (today - date.fromisoformat(arrest)).days
    except ValueError:
        return RuleResult(flag="NEEDS_REVIEW", rule_fired="unparseable_arrest_date")
    maximum_days = statutes[section] * 365
    if custody_days >= maximum_days:
        return RuleResult(flag="PAST_MAX", days_in_custody=custody_days, days_overdue=custody_days - maximum_days, rule_fired="custody_at_or_over_maximum")
    if custody_days >= maximum_days / 2:
        return RuleResult(flag="PAST_HALF", days_in_custody=custody_days, days_overdue=0, rule_fired="custody_at_or_over_half")
    return RuleResult(flag="NOT_YET", days_in_custody=custody_days, days_overdue=0, rule_fired="custody_below_half")
