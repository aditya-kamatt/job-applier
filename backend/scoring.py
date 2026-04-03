from __future__ import annotations

from math import ceil

from shared.models import CVDocument, FitAnalysis, JobDescription, ScoreBreakdown

from .config import settings


def _score_overlap(have: set[str], wanted: set[str]) -> int:
    if not wanted:
        return 100
    return round((len(have & wanted) / len(wanted)) * 100)


def _collect_cv_skills(cv_document: CVDocument) -> set[str]:
    direct = {item.skill for item in cv_document.technologies}
    skills_text = cv_document.skills.text.lower()
    direct.update(part.strip().lower() for part in skills_text.replace("\n", ",").split(",") if part.strip())
    return {item for item in direct if item}


def _seniority_score(cv_document: CVDocument, job_description: JobDescription) -> tuple[int, list[str]]:
    evidence: list[str] = []
    target = (job_description.seniority_level or " ".join(job_description.seniority_indicators)).lower()
    if not target:
        return 75, evidence

    corpus = " ".join(
        [
            cv_document.summary.text.lower(),
            cv_document.experience.text.lower(),
            cv_document.projects.text.lower(),
        ]
    )
    if target and target in corpus:
        evidence.append(f"CV references seniority-aligned language: {target}")
        return 100, evidence
    evidence.append(f"JD requests {target} level, but the CV does not explicitly claim it.")
    return 55, evidence


def _keyword_coverage(cv_document: CVDocument, jd: JobDescription) -> tuple[int, list[str]]:
    corpus = " ".join(
        [
            cv_document.summary.text.lower(),
            cv_document.experience.text.lower(),
            cv_document.projects.text.lower(),
            cv_document.skills.text.lower(),
            cv_document.certifications.text.lower(),
            cv_document.publications.text.lower(),
        ]
    )
    matched = [keyword for keyword in jd.required_skills + jd.tools_frameworks if keyword.lower() in corpus]
    wanted = set(jd.required_skills + jd.tools_frameworks)
    return _score_overlap(set(matched), wanted), sorted(set(matched))


def analyze_fit(cv_document: CVDocument, job_description: JobDescription) -> FitAnalysis:
    cv_skills = _collect_cv_skills(cv_document)
    jd_required = {skill.lower() for skill in job_description.required_skills}
    jd_preferred = {skill.lower() for skill in job_description.preferred_skills}
    jd_tools = {tool.lower() for tool in job_description.tools_frameworks}

    skill_match = _score_overlap(cv_skills, jd_required or jd_tools)
    experience_relevance = _score_overlap(
        set(cv_document.experience.text.lower().split()),
        set(" ".join(job_description.responsibilities).lower().split()),
    )
    project_relevance = _score_overlap(
        set(cv_document.projects.text.lower().split()),
        set(" ".join(job_description.domain_keywords + job_description.tools_frameworks).lower().split()),
    )
    keyword_coverage, keyword_matches = _keyword_coverage(cv_document, job_description)
    seniority_fit, seniority_evidence = _seniority_score(cv_document, job_description)

    weights = settings.scoring_weights
    overall = ceil(
        skill_match * weights.skill_match
        + experience_relevance * weights.experience_relevance
        + project_relevance * weights.project_relevance
        + keyword_coverage * weights.keyword_coverage
        + seniority_fit * weights.seniority_fit
    )
    ats = min(100, round((skill_match * 0.45) + (keyword_coverage * 0.40) + (seniority_fit * 0.15)))

    missing_keywords = sorted((jd_required | jd_tools | jd_preferred) - cv_skills)
    strong_sections: list[str] = []
    weak_sections: list[str] = []
    section_evidence: dict[str, list[str]] = {}
    if cv_document.summary.text:
        summary_hits = [item for item in keyword_matches if item in cv_document.summary.text.lower()]
        if summary_hits:
            strong_sections.append("summary")
            section_evidence["summary"] = summary_hits
        else:
            weak_sections.append("summary")
            section_evidence["summary"] = ["Summary lacks direct JD keyword alignment."]
    else:
        weak_sections.append("summary")
        section_evidence["summary"] = ["Summary section is empty."]

    if cv_document.skills.text:
        strong_sections.append("skills")
        section_evidence["skills"] = sorted(cv_skills & (jd_required | jd_tools | jd_preferred))
    else:
        weak_sections.append("skills")
        section_evidence["skills"] = ["Skills section is empty."]

    for locked_name in ("experience", "projects"):
        section = getattr(cv_document, locked_name)
        if section.text:
            section_hits = [item for item in keyword_matches if item in section.text.lower()]
            section_evidence[locked_name] = section_hits or [f"{locked_name.capitalize()} provides supporting evidence."]
        else:
            section_evidence[locked_name] = [f"{locked_name.capitalize()} section is missing or sparse."]

    supported_facts = sorted(
        {
            evidence
            for skill in cv_document.technologies
            for evidence in skill.evidence
        }
    )[:12]
    inferred_alignment = []
    if skill_match >= 60:
        inferred_alignment.append("Candidate appears to match core technical requirements.")
    if project_relevance >= 50:
        inferred_alignment.append("Projects suggest practical relevance to the target role.")

    missing_requirements = [
        f"Missing or weak evidence for: {keyword}"
        for keyword in missing_keywords[:10]
    ]

    editable_recommendations = {
        "summary": [],
        "skills": [],
    }
    if missing_keywords:
        editable_recommendations["summary"].append(
            "Emphasize the strongest supported technologies and role-relevant outcomes in the summary."
        )
        editable_recommendations["skills"].append(
            "Reorder supported skills so the most relevant JD-aligned technologies appear first."
        )
    if keyword_coverage < 60:
        editable_recommendations["summary"].append(
            "Mirror JD terminology in the summary using only evidence already present elsewhere in the CV."
        )
    if not (cv_skills & jd_required):
        editable_recommendations["skills"].append(
            "Do not add unsupported skills; instead surface missing JD keywords separately as gaps."
        )

    return FitAnalysis(
        overall_fit_score=overall,
        estimated_ats_score=ats,
        score_breakdown=ScoreBreakdown(
            skill_match=skill_match,
            experience_relevance=experience_relevance,
            project_relevance=project_relevance,
            keyword_coverage=keyword_coverage,
            seniority_fit=seniority_fit,
        ),
        missing_keywords=missing_keywords,
        strong_sections=sorted(set(strong_sections)),
        weak_sections=sorted(set(weak_sections)),
        supported_facts=supported_facts,
        inferred_alignment=inferred_alignment + seniority_evidence,
        missing_requirements=missing_requirements,
        editable_recommendations=editable_recommendations,
        section_evidence=section_evidence,
    )
