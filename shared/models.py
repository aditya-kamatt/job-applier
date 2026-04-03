from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


EDITABLE_SECTIONS = ("summary", "skills")
LOCKED_SECTIONS = (
    "experience",
    "education",
    "projects",
    "certifications",
    "publications",
)


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: dataclass_to_dict(item) for key, item in value.items()}
    return value


@dataclass(slots=True)
class SectionContent:
    heading: str
    text: str = ""
    bullets: list[str] = field(default_factory=list)
    order: int = 0
    source_span: tuple[int, int] | None = None


@dataclass(slots=True)
class SkillEvidence:
    skill: str
    evidence: list[str] = field(default_factory=list)
    supported: bool = True


@dataclass(slots=True)
class SkillsSubsection:
    heading: str
    tools: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CVDocument:
    raw_text: str
    summary: SectionContent = field(default_factory=lambda: SectionContent(heading="Summary"))
    experience: SectionContent = field(default_factory=lambda: SectionContent(heading="Experience"))
    education: SectionContent = field(default_factory=lambda: SectionContent(heading="Education"))
    projects: SectionContent = field(default_factory=lambda: SectionContent(heading="Projects"))
    skills: SectionContent = field(default_factory=lambda: SectionContent(heading="Skills"))
    certifications: SectionContent = field(default_factory=lambda: SectionContent(heading="Certifications"))
    publications: SectionContent = field(default_factory=lambda: SectionContent(heading="Publications"))
    technologies: list[SkillEvidence] = field(default_factory=list)
    skills_subsections: list[SkillsSubsection] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    editable_sections: list[str] = field(default_factory=lambda: list(EDITABLE_SECTIONS))
    locked_sections: list[str] = field(default_factory=lambda: list(LOCKED_SECTIONS))


@dataclass(slots=True)
class JobDescription:
    raw_text: str
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    tools_frameworks: list[str] = field(default_factory=list)
    domain_keywords: list[str] = field(default_factory=list)
    soft_skills: list[str] = field(default_factory=list)
    seniority_indicators: list[str] = field(default_factory=list)
    job_title: str | None = None
    company_name: str | None = None
    seniority_level: str | None = None


@dataclass(slots=True)
class ScoreBreakdown:
    skill_match: int
    experience_relevance: int
    project_relevance: int
    keyword_coverage: int
    seniority_fit: int


@dataclass(slots=True)
class FitAnalysis:
    overall_fit_score: int
    estimated_ats_score: int
    score_breakdown: ScoreBreakdown
    missing_keywords: list[str]
    strong_sections: list[str]
    weak_sections: list[str]
    supported_facts: list[str]
    inferred_alignment: list[str]
    missing_requirements: list[str]
    editable_recommendations: dict[str, list[str]]
    section_evidence: dict[str, list[str]]


@dataclass(slots=True)
class RewriteSuggestion:
    rewritten_summary: str
    suggested_skills_section: dict[str, list[str]]
    skills_change_message: str | None
    missing_but_not_inserted: list[str]
    improved_ats_estimate: int
    evidence_map: dict[str, list[str]]
    used_llm: bool = False
    fallback_reason: str | None = None
    editable_sections: list[str] = field(default_factory=lambda: list(EDITABLE_SECTIONS))
    locked_sections: list[str] = field(default_factory=lambda: list(LOCKED_SECTIONS))


@dataclass(slots=True)
class LinkedInMessageResult:
    hiring_manager_message: str
    personalization_evidence: list[str]
    used_llm: bool = False
    fallback_reason: str | None = None
    tone: str = "professional"
    max_length_words: int = 150


@dataclass(slots=True)
class ApplicationRecord:
    application_id: str
    cv_document: CVDocument
    job_description: JobDescription
    fit_analysis: FitAnalysis
    rewrite_suggestion: RewriteSuggestion
    linkedin_message: LinkedInMessageResult


@dataclass(slots=True)
class AnalyzeRequest:
    cv_text: str
    job_description_text: str
    job_title: str | None = None
    company_name: str | None = None
    seniority_level: str | None = None


@dataclass(slots=True)
class ParseCVRequest:
    cv_text: str


@dataclass(slots=True)
class ParseJDRequest:
    job_description_text: str
    job_title: str | None = None
    company_name: str | None = None
    seniority_level: str | None = None


@dataclass(slots=True)
class RewriteRequest:
    cv_document: CVDocument
    job_description: JobDescription
    fit_analysis: FitAnalysis


@dataclass(slots=True)
class MessageRequest:
    cv_document: CVDocument
    job_description: JobDescription
    fit_analysis: FitAnalysis
