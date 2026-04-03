from __future__ import annotations

from shared.models import (
    ApplicationRecord,
    CVDocument,
    FitAnalysis,
    JobDescription,
    LinkedInMessageResult,
    RewriteSuggestion,
    ScoreBreakdown,
    SectionContent,
    SkillEvidence,
    SkillsSubsection,
)


def section_from_dict(data: dict) -> SectionContent:
    return SectionContent(
        heading=data.get("heading", ""),
        text=data.get("text", ""),
        bullets=data.get("bullets", []),
        order=data.get("order", 0),
        source_span=tuple(data["source_span"]) if data.get("source_span") else None,
    )


def cv_document_from_dict(data: dict) -> CVDocument:
    return CVDocument(
        raw_text=data.get("raw_text", ""),
        summary=section_from_dict(data.get("summary", {})),
        experience=section_from_dict(data.get("experience", {})),
        education=section_from_dict(data.get("education", {})),
        projects=section_from_dict(data.get("projects", {})),
        skills=section_from_dict(data.get("skills", {})),
        certifications=section_from_dict(data.get("certifications", {})),
        publications=section_from_dict(data.get("publications", {})),
        technologies=[SkillEvidence(**item) for item in data.get("technologies", [])],
        skills_subsections=[SkillsSubsection(**item) for item in data.get("skills_subsections", [])],
        metrics=data.get("metrics", []),
        editable_sections=data.get("editable_sections", []),
        locked_sections=data.get("locked_sections", []),
    )


def job_description_from_dict(data: dict) -> JobDescription:
    return JobDescription(**data)


def fit_analysis_from_dict(data: dict) -> FitAnalysis:
    breakdown = ScoreBreakdown(**data["score_breakdown"])
    return FitAnalysis(
        overall_fit_score=data["overall_fit_score"],
        estimated_ats_score=data["estimated_ats_score"],
        score_breakdown=breakdown,
        missing_keywords=data.get("missing_keywords", []),
        strong_sections=data.get("strong_sections", []),
        weak_sections=data.get("weak_sections", []),
        supported_facts=data.get("supported_facts", []),
        inferred_alignment=data.get("inferred_alignment", []),
        missing_requirements=data.get("missing_requirements", []),
        editable_recommendations=data.get("editable_recommendations", {}),
        section_evidence=data.get("section_evidence", {}),
    )


def rewrite_suggestion_from_dict(data: dict) -> RewriteSuggestion:
    return RewriteSuggestion(**data)


def linkedin_message_from_dict(data: dict) -> LinkedInMessageResult:
    return LinkedInMessageResult(**data)


def application_record_from_dict(data: dict) -> ApplicationRecord:
    return ApplicationRecord(
        application_id=data["application_id"],
        cv_document=cv_document_from_dict(data["cv_document"]),
        job_description=job_description_from_dict(data["job_description"]),
        fit_analysis=fit_analysis_from_dict(data["fit_analysis"]),
        rewrite_suggestion=rewrite_suggestion_from_dict(data["rewrite_suggestion"]),
        linkedin_message=linkedin_message_from_dict(data["linkedin_message"]),
    )
