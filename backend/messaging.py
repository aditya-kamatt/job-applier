from __future__ import annotations

from shared.models import CVDocument, FitAnalysis, JobDescription, LinkedInMessageResult

from .gemini_client import GeminiRewriteClient, GeminiRewriteError


def _compose_hiring_manager_message(
    body: str,
    job_description: JobDescription,
) -> str:
    role = job_description.job_title or "[role name]"
    company = f" at {job_description.company_name}" if job_description.company_name else ""
    return (
        f"Hi [Hiring manager's name],\n\n"
        f"I hope you are doing well. I came across the {role} role{company} and wanted to reach out directly.\n\n"
        f"{body.strip()}\n\n"
        f"I have applied for the job on LinkedIn and have also attached my CV for your reference below. "
        f"We can have a chat to discuss more about the role and how it aligns with my experiences. "
        f"Please let me know whenever it suits you to have a quick chat.\n\n"
        f"Thank you for your time.\n\n"
        f"Best regards,\n"
        f"Aditya Ajit Kamat\n"
    )


def _deterministic_hiring_manager_message(
    cv_document: CVDocument,
    job_description: JobDescription,
    fit_analysis: FitAnalysis,
) -> LinkedInMessageResult:
    strongest_skills = fit_analysis.section_evidence.get("skills", [])[:3]
    strongest_skill_text = ", ".join(strongest_skills) if strongest_skills else "production-grade AI engineering"
    experience_lines = cv_document.experience.bullets[:2] or cv_document.projects.bullets[:2]
    evidence_line = " ".join(experience_lines).strip() if experience_lines else "I have been building production-facing AI systems with measurable impact."
    visa_line = ""
    lowered_cv = cv_document.raw_text.lower()
    if "skilled worker visa" in lowered_cv:
        visa_line = " I am currently holding a UK skilled worker visa."
    body = (
        f"I’m currently working in AI engineering roles where I build and deploy systems aligned with skills such as {strongest_skill_text}. "
        f"{evidence_line}{visa_line}"
    )
    return LinkedInMessageResult(
        hiring_manager_message=_compose_hiring_manager_message(body, job_description),
        personalization_evidence=fit_analysis.supported_facts[:5],
        used_llm=False,
        fallback_reason="GEMINI_API_KEY is not configured.",
    )


def _build_message_prompt(
    cv_document: CVDocument,
    job_description: JobDescription,
    fit_analysis: FitAnalysis,
) -> str:
    role = job_description.job_title or "role"
    company = job_description.company_name or "[Company name]"
    skills = fit_analysis.section_evidence.get("skills", [])[:6]
    experience_lines = cv_document.experience.bullets[:3] or cv_document.projects.bullets[:3]
    visa_note = "Include that the candidate holds a UK skilled worker visa." if "skilled worker visa" in cv_document.raw_text.lower() else "Do not mention visa status unless supported."
    return f"""
Write only the body paragraph for a LinkedIn message to the hiring manager.

The app will wrap your body inside this fixed template:
- Greeting to hiring manager
- "I hope you are doing well. I came across the {role} role at {company} and wanted to reach out directly."
- Your generated body
- "I have applied for the job on LinkedIn and have also attached my CV for your reference below. We can have a chat to discuss more about the role and how it aligns with my experiences. Please let me know whenever it suits you to have a quick chat."
- "Thank you for your time."
- "Best regards, Aditya Ajit Kamat"

Rules:
- Return only the body paragraph.
- Do not include greeting, closing, sign-off, or template text.
- Keep it professional, polished, and moderately detailed.
- Use only supported CV evidence.
- Do not exaggerate or invent tools, projects, employers, or metrics.
- The body should sound like a direct, polished hiring manager outreach note.
- Relate the candidate's skills and recent experience to the JD.
- It is okay to mention visa status only if supported by the CV.
- {visa_note}

Supported evidence:
{fit_analysis.supported_facts[:8]}

Relevant skills:
{skills}

Relevant project or experience bullets:
{experience_lines}

Job description:
Required skills: {job_description.required_skills}
Preferred skills: {job_description.preferred_skills}
Responsibilities: {job_description.responsibilities[:5]}
""".strip()


def generate_linkedin_messages(
    cv_document: CVDocument,
    job_description: JobDescription,
    fit_analysis: FitAnalysis,
) -> LinkedInMessageResult:
    client = GeminiRewriteClient()
    deterministic = _deterministic_hiring_manager_message(cv_document, job_description, fit_analysis)
    if not client.enabled:
        return deterministic
    try:
        body = client.generate_hiring_manager_message_body(
            _build_message_prompt(cv_document, job_description, fit_analysis)
        )
    except GeminiRewriteError as exc:
        deterministic.fallback_reason = str(exc)
        return deterministic
    return LinkedInMessageResult(
        hiring_manager_message=_compose_hiring_manager_message(body, job_description),
        personalization_evidence=fit_analysis.supported_facts[:5],
        used_llm=True,
        fallback_reason=None,
    )
