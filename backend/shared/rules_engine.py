"""The Section 479 BNSS rule engine.

This is the only place eligibility is decided. It lives in the shared layer
rather than inside one function because two Lambdas need it: `rules`, which
evaluates a case when it is first processed, and `reevaluate`, which re-runs it
on a schedule as custody lengthens.

Nothing here talks to AWS or to a model. It is pure logic over an Extracted.
"""
import os
import re
from datetime import date

from schemas import Extracted, RuleResult

# A fact the engine is about to rely on must be supported by evidence at or
# above this score. schemas.py promises exactly this ("low-confidence fields
# can trigger NEEDS_REVIEW instead of a silent wrong answer"); before it was
# enforced, an arrest date extracted at 0.2 confidence produced a hard flag
# indistinguishable from one extracted at 0.99.
#
# The default is high because the extraction model is poorly calibrated: on a
# document stating in terms that the arrest date was unconfirmed and the remand
# register untraced, it still returned 0.7-0.8 and scored every other field 1.0.
# Tuned against a handful of documents, not labelled data — it needs proper
# calibration, and is a deploy parameter (ConfidenceThreshold) so it can be
# moved without a code change.
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.90"))

# No one has been in custody for a century. A span this long means a misread
# year, not a real detention.
MAX_PLAUSIBLE_CUSTODY_DAYS = 100 * 365

# "BNS 303(2)", "Section 303(2) BNS", "bns#303(2)" all mean the same row in the
# statutes table. The table is keyed "BNS#303(2)", so everything is folded to
# that shape before lookup — an unrecognised spelling must fail as an unknown
# section, never as a silent miss that changes the flag.
_SECTION_PATTERN = re.compile(
    r"(?:^|\b)(?:section\s+)?(IPC|BNS)\s*[#\s]?\s*([0-9]+(?:\s*\([0-9a-zA-Z]+\))?(?:-[IV]+)?)",
    re.IGNORECASE,
)
_TRAILING_PATTERN = re.compile(
    r"(?:^|\b)(?:section\s+)?([0-9]+(?:\s*\([0-9a-zA-Z]+\))?(?:-[IV]+)?)\s*(?:of\s+the\s+)?(IPC|BNS)\b",
    re.IGNORECASE,
)


def normalize_section(raw: str) -> str | None:
    """Fold any spelling of a section reference to the table's "PREFIX#NUMBER" key."""
    if not raw:
        return None
    text = str(raw).strip()
    match = _SECTION_PATTERN.search(text) or _TRAILING_PATTERN.search(text)
    if not match:
        return None
    groups = match.groups()
    prefix, number = (groups[0], groups[1]) if groups[0].upper() in ("IPC", "BNS") else (groups[1], groups[0])
    return f"{prefix.upper()}#{number.replace(' ', '')}"


def unverified_facts(e: Extracted, threshold: float) -> list[str]:
    """Names the facts this decision would rest on that the extraction cannot
    vouch for — either scored below the threshold, or with no evidence recorded
    at all. A fact left null is not listed: the engine already treats a missing
    fact conservatively, so there is nothing to distrust.

    No attempt is made to judge which direction an error would fall in. A
    low-confidence fact means a human should look, whichever way it points."""
    required = ["sections", "arrest_date"]
    if e.release_date is not None:
        required.append("release_date")
    if e.first_time_offender is not None:
        required.append("first_time_offender")
    if e.other_pending_cases is not None:
        required.append("other_pending_cases")

    problems = []
    for name in required:
        item = e.evidence.get(name)
        if item is None:
            problems.append(f"{name} (no supporting evidence recorded)")
        elif item.confidence < threshold:
            problems.append(f"{name} ({item.confidence:.0%} confidence)")
    return problems


def _review(reason: str) -> RuleResult:
    return RuleResult(flag="NEEDS_REVIEW", days_in_custody=None, days_overdue=None, rule_fired=reason)


def implausible_dates(e: Extracted, today: date) -> str | None:
    """Catches date combinations that cannot describe a real detention. Without
    this, a misread year produced a negative or absurd custody figure and a
    confident flag derived from it."""
    if e.arrest_date > today:
        return (f"Arrest date {e.arrest_date.isoformat()} is in the future. "
                "The date was most likely misread; verify against the source document.")
    if e.release_date and e.release_date < e.arrest_date:
        return (f"Release date {e.release_date.isoformat()} precedes the arrest date "
                f"{e.arrest_date.isoformat()}. Verify both against the source document.")
    end_date = e.release_date or today
    if (end_date - e.arrest_date).days > MAX_PLAUSIBLE_CUSTODY_DAYS:
        return (f"Arrest date {e.arrest_date.isoformat()} implies over 100 years in custody. "
                "The year was most likely misread; verify against the source document.")
    return None


def evaluate(e: Extracted, statutes: dict[str, dict], today: date,
             confidence_threshold: float = CONFIDENCE_THRESHOLD) -> RuleResult:
    if not e.arrest_date or not e.sections:
        return _review("Missing arrest date or charged sections")

    unverified = unverified_facts(e, confidence_threshold)
    if unverified:
        return _review(
            f"Extraction confidence below {confidence_threshold:.0%} on a fact this decision "
            f"depends on: {'; '.join(unverified)}. Verify against the source document."
        )

    date_problem = implausible_dates(e, today)
    if date_problem:
        return _review(date_problem)

    resolved = {raw: normalize_section(raw) for raw in e.sections}
    unknown = [raw for raw, code in resolved.items() if code is None or code not in statutes]
    if unknown:
        return _review(f"Unknown section(s): {unknown}")

    codes = list(resolved.values())

    if any(statutes[s]["lifeOrDeath"] for s in codes):
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

    max_years = max(statutes[s]["maxYears"] for s in codes)
    # Rounded to whole days once, here, so the flag, the overdue figure and the
    # timeline the UI draws are all derived from the same integers.
    max_days = round(max_years * 365)
    half_days = round(max_days / 2)
    third_days = round(max_days / 3)
    thresholds = {"max_days": max_days, "half_days": half_days, "third_days": third_days}

    if days_in_custody >= max_days:
        return RuleResult(
            flag="PAST_MAX", days_in_custody=days_in_custody,
            days_overdue=days_in_custody - max_days,
            rule_fired=f"Served {days_in_custody}d, exceeds max sentence of {max_days}d",
            **thresholds,
        )

    if days_in_custody >= half_days:
        return RuleResult(
            flag="PAST_HALF", days_in_custody=days_in_custody,
            days_overdue=days_in_custody - half_days,
            rule_fired=f"Served over half the max sentence ({half_days}d)",
            **thresholds,
        )

    if e.first_time_offender and days_in_custody >= third_days:
        return RuleResult(
            flag="PAST_THIRD", days_in_custody=days_in_custody,
            days_overdue=days_in_custody - third_days,
            rule_fired=f"First-time offender past one-third threshold ({third_days}d)",
            **thresholds,
        )

    # Negative days_overdue reads as "days still to serve before eligibility".
    next_threshold = third_days if e.first_time_offender else half_days
    return RuleResult(
        flag="NOT_YET", days_in_custody=days_in_custody,
        days_overdue=days_in_custody - next_threshold,
        rule_fired=f"Below all thresholds; {next_threshold - days_in_custody}d until the "
                   f"{'one-third' if e.first_time_offender else 'half'} threshold",
        **thresholds,
    )
