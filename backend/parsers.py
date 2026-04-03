from __future__ import annotations

from collections import defaultdict

from shared.models import CVDocument, JobDescription, SectionContent, SkillEvidence, SkillsSubsection

from .text_utils import (
    SECTION_HEADERS,
    SOFT_SKILLS,
    SENIORITY_KEYWORDS,
    SKILL_KEYWORDS,
    bullet_text,
    canonical_section_name,
    extract_numbers,
    find_keywords,
    is_bullet,
    normalize_whitespace,
)


def _blank_section(section_name: str, order: int = 0) -> SectionContent:
    heading = section_name.capitalize()
    return SectionContent(heading=heading, order=order)


SKILL_SUBSECTION_ALIASES = {
    "programming & software engineering": "Programming & Software Engineering",
    "machine learning": "Machine Learning",
    "llm & agentic ai": "LLM & Agentic AI",
    "cloud & infrastructure": "Cloud & Infrastructure",
}


def _canonical_skill_subsection(line: str) -> str | None:
    normalized = line.strip().strip(":").strip(" -•*◦–").lower()
    return SKILL_SUBSECTION_ALIASES.get(normalized)


def _split_skill_tools(line: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in line:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        if char == "," and depth == 0:
            candidate = "".join(current).strip()
            if candidate:
                parts.append(candidate)
            current = []
            continue
        current.append(char)
    candidate = "".join(current).strip()
    if candidate:
        parts.append(candidate)
    return parts


def _parse_skills_subsections(section: SectionContent) -> list[SkillsSubsection]:
    subsections: list[SkillsSubsection] = []
    current_heading: str | None = None
    current_tools: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_tools
        if current_heading:
            deduped: list[str] = []
            seen: set[str] = set()
            for tool in current_tools:
                key = tool.lower()
                if key not in seen:
                    seen.add(key)
                    deduped.append(tool)
            subsections.append(SkillsSubsection(heading=current_heading, tools=deduped))
        current_heading = None
        current_tools = []

    for bullet in section.bullets:
        maybe_heading = _canonical_skill_subsection(bullet)
        if maybe_heading:
            flush()
            current_heading = maybe_heading
            continue
        if not current_heading:
            continue
        cleaned_parts = _split_skill_tools(bullet)
        current_tools.extend(cleaned_parts)
    flush()
    return subsections


def parse_cv(cv_text: str) -> CVDocument:
    normalized = normalize_whitespace(cv_text.replace("\f", "\n"))
    lines = normalized.split("\n")
    known_sections = {name: _blank_section(name) for name in SECTION_HEADERS}
    current = None
    buffer: list[str] = []
    bullets: defaultdict[str, list[str]] = defaultdict(list)
    current_bullet: dict[str, str] = {}
    order = 0
    start_line = 0

    def flush(section_name: str | None, end_line: int) -> None:
        nonlocal buffer, start_line
        if section_name is None:
            buffer = []
            return
        if section_name in current_bullet and current_bullet[section_name]:
            bullets[section_name].append(current_bullet[section_name].strip())
            current_bullet[section_name] = ""
        section = known_sections[section_name]
        section.text = "\n".join(buffer).strip()
        section.bullets = bullets.get(section_name, [])
        section.source_span = (start_line, end_line)
        buffer = []

    for index, line in enumerate(lines):
        section_name = canonical_section_name(line)
        if section_name:
            flush(current, index - 1)
            if section_name == "certifications_publications":
                current = section_name
            else:
                current = section_name
            order += 1
            known_sections[section_name].order = order
            known_sections[section_name].heading = line.strip().strip(":")
            start_line = index
            continue
        if current:
            buffer.append(line)
            if is_bullet(line):
                if current_bullet.get(current):
                    bullets[current].append(current_bullet[current].strip())
                current_bullet[current] = bullet_text(line)
            elif current_bullet.get(current) and line.strip():
                current_bullet[current] = f"{current_bullet[current]} {line.strip()}"
    flush(current, len(lines) - 1)

    combined_section = known_sections.get("certifications_publications")
    if combined_section and (combined_section.text or combined_section.bullets):
        cert_lines: list[str] = []
        pub_lines: list[str] = []
        combined_items = combined_section.bullets or [
            line.strip() for line in combined_section.text.split("\n") if line.strip()
        ]
        for item in combined_items:
            lowered = item.lower()
            if "publish" in lowered or "research" in lowered or "paper" in lowered:
                pub_lines.append(item)
            else:
                cert_lines.append(item)
        known_sections["certifications"].text = "\n".join(cert_lines).strip()
        known_sections["certifications"].bullets = cert_lines
        known_sections["certifications"].heading = "Certifications"
        known_sections["certifications"].order = combined_section.order
        known_sections["publications"].text = "\n".join(pub_lines).strip()
        known_sections["publications"].bullets = pub_lines
        known_sections["publications"].heading = "Publications"
        known_sections["publications"].order = combined_section.order + 1
        known_sections.pop("certifications_publications", None)

    evidence_lines: list[str] = []
    for name in ("experience", "projects", "summary", "skills", "certifications", "publications"):
        section = known_sections[name]
        if section.text:
            evidence_lines.append(section.text)
        evidence_lines.extend(section.bullets)

    skill_hits = find_keywords("\n".join(evidence_lines), SKILL_KEYWORDS)
    technologies = [
        SkillEvidence(
            skill=skill,
            evidence=[line for line in evidence_lines if skill.lower() in line.lower()][:3],
            supported=True,
        )
        for skill in skill_hits
    ]

    metrics = extract_numbers("\n".join(evidence_lines))
    return CVDocument(
        raw_text=normalized,
        summary=known_sections["summary"],
        experience=known_sections["experience"],
        education=known_sections["education"],
        projects=known_sections["projects"],
        skills=known_sections["skills"],
        certifications=known_sections["certifications"],
        publications=known_sections["publications"],
        technologies=technologies,
        skills_subsections=_parse_skills_subsections(known_sections["skills"]),
        metrics=metrics,
    )


def _split_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    for line in normalize_whitespace(text).split("\n"):
        stripped = line.strip(" -•*")
        if not stripped:
            continue
        if ":" in stripped and len(stripped.split()) <= 5:
            continue
        parts = [item.strip() for item in stripped.split(",")]
        if len(parts) > 1:
            phrases.extend(part for part in parts if part)
        else:
            phrases.append(stripped)
    return phrases


def parse_job_description(
    job_description_text: str,
    job_title: str | None = None,
    company_name: str | None = None,
    seniority_level: str | None = None,
) -> JobDescription:
    normalized = normalize_whitespace(job_description_text)
    lines = normalized.split("\n")
    phrases = _split_phrases(normalized)
    keyword_hits = find_keywords(normalized, SKILL_KEYWORDS)
    soft_skill_hits = find_keywords(normalized, SOFT_SKILLS)
    seniority_hits = find_keywords(normalized, set(SENIORITY_KEYWORDS))

    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: list[str] = []
    tools_frameworks: list[str] = []
    domain_keywords: list[str] = []

    for line in lines:
        lowered = line.lower()
        if lowered.startswith("required:") or lowered.startswith("requirements:"):
            required_skills.extend([skill for skill in keyword_hits if skill in lowered])
        elif lowered.startswith("preferred:") or lowered.startswith("nice to have:"):
            preferred_skills.extend([skill for skill in keyword_hits if skill in lowered])

    for phrase in phrases:
        lowered = phrase.lower()
        if any(token in lowered for token in ("must", "required", "requirement", "need", "expertise in")):
            required_skills.extend([skill for skill in keyword_hits if skill in lowered])
        elif any(token in lowered for token in ("preferred", "nice to have", "bonus", "plus")):
            preferred_skills.extend([skill for skill in keyword_hits if skill in lowered])
        elif any(token in lowered for token in ("build", "design", "develop", "deploy", "lead", "own")):
            responsibilities.append(phrase)
        elif any(skill in lowered for skill in keyword_hits):
            tools_frameworks.extend([skill for skill in keyword_hits if skill in lowered])
        else:
            domain_keywords.append(phrase)

    if not required_skills:
        required_skills = keyword_hits[:5]

    if not tools_frameworks:
        tools_frameworks = keyword_hits

    if not domain_keywords:
        domain_keywords = [phrase for phrase in phrases if len(phrase.split()) <= 6][:8]

    detected_seniority = [SENIORITY_KEYWORDS[item] for item in seniority_hits]
    return JobDescription(
        raw_text=normalized,
        required_skills=sorted(set(required_skills)),
        preferred_skills=sorted(set(preferred_skills)),
        responsibilities=responsibilities[:10],
        tools_frameworks=sorted(set(tools_frameworks)),
        domain_keywords=sorted(set(domain_keywords))[:12],
        soft_skills=soft_skill_hits,
        seniority_indicators=detected_seniority,
        job_title=job_title,
        company_name=company_name,
        seniority_level=seniority_level,
    )
