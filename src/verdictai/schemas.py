"""Contracts separating extracted evidence from deterministic legal results."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Page(BaseModel):
    page: int = Field(ge=1)
    text: str


class AnnotationEntity(BaseModel):
    type: str
    text: str
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, end: int, info):
        if "start" in info.data and end <= info.data["start"]:
            raise ValueError("end must be greater than start")
        return end


class LegalDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(min_length=1)
    language: str = Field(default="en", min_length=2)
    pages: list[Page] = Field(min_length=1)
    entities: list[AnnotationEntity] = Field(default_factory=list)
    source_type: Literal["public", "synthetic", "human_annotated", "unknown"] = "unknown"
    annotator_id: str | None = None
    annotation_version: str | None = None
    review_status: Literal["unreviewed", "reviewed", "approved", "rejected"] = "unreviewed"
    case_group_id: str | None = None


class Evidence(BaseModel):
    document_id: str
    text: str
    page: int | None = Field(default=None, ge=1)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedEntity(BaseModel):
    type: str
    value: str
    normalized_value: str | None = None
    evidence: Evidence


class ExtractionResult(BaseModel):
    document_id: str
    entities: list[ExtractedEntity] = Field(default_factory=list)
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)


class RuleResult(BaseModel):
    """A deterministic result, deliberately not a model output."""
    flag: Literal["PAST_MAX", "PAST_HALF", "PAST_THIRD", "NOT_ELIGIBLE", "NOT_YET", "NEEDS_REVIEW"]
    days_in_custody: int | None = None
    days_overdue: int | None = None
    rule_fired: str
