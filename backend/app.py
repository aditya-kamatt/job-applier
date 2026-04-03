from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException

from shared.models import AnalyzeRequest, MessageRequest, ParseCVRequest, ParseJDRequest, RewriteRequest

from .pipeline import ApplyAIPipeline

app = FastAPI(title="ApplyAI API", version="0.1.0")
pipeline = ApplyAIPipeline()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse/cv")
def parse_cv_endpoint(request: AnalyzeRequest | ParseCVRequest):
    cv_text = request.cv_text
    return asdict(pipeline.parse_cv(ParseCVRequest(cv_text=cv_text)))


@app.post("/parse/jd")
def parse_jd_endpoint(request: AnalyzeRequest | ParseJDRequest):
    if isinstance(request, AnalyzeRequest):
        job_description_text = request.job_description_text
        job_title = request.job_title
        company_name = request.company_name
        seniority_level = request.seniority_level
    else:
        job_description_text = request.job_description_text
        job_title = request.job_title
        company_name = request.company_name
        seniority_level = request.seniority_level
    return asdict(
        pipeline.parse_jd(
            ParseJDRequest(
                job_description_text=job_description_text,
                job_title=job_title,
                company_name=company_name,
                seniority_level=seniority_level,
            )
        )
    )


@app.post("/analyze")
def analyze_endpoint(request: AnalyzeRequest):
    return pipeline.analyze(request)


@app.post("/rewrite")
def rewrite_endpoint(request: RewriteRequest):
    return asdict(pipeline.rewrite(request))


@app.post("/linkedin-message")
def linkedin_message_endpoint(request: MessageRequest):
    return asdict(pipeline.linkedin_message(request))


@app.get("/applications/{application_id}")
def get_application_endpoint(application_id: str):
    record = pipeline.get_application(application_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    return asdict(record)
