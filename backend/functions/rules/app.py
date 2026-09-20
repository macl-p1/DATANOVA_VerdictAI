"""Evaluates a freshly extracted case against Section 479 BNSS.

The engine itself lives in the shared layer (rules_engine.py) because the
scheduled reevaluate Lambda runs the same logic. This module is only the
pipeline adapter: it loads statutes, calls evaluate(), and shapes the result
for the next step.
"""
from datetime import date

from schemas import Extracted
from statutes import load_statutes
# Re-exported so tests and the reevaluate Lambda have one import site.
from rules_engine import (  # noqa: F401
    evaluate, normalize_section, unverified_facts, implausible_dates, CONFIDENCE_THRESHOLD,
)


def lambda_handler(event, context):
    case_id = event.pop("caseId", None)

    # extract/app.py hands us a pre-decided result when it could not parse the
    # document. Forward it untouched so the reason reaches the UI instead of
    # blowing up validation and marking the whole case FAILED.
    if "flag" in event:
        event["caseId"] = case_id
        return event

    extracted = Extracted(**event)

    result = evaluate(extracted, load_statutes(), today=date.today())
    output = result.model_dump(mode="json")
    output["caseId"] = case_id
    # Everything the UI needs to render the case, carried through the pipeline.
    # The rule engine does not use these, but dropping them here is what
    # previously left the case record without names, evidence or source quotes.
    output["accused_name"] = extracted.accused_name
    output["arrest_date"] = extracted.arrest_date.isoformat() if extracted.arrest_date else None
    output["release_date"] = extracted.release_date.isoformat() if extracted.release_date else None
    output["in_custody"] = extracted.in_custody
    output["first_time_offender"] = extracted.first_time_offender
    output["other_pending_cases"] = extracted.other_pending_cases
    output["sections"] = [normalize_section(s) or s for s in extracted.sections]
    output["evidence"] = {k: v.model_dump(mode="json") for k, v in extracted.evidence.items()}
    return output
