"""Optional FastAPI adapter; it exposes extraction only."""
from __future__ import annotations
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl

from verdictai.schemas import ExtractionResult


class PredictRequest(BaseModel):
    document_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class PublicCaseReviewRequest(PredictRequest):
    case_title: str = Field(min_length=1, max_length=300)
    source_url: HttpUrl | None = None
    source_label: str = Field(default="Pasted text", min_length=1, max_length=300)


class PublicCaseReviewResponse(BaseModel):
    case_title: str
    source_url: HttpUrl | None = None
    source_label: str
    extraction: ExtractionResult
    factual_summary: list[str]
    review_guidance: list[str]
    disclaimer: str


def create_app(model_path: str, confidence_threshold: float = 0.70):
    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from transformers import AutoModelForTokenClassification, AutoTokenizer
    from verdictai.inference.pipeline import predict_text
    model_directory = Path(model_path)
    if not model_directory.is_dir():
        raise FileNotFoundError(
            f"Local model directory not found: {model_directory}. "
            "Train a model first, or pass an existing local checkpoint directory."
        )
    tokenizer = AutoTokenizer.from_pretrained(str(model_directory))
    model = AutoModelForTokenClassification.from_pretrained(str(model_directory))
    app = FastAPI(title="VerdictAI Extraction API")
    static_directory = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_directory), name="static")

    @app.get("/")
    def interface():
        return FileResponse(static_directory / "index.html")

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "VerdictAI Extraction API",
            "docs": "/docs",
            "interface": "/",
            "predict_endpoint": "POST /predict",
        }

    @app.post("/predict")
    def predict(request: PredictRequest):
        return predict_text(model, tokenizer, request.text, request.document_id, confidence_threshold).model_dump()

    @app.post("/review-public-case", response_model=PublicCaseReviewResponse)
    def review_public_case(request: PublicCaseReviewRequest):
        """Produce a source-linked evidence review, never a legal conclusion."""
        extraction = predict_text(model, tokenizer, request.text, request.document_id, confidence_threshold)
        summary = [
            f"{entity.type}: {entity.normalized_value or entity.value}"
            for entity in extraction.entities
        ]
        guidance = list(extraction.review_reasons)
        if not summary:
            guidance.append("No configured facts were extracted; compare the source text with the original public record.")
        guidance.append("Verify all extracted text, source offsets, and statutory references against the linked public record.")
        return PublicCaseReviewResponse(
            case_title=request.case_title,
            source_url=request.source_url,
            source_label=request.source_label,
            extraction=extraction,
            factual_summary=summary,
            review_guidance=guidance,
            disclaimer=(
                "This is an evidence-extraction review only. It does not determine guilt, innocence, "
                "liability, punishment, fines, bail, or any legal outcome."
            ),
        )
    return app
