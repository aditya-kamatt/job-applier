from __future__ import annotations

from dataclasses import dataclass

from shared.models import CVDocument, FitAnalysis, JobDescription, RewriteSuggestion

from .gemini_client import GeminiRewriteClient, GeminiRewriteError
from .text_utils import CANONICAL_TECH_TERMS, display_label_for_term


@dataclass(slots=True)
class RewriteEvidence:
    allowed_summary_facts: list[str]
    supported_skills_by_subsection: dict[str, list[str]]
    missing_skills_not_allowed: list[str]
    locked_sections: list[str]


def _original_skills_by_subsection(cv_document: CVDocument) -> dict[str, list[str]]:
    return {subsection.heading: list(subsection.tools) for subsection in cv_document.skills_subsections}


def _build_supported_skill_inventory(cv_document: CVDocument) -> set[str]:
    supported = {skill.skill.lower() for skill in cv_document.technologies if skill.supported}
    for subsection in cv_document.skills_subsections:
        for tool in subsection.tools:
            supported.add(tool.lower())
    return supported


def _sentence_case(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


def _prepare_rewrite_evidence(
    cv_document: CVDocument,
    job_description: JobDescription,
    fit_analysis: FitAnalysis,
) -> RewriteEvidence:
    supported_skills = _build_supported_skill_inventory(cv_document)
    by_subsection: dict[str, list[str]] = {}
    for subsection in cv_document.skills_subsections:
        filtered_tools = [tool for tool in subsection.tools if tool.lower() in supported_skills]
        by_subsection[subsection.heading] = filtered_tools
    return RewriteEvidence(
        allowed_summary_facts=fit_analysis.supported_facts[:10],
        supported_skills_by_subsection=by_subsection,
        missing_skills_not_allowed=fit_analysis.missing_keywords[:10],
        locked_sections=cv_document.locked_sections,
    )


def _deterministic_rewrite(
    cv_document: CVDocument,
    job_description: JobDescription,
    fit_analysis: FitAnalysis,
    evidence: RewriteEvidence,
    fallback_reason: str | None = None,
) -> RewriteSuggestion:
    supported_skills = _build_supported_skill_inventory(cv_document)
    jd_focus = [
        display_label_for_term(skill)
        for skill in job_description.required_skills + job_description.tools_frameworks
        if any(
            variant in supported_skills
            for variant in CANONICAL_TECH_TERMS.get(skill.lower(), {skill.lower()})
        ) or skill.lower() in supported_skills
    ]
    jd_focus = list(dict.fromkeys(jd_focus))[:5]

    base_summary_parts = []
    if cv_document.summary.text:
        base_summary_parts.append(cv_document.summary.text.strip().rstrip("."))
    else:
        base_summary_parts.append("Engineer with hands-on experience relevant to the target role")

    if jd_focus:
        summary_focus = ", ".join(jd_focus[:3])
        base_summary_parts.append(
            f"My background aligns well with work involving {summary_focus}"
        )

    if cv_document.experience.bullets:
        base_summary_parts.append(
            f"My recent experience includes {cv_document.experience.bullets[0].rstrip('.')}"
        )

    rewritten_summary = ". ".join(_sentence_case(part.strip()) for part in base_summary_parts if part.strip()) + "."

    suggested_skills: dict[str, list[str]] = {}
    original_skills = _original_skills_by_subsection(cv_document)
    for heading, tools in evidence.supported_skills_by_subsection.items():
        prioritized = [tool for tool in tools if tool.lower() in {item.lower() for item in jd_focus}]
        remaining = [tool for tool in tools if tool.lower() not in {item.lower() for item in prioritized}]
        reordered = prioritized + remaining
        if reordered != original_skills.get(heading, []):
            suggested_skills[heading] = reordered
    skills_change_message = None
    if not suggested_skills:
        skills_change_message = "No changes required in the Skills section."
    evidence_map = {
        "rewritten_summary": fit_analysis.supported_facts[:8] or ["Grounded in parsed CV sections only."],
        "suggested_skills_section": [
            "Only changed subsections are returned for the Skills section.",
            "Only supported skills extracted from the CV are eligible for reordering.",
            "Missing JD keywords are listed separately and are not inserted into the skills section.",
        ],
    }
    improved_ats = min(100, fit_analysis.estimated_ats_score + (5 if jd_focus else 0))
    return RewriteSuggestion(
        rewritten_summary=rewritten_summary,
        suggested_skills_section=suggested_skills,
        skills_change_message=skills_change_message,
        missing_but_not_inserted=evidence.missing_skills_not_allowed,
        improved_ats_estimate=improved_ats,
        evidence_map=evidence_map,
        used_llm=False,
        fallback_reason=fallback_reason,
    )


def _build_llm_prompt(
    cv_document: CVDocument,
    job_description: JobDescription,
    evidence: RewriteEvidence,
) -> str:
    return f"""
You are rewriting only the Summary and Skills sections of a CV.

Rules:
- Rewrite only the summary.
- For skills, preserve only these existing subsection headings from the source CV: {list(evidence.supported_skills_by_subsection.keys())}
- Do not add subsection headings.
- Do not add tools not already present in the allowed skills lists below.
- Do not mention missing skills in the rewritten CV.
- Do not invent employers, projects, metrics, or responsibilities.
- You may use normalized synonyms for supported tools and concepts, such as 'large language models' for 'LLMs' and 'retrieval-augmented generation' for 'RAG'.
- Do not introduce adjacent tools that are not supported by the CV.

Allowed summary facts:
{evidence.allowed_summary_facts}

Supported skills by subsection:
{evidence.supported_skills_by_subsection}

Missing skills not allowed:
{evidence.missing_skills_not_allowed}

Job description context:
Required skills: {job_description.required_skills}
Preferred skills: {job_description.preferred_skills}
Tools/frameworks: {job_description.tools_frameworks}

Current summary:
{cv_document.summary.text}
""".strip()


def _validate_llm_output(output: dict, evidence: RewriteEvidence) -> tuple[bool, str | None]:
    allowed_headings = set(evidence.supported_skills_by_subsection)
    actual_headings = set(output.get("suggested_skills_section", {}))
    if not actual_headings.issubset(allowed_headings):
        return False, "LLM introduced unsupported skills subsection headings."

    allowed_tools = {
        heading: {tool.lower() for tool in tools}
        for heading, tools in evidence.supported_skills_by_subsection.items()
    }
    for heading, tools in output.get("suggested_skills_section", {}).items():
        if any(tool.lower() not in allowed_tools.get(heading, set()) for tool in tools):
            return False, "LLM introduced unsupported tools into the skills section."
    summary = output.get("rewritten_summary", "")
    lowered_summary = summary.lower()
    for forbidden in evidence.missing_skills_not_allowed:
        if forbidden.lower() in lowered_summary:
            return False, "LLM inserted missing JD keywords into the summary."
    return True, None


def _filter_changed_skills_sections(
    cv_document: CVDocument,
    suggested_skills_section: dict[str, list[str]],
) -> tuple[dict[str, list[str]], str | None]:
    original_skills = _original_skills_by_subsection(cv_document)
    changed = {
        heading: tools
        for heading, tools in suggested_skills_section.items()
        if tools != original_skills.get(heading, [])
    }
    if not changed:
        return {}, "No changes required in the Skills section."
    return changed, None


def generate_rewrite(
    cv_document: CVDocument,
    job_description: JobDescription,
    fit_analysis: FitAnalysis,
    client: GeminiRewriteClient | None = None,
) -> RewriteSuggestion:
    evidence = _prepare_rewrite_evidence(cv_document, job_description, fit_analysis)
    deterministic = _deterministic_rewrite(cv_document, job_description, fit_analysis, evidence)
    rewrite_client = client or GeminiRewriteClient()
    if not rewrite_client.enabled:
        deterministic.fallback_reason = "GEMINI_API_KEY is not configured."
        return deterministic

    try:
        llm_output = rewrite_client.rewrite(_build_llm_prompt(cv_document, job_description, evidence))
    except GeminiRewriteError as exc:
        deterministic.fallback_reason = str(exc)
        return deterministic

    valid, reason = _validate_llm_output(llm_output, evidence)
    if not valid:
        deterministic.fallback_reason = reason
        return deterministic

    improved_ats = min(100, fit_analysis.estimated_ats_score + 5)
    changed_skills, skills_change_message = _filter_changed_skills_sections(
        cv_document,
        llm_output["suggested_skills_section"],
    )
    return RewriteSuggestion(
        rewritten_summary=llm_output["rewritten_summary"].strip(),
        suggested_skills_section=changed_skills,
        skills_change_message=skills_change_message,
        missing_but_not_inserted=evidence.missing_skills_not_allowed,
        improved_ats_estimate=improved_ats,
        evidence_map={
            "rewritten_summary": evidence.allowed_summary_facts,
            "suggested_skills_section": [
                "Only changed subsections are returned for the Skills section.",
                "LLM output validated against parsed subsection headings and supported tools."
            ],
        },
        used_llm=True,
        fallback_reason=None,
    )
