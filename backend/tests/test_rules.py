from datetime import date
from functions.rules.app import evaluate
from shared.schemas import Extracted

STATUTES = {
    "IPC#379": {"maxYears": 3, "lifeOrDeath": False},   # theft
    "IPC#302": {"maxYears": 0, "lifeOrDeath": True},    # murder
}

def make(**kw):
    defaults = dict(
        sections=["IPC#379"], arrest_date=date(2023, 1, 1), in_custody=True,
        release_date=None, first_time_offender=True, other_pending_cases=False,
        evidence={}
    )
    defaults.update(kw)
    return Extracted(**defaults)

def test_past_max():
    e = make(arrest_date=date(2019, 1, 1))
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "PAST_MAX"

def test_past_half():
    e = make(arrest_date=date(2024, 6, 1), first_time_offender=False)
    r = evaluate(e, STATUTES, today=date(2026, 1, 1))
    assert r.flag in ("PAST_HALF", "PAST_MAX")

def test_first_time_offender_past_third():
    e = make(arrest_date=date(2025, 1, 1), first_time_offender=True)
    r = evaluate(e, STATUTES, today=date(2026, 5, 1))
    assert r.flag in ("PAST_THIRD", "PAST_HALF", "PAST_MAX")

def test_not_eligible_life_sentence():
    e = make(sections=["IPC#302"], arrest_date=date(2019, 1, 1))
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "NOT_ELIGIBLE"

def test_not_eligible_other_pending_case():
    e = make(other_pending_cases=True, arrest_date=date(2019, 1, 1))
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "NOT_ELIGIBLE"

def test_needs_review_missing_date():
    e = make(arrest_date=None)
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "NEEDS_REVIEW"

def test_needs_review_unknown_section():
    e = make(sections=["IPC#999"])
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "NEEDS_REVIEW"

def test_not_yet():
    e = make(arrest_date=date(2026, 6, 1))
    assert evaluate(e, STATUTES, today=date(2026, 8, 1)).flag == "NOT_YET"