from datetime import date
from typing import Literal
from pydantic import BaseModel


class Field(BaseModel):
    """One extracted fact, always paired with proof of where it came from.
    Every value the LLM extracts must carry this so the UI can show
    the source quote next to the fact, and so low-confidence fields
    can trigger NEEDS_REVIEW instead of a silent wrong answer."""
    value: str | None
    source_quote: str | None
    confidence: float


class Extracted(BaseModel):
    """What the extract Lambda returns after Bedrock reads a document.
    This is the ONLY thing the rule engine is allowed to look at —
    it never sees the raw document or talks to Bedrock itself."""
    sections: list[str]                    # e.g. ["IPC#379", "BNS#303(2)"]
    arrest_date: date | None
    in_custody: bool
    evidence: dict[str, Field]             # field name -> Field, for the UI
    # Optional facts. A terse model response that omits these should still
    # parse — the rule engine already treats a missing fact conservatively —
    # rather than failing the whole extraction.
    accused_name: str | None = None        # shown in the register; null if the document never names them
    release_date: date | None = None       # None if still in custody
    first_time_offender: bool | None = None
    other_pending_cases: bool | None = None


Flag = Literal[
    "PAST_MAX",       # in custody longer than the max possible sentence
    "PAST_HALF",      # past the half-sentence threshold
    "PAST_THIRD",     # first-time offender, past one-third
    "NOT_ELIGIBLE",   # life/death offence, or other cases pending
    "NOT_YET",        # below every threshold
    "NEEDS_REVIEW",   # missing data, unknown section, or low confidence
]

# The UI paints one colour per flag. Kept here, beside the Flag definition,
# so a new flag cannot be added without deciding how it renders.
FLAG_TO_STATUS: dict[str, str] = {
    "PAST_MAX": "red",
    "PAST_HALF": "amber",
    "PAST_THIRD": "yellow",
    "NOT_ELIGIBLE": "barred",
    "NOT_YET": "gray",
    "NEEDS_REVIEW": "review",
}


class RuleResult(BaseModel):
    """What the rules Lambda returns. Nothing here comes from an LLM —
    every field is computed by evaluate() in functions/rules/app.py."""
    flag: Flag
    days_in_custody: int | None
    days_overdue: int | None
    rule_fired: str          # human-readable reason, shown in the UI and demo video
    # Thresholds are returned so the UI can draw the custody timeline without
    # re-deriving them from a statute table it should not have a copy of.
    max_days: int | None = None
    half_days: int | None = None
    third_days: int | None = None
