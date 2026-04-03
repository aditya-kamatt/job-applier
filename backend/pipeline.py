from __future__ import annotations

from dataclasses import asdict

from shared.models import (
    AnalyzeRequest,
    MessageRequest,
    ParseCVRequest,
    ParseJDRequest,
    RewriteRequest,
)

from .messaging import generate_linkedin_messages
from .parsers import parse_cv, parse_job_description
from .rewrite import generate_rewrite
from .scoring import analyze_fit
from .storage import ApplicationRepository


class ApplyAIPipeline:
    def __init__(self, repository: ApplicationRepository | None = None) -> None:
        self.repository = repository or ApplicationRepository()

    def parse_cv(self, request: ParseCVRequest):
        return parse_cv(request.cv_text)

    def parse_jd(self, request: ParseJDRequest):
        return parse_job_description(
            request.job_description_text,
            request.job_title,
            request.company_name,
            request.seniority_level,
        )

    def analyze(self, request: AnalyzeRequest) -> dict:
        cv_document = parse_cv(request.cv_text)
        job_description = parse_job_description(
            request.job_description_text,
            request.job_title,
            request.company_name,
            request.seniority_level,
        )
        fit_analysis = analyze_fit(cv_document, job_description)
        rewrite_suggestion = generate_rewrite(cv_document, job_description, fit_analysis)
        linkedin_message = generate_linkedin_messages(cv_document, job_description, fit_analysis)
        record = self.repository.save(
            cv_document=cv_document,
            job_description=job_description,
            fit_analysis=fit_analysis,
            rewrite_suggestion=rewrite_suggestion,
            linkedin_message=linkedin_message,
        )
        return {
            "application_id": record.application_id,
            "cv_document": asdict(cv_document),
            "job_description": asdict(job_description),
            "fit_analysis": asdict(fit_analysis),
            "rewrite_suggestion": asdict(rewrite_suggestion),
            "linkedin_message": asdict(linkedin_message),
        }

    def rewrite(self, request: RewriteRequest):
        return generate_rewrite(request.cv_document, request.job_description, request.fit_analysis)

    def linkedin_message(self, request: MessageRequest):
        return generate_linkedin_messages(request.cv_document, request.job_description, request.fit_analysis)

    def get_application(self, application_id: str):
        return self.repository.get(application_id)
