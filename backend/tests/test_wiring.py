"""Covers the contract the frontend depends on: section spellings resolving to
statute keys, thresholds and evidence surviving the pipeline, and numbers
arriving in a shape DynamoDB and the browser both accept."""
import json
from datetime import date

import pytest

import statutes as statutes_module
from functions.rules.app import evaluate, normalize_section, lambda_handler as rules_handler
from functions.write_result.app import to_dynamo
from http_utils import respond, DecimalEncoder
from decimal import Decimal
from shared.schemas import Extracted, FLAG_TO_STATUS
from tests.helpers import confident_evidence

STATUTES = {
    "IPC#379": {"maxYears": 3, "lifeOrDeath": False},
    "BNS#303(2)": {"maxYears": 3, "lifeOrDeath": False},
    "IPC#302": {"maxYears": 0, "lifeOrDeath": True},
}


@pytest.fixture
def stub_statutes(monkeypatch):
    """load_statutes() scans DynamoDB. Seed its cache so the handler tests stay
    offline and deterministic."""
    monkeypatch.setattr(statutes_module, "_cache", STATUTES)
    yield


def make(**kw):
    defaults = dict(
        sections=["IPC#379"], arrest_date=date(2023, 1, 1), in_custody=True,
        evidence=confident_evidence(),
    )
    defaults.update(kw)
    return Extracted(**defaults)


@pytest.mark.parametrize("raw,expected", [
    ("IPC#379", "IPC#379"),
    ("BNS 303(2)", "BNS#303(2)"),
    ("bns#303(2)", "BNS#303(2)"),
    ("Section 379 IPC", "IPC#379"),
    ("379 of the IPC", "IPC#379"),
    ("IPC 506-II", "IPC#506-II"),
])
def test_normalize_section_spellings(raw, expected):
    assert normalize_section(raw) == expected


def test_normalize_section_rejects_junk():
    assert normalize_section("not a section") is None
    assert normalize_section("") is None


def test_frontend_section_spelling_resolves():
    """The UI used to hold codes like "BNS 303(2)", which never matched the
    statute table. They must now resolve rather than fall through to review."""
    result = evaluate(make(sections=["BNS 303(2)"]), STATUTES, today=date(2026, 1, 1))
    assert result.flag == "PAST_MAX"


def test_unknown_section_still_needs_review():
    result = evaluate(make(sections=["BNS 999"]), STATUTES, today=date(2026, 1, 1))
    assert result.flag == "NEEDS_REVIEW"


def test_thresholds_are_returned_for_the_timeline():
    result = evaluate(make(arrest_date=date(2025, 1, 1)), STATUTES, today=date(2026, 1, 1))
    assert result.max_days == 1095
    assert result.half_days == 548
    assert result.third_days == 365


def test_not_yet_reports_days_remaining_as_negative():
    result = evaluate(
        make(arrest_date=date(2026, 6, 1), first_time_offender=False),
        STATUTES, today=date(2026, 8, 1),
    )
    assert result.flag == "NOT_YET"
    assert result.days_overdue < 0


def test_every_flag_has_a_ui_status():
    for flag in ("PAST_MAX", "PAST_HALF", "PAST_THIRD", "NOT_ELIGIBLE", "NOT_YET", "NEEDS_REVIEW"):
        assert flag in FLAG_TO_STATUS


def test_rules_handler_carries_evidence_and_name_through(stub_statutes):
    event = {
        "caseId": "abc",
        "accused_name": "Rajesh Yadav",
        "sections": ["BNS 303(2)"],
        "arrest_date": "2019-01-01",
        "in_custody": True,
        "first_time_offender": True,
        "other_pending_cases": False,
        "evidence": {"arrest_date": {"value": "2019-01-01", "source_quote": "arrested on 1 Jan 2019", "confidence": 0.95}},
    }
    out = rules_handler(event, None)
    assert out["caseId"] == "abc"
    assert out["accused_name"] == "Rajesh Yadav"
    assert out["sections"] == ["BNS#303(2)"]
    assert out["evidence"]["arrest_date"]["source_quote"] == "arrested on 1 Jan 2019"
    assert out["first_time_offender"] is True


def test_rules_handler_forwards_a_failed_extraction():
    """extract/app.py hands over a pre-decided NEEDS_REVIEW when it cannot parse
    the document; validating that as Extracted would fail the whole case."""
    event = {"caseId": "abc", "flag": "NEEDS_REVIEW", "rule_fired": "could not parse", "evidence": {}}
    out = rules_handler(event, None)
    assert out["flag"] == "NEEDS_REVIEW"
    assert out["caseId"] == "abc"


def test_to_dynamo_converts_floats_for_storage():
    converted = to_dynamo({"evidence": {"arrest_date": {"confidence": 0.95}}, "days": 3})
    assert converted["evidence"]["arrest_date"]["confidence"] == Decimal("0.95")
    assert converted["days"] == 3


def test_respond_emits_numbers_the_browser_can_read():
    body = json.loads(respond(200, {"confidence": Decimal("0.95"), "days": Decimal("12")})["body"])
    assert body["confidence"] == 0.95
    assert body["days"] == 12


def test_respond_sets_cors_header():
    assert respond(200, {})["headers"]["Access-Control-Allow-Origin"] == "*"


def test_failed_textract_still_resolves_the_real_case_id():
    """The MarkFailed branch is entered with the raw EventBridge event. Writing
    to "unknown" there orphaned the real case in UPLOADED for ever."""
    from functions.write_result.app import resolve_case_id
    event = {"detail": {"object": {"key": "uploads/c1c6fa5a-8eff-4cd8-b2db-3ed821339577.pdf"}}}
    assert resolve_case_id(event) == "c1c6fa5a-8eff-4cd8-b2db-3ed821339577"


def test_case_id_in_the_event_wins():
    from functions.write_result.app import resolve_case_id
    assert resolve_case_id({"caseId": "abc", "detail": {"object": {"key": "uploads/zzz.txt"}}}) == "abc"


def test_unresolvable_case_id_is_none():
    from functions.write_result.app import resolve_case_id
    assert resolve_case_id({"detail": {"object": {"key": "somewhere/else.png"}}}) is None


def test_failure_reason_explains_a_missing_textract_subscription():
    from functions.write_result.app import failure_reason
    reason = failure_reason({"error": {"Cause": "ClientError: SubscriptionRequiredException ..."}})
    assert "Textract is not enabled" in reason
    assert ".txt" in reason


def test_failure_reason_falls_back_when_no_cause():
    from functions.write_result.app import failure_reason
    assert "Re-upload" in failure_reason({})


# --- confidence gate (shared/schemas.py promised this; it was never enforced) ---

def test_low_confidence_arrest_date_blocks_a_hard_flag():
    """A 20%-confidence arrest date used to produce PAST_MAX indistinguishable
    from a 99%-confidence one."""
    e = make(arrest_date=date(2019, 1, 1), evidence=confident_evidence(arrest_date=0.2))
    result = evaluate(e, STATUTES, today=date(2026, 1, 1))
    assert result.flag == "NEEDS_REVIEW"
    assert "arrest_date" in result.rule_fired
    assert "20%" in result.rule_fired


def test_confident_facts_still_decide_normally():
    e = make(arrest_date=date(2019, 1, 1), evidence=confident_evidence())
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "PAST_MAX"


def test_missing_evidence_entry_is_not_treated_as_verified():
    e = make(arrest_date=date(2019, 1, 1), evidence=confident_evidence(sections=None))
    result = evaluate(e, STATUTES, today=date(2026, 1, 1))
    assert result.flag == "NEEDS_REVIEW"
    assert "no supporting evidence" in result.rule_fired


def test_low_confidence_on_an_unused_fact_does_not_block():
    """accused_name never enters the decision, so a poor score on it must not
    stop an otherwise well-supported case from being flagged."""
    e = make(arrest_date=date(2019, 1, 1), evidence=confident_evidence(accused_name=0.1))
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "PAST_MAX"


def test_null_fact_needs_no_evidence():
    """other_pending_cases=None is handled conservatively already, so its
    absence from the evidence block is not a reason to review."""
    e = make(arrest_date=date(2019, 1, 1), other_pending_cases=None,
             evidence=confident_evidence(other_pending_cases=None))
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "PAST_MAX"


def test_low_confidence_on_a_bar_is_also_reviewed():
    """A shaky 'other cases pending' must not silently produce NOT_ELIGIBLE."""
    e = make(arrest_date=date(2019, 1, 1), other_pending_cases=True,
             evidence=confident_evidence(other_pending_cases=0.3))
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "NEEDS_REVIEW"


def test_threshold_is_configurable():
    e = make(arrest_date=date(2019, 1, 1), evidence=confident_evidence(arrest_date=0.5))
    assert evaluate(e, STATUTES, today=date(2026, 1, 1), confidence_threshold=0.4).flag == "PAST_MAX"
    assert evaluate(e, STATUTES, today=date(2026, 1, 1), confidence_threshold=0.9).flag == "NEEDS_REVIEW"


# --- retention (case rows previously had no expiry at all) ---

def test_expires_at_is_in_the_future_and_honours_the_window(monkeypatch):
    import retention
    monkeypatch.setenv("CASE_RETENTION_DAYS", "90")
    assert retention.expires_at(now=0) == 90 * 86400


def test_retention_window_is_configurable(monkeypatch):
    import retention
    monkeypatch.setenv("CASE_RETENTION_DAYS", "7")
    assert retention.expires_at(now=0) == 7 * 86400


def test_bad_retention_value_falls_back_to_the_default(monkeypatch):
    import retention
    monkeypatch.setenv("CASE_RETENTION_DAYS", "not-a-number")
    assert retention.expires_at(now=0) == retention.DEFAULT_RETENTION_DAYS * 86400
    monkeypatch.setenv("CASE_RETENTION_DAYS", "0")
    assert retention.expires_at(now=0) == retention.DEFAULT_RETENTION_DAYS * 86400


# --- date sanity (a misread year used to produce a confident flag) ---

def test_future_arrest_date_is_reviewed():
    e = make(arrest_date=date(2030, 1, 1))
    result = evaluate(e, STATUTES, today=date(2026, 1, 1))
    assert result.flag == "NEEDS_REVIEW"
    assert "future" in result.rule_fired


def test_release_before_arrest_is_reviewed():
    e = make(arrest_date=date(2024, 5, 1), release_date=date(2023, 1, 1))
    result = evaluate(e, STATUTES, today=date(2026, 1, 1))
    assert result.flag == "NEEDS_REVIEW"
    assert "precedes the arrest date" in result.rule_fired


def test_absurd_custody_span_is_reviewed():
    """A misread year (1019 for 2019) must not yield a confident PAST_MAX."""
    e = make(arrest_date=date(1019, 6, 14))
    result = evaluate(e, STATUTES, today=date(2026, 1, 1))
    assert result.flag == "NEEDS_REVIEW"
    assert "100 years" in result.rule_fired


def test_a_normal_long_detention_is_still_decided():
    e = make(arrest_date=date(2015, 1, 1))
    assert evaluate(e, STATUTES, today=date(2026, 1, 1)).flag == "PAST_MAX"


def test_custody_days_are_never_negative():
    for years_ago in (0, 1, 5):
        e = make(arrest_date=date(2026 - years_ago, 1, 1))
        result = evaluate(e, STATUTES, today=date(2026, 1, 1))
        assert result.days_in_custody is None or result.days_in_custody >= 0


# --- scheduled re-evaluation (flags used to be frozen at upload time) ---

def test_reevaluate_rebuilds_the_engine_input_from_a_stored_case():
    from functions.reevaluate.app import rebuild_extracted
    record = {
        "caseId": "abc", "accusedName": "Rajesh Yadav", "sections": ["IPC#379"],
        "arrestDate": "2019-01-01", "releaseDate": "", "inCustody": True,
        "firstTimeOffender": True, "otherPendingCases": False,
        "evidence": {"arrest_date": {"value": "2019-01-01", "source_quote": "q", "confidence": Decimal("0.95")},
                     "sections": {"value": "IPC#379", "source_quote": "q", "confidence": Decimal("0.95")},
                     "first_time_offender": {"value": "true", "source_quote": "q", "confidence": Decimal("0.95")},
                     "other_pending_cases": {"value": "false", "source_quote": "q", "confidence": Decimal("0.95")}},
    }
    e = rebuild_extracted(record)
    assert e is not None
    assert e.sections == ["IPC#379"]
    assert e.arrest_date == date(2019, 1, 1)
    assert e.release_date is None
    assert e.evidence["arrest_date"].confidence == 0.95


def test_reevaluate_skips_records_with_no_evidence():
    """Pre-evidence records cannot be re-checked against the confidence gate,
    so they are left alone rather than silently re-flagged."""
    from functions.reevaluate.app import rebuild_extracted
    assert rebuild_extracted({"caseId": "old", "sections": ["IPC#379"], "arrestDate": "2019-01-01"}) is None


def test_reevaluate_escalates_a_case_as_time_passes():
    """The bug this fixes: a case below every threshold stayed NOT_YET for ever."""
    from functions.reevaluate.app import rebuild_extracted
    record = {
        "caseId": "abc", "sections": ["IPC#379"], "arrestDate": "2025-01-01",
        "inCustody": True, "firstTimeOffender": False, "otherPendingCases": False,
        "evidence": {n: {"value": n, "source_quote": "q", "confidence": Decimal("0.95")}
                     for n in ("sections", "arrest_date", "first_time_offender", "other_pending_cases")},
    }
    e = rebuild_extracted(record)
    assert evaluate(e, STATUTES, today=date(2025, 6, 1)).flag == "NOT_YET"
    assert evaluate(e, STATUTES, today=date(2026, 9, 1)).flag == "PAST_HALF"
    assert evaluate(e, STATUTES, today=date(2028, 6, 1)).flag == "PAST_MAX"


def test_reevaluate_only_revisits_flags_that_can_move():
    from functions.reevaluate.app import OPEN_FLAGS
    assert OPEN_FLAGS == {"NOT_YET", "PAST_THIRD", "PAST_HALF"}
    for terminal in ("PAST_MAX", "NOT_ELIGIBLE", "NEEDS_REVIEW"):
        assert terminal not in OPEN_FLAGS


# --- pagination (a single scan silently stopped at 1MB) ---

def test_query_limit_is_clamped():
    from functions.query.app import parse_limit, DEFAULT_LIMIT, MAX_LIMIT
    assert parse_limit({}) == DEFAULT_LIMIT
    assert parse_limit({"limit": "10"}) == 10
    assert parse_limit({"limit": "99999"}) == MAX_LIMIT
    assert parse_limit({"limit": "0"}) == 1
    assert parse_limit({"limit": "nonsense"}) == DEFAULT_LIMIT


def test_query_follows_pages_until_the_limit():
    from functions.query.app import collect

    class FakeTable:
        def __init__(self): self.calls = 0
        def scan(self, **kw):
            self.calls += 1
            if self.calls < 3:
                return {"Items": [{"caseId": f"c{self.calls}-{i}"} for i in range(2)],
                        "LastEvaluatedKey": {"caseId": "next"}}
            return {"Items": [{"caseId": "last"}]}

    table = FakeTable()
    assert len(collect(table, limit=100)) == 5
    assert table.calls == 3

    table2 = FakeTable()
    assert len(collect(table2, limit=3)) == 3


# --- document routing: the text path must never depend on Textract ---

def _client_error(code):
    from botocore.exceptions import ClientError
    return ClientError({"Error": {"Code": code, "Message": code}}, "StartDocumentTextDetection")


def test_plain_text_is_read_without_textract():
    from functions.textract_extract.app import decode_if_text
    body = "The accused was arrested on 15 January 2024 under BNS Section 303(2).".encode()
    assert decode_if_text(body) is not None


def test_a_pdf_is_never_mistaken_for_text():
    from functions.textract_extract.app import decode_if_text
    assert decode_if_text(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n") is None


def test_binary_is_not_mistaken_for_text():
    from functions.textract_extract.app import decode_if_text
    assert decode_if_text(bytes(range(256)) * 4) is None
    assert decode_if_text(b"text with a \x00 null byte in it") is None


def test_text_file_named_pdf_still_takes_the_text_route():
    """The uploader's extension is not trusted: routing is by content, so this
    works even while Textract is unavailable."""
    from functions.textract_extract.app import decode_if_text
    assert decode_if_text("Arrested on 3 March 2020 under IPC#379.".encode()) is not None


def test_utf8_bom_and_accents_survive():
    from functions.textract_extract.app import decode_if_text
    assert decode_if_text("﻿Accused: Farhan Sheikh — arrested 2019".encode("utf-8")) \
        .startswith("Accused")


def test_empty_upload_is_not_treated_as_text():
    from functions.textract_extract.app import decode_if_text
    assert decode_if_text(b"") is None
    assert decode_if_text(b"   \n\t  ") is None


def test_missing_textract_subscription_is_explained_not_retried():
    from functions.textract_extract.app import classify, DocumentUnreadable
    result = classify(_client_error("SubscriptionRequiredException"), "StartDocumentTextDetection")
    assert isinstance(result, DocumentUnreadable)
    assert ".txt" in str(result)
    assert "not available to this AWS account" in str(result)


def test_a_broken_document_is_reported_as_a_document_problem():
    from functions.textract_extract.app import classify, DocumentUnreadable
    result = classify(_client_error("UnsupportedDocumentException"), "StartDocumentTextDetection")
    assert isinstance(result, DocumentUnreadable)
    assert "could not read this document" in str(result)


def test_an_unknown_textract_error_is_not_dressed_up():
    from functions.textract_extract.app import classify, DocumentUnreadable
    result = classify(_client_error("SomethingNewException"), "StartDocumentTextDetection")
    assert not isinstance(result, DocumentUnreadable)


def test_throttling_is_retried_then_surfaces():
    from functions.textract_extract import app as textract_app
    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _client_error("ThrottlingException")
        return {"JobId": "ok"}

    textract_app.RETRY_BACKOFF = (0, 0, 0)
    assert textract_app.call_with_retry(flaky)["JobId"] == "ok"
    assert calls["n"] == 3


def test_a_subscription_error_is_not_retried():
    from functions.textract_extract import app as textract_app
    calls = {"n": 0}

    def always(**kwargs):
        calls["n"] += 1
        raise _client_error("SubscriptionRequiredException")

    textract_app.RETRY_BACKOFF = (0, 0, 0)
    try:
        textract_app.call_with_retry(always)
        raise AssertionError("should have raised")
    except textract_app.DocumentUnreadable:
        pass
    assert calls["n"] == 1, "retrying a missing subscription wastes the Lambda timeout"


def test_case_id_resolves_for_any_extension():
    """A .txt or .pdf was fine, anything else was orphaned in UPLOADED."""
    from functions.textract_extract.app import KEY_PATTERN
    from functions.write_result.app import resolve_case_id
    for ext in ("txt", "pdf", "md", "TIFF", "png"):
        key = f"uploads/c1c6fa5a-8eff-4cd8-b2db-3ed821339577.{ext}"
        assert KEY_PATTERN.search(key).group(1) == "c1c6fa5a-8eff-4cd8-b2db-3ed821339577"
        assert resolve_case_id({"detail": {"object": {"key": key}}}) == "c1c6fa5a-8eff-4cd8-b2db-3ed821339577"


def test_failure_reason_uses_the_handlers_own_wording():
    """A Lambda failure arrives as JSON, so the exact message is recoverable."""
    from functions.write_result.app import failure_reason
    cause = json.dumps({
        "errorType": "DocumentUnreadable",
        "errorMessage": "This looks like a scanned PDF ... Upload the case as a .txt file instead.",
        "trace": ["..."],
    })
    assert failure_reason({"error": {"Cause": cause}}).endswith(".txt file instead.")


def test_failure_reason_still_handles_a_bare_stack_trace():
    from functions.write_result.app import failure_reason
    reason = failure_reason({"error": {"Cause": "ClientError: SubscriptionRequiredException ..."}})
    assert "Textract is not enabled" in reason
