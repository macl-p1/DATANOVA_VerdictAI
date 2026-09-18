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
    sections: list[str]                    # e.g. ["IPC#379", "BNS#303"]
    arrest_date: date | None
    in_custody: bool
    release_date: date | None              # None if still in custody
    first_time_offender: bool | None
    other_pending_cases: bool | None
    evidence: dict[str, Field]             # field name -> Field, for the UI


Flag = Literal[
    "PAST_MAX",       # in custody longer than the max possible sentence
    "PAST_HALF",      # past the half-sentence threshold
    "PAST_THIRD",     # first-time offender, past one-third
    "NOT_ELIGIBLE",   # life/death offence, or other cases pending
    "NOT_YET",        # below every threshold
    "NEEDS_REVIEW",   # missing data, unknown section, or low confidence
]


class RuleResult(BaseModel):
    """What the rules Lambda returns. Nothing here comes from an LLM —
    every field is computed by evaluate() in functions/rules/app.py."""
    flag: Flag
    days_in_custody: int | None
    days_overdue: int | None
    rule_fired: str          # human-readable reason, shown in the UI and demo video