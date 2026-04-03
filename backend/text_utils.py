from __future__ import annotations

import re


SECTION_HEADERS = {
    "summary": ["summary", "professional summary", "profile"],
    "experience": ["experience", "work experience", "professional experience", "employment"],
    "education": ["education", "academic background"],
    "projects": ["projects", "selected projects"],
    "skills": ["skills", "technical skills", "core skills", "technologies"],
    "certifications": ["certifications", "licenses", "certificates"],
    "publications": ["publications", "research", "papers"],
    "certifications_publications": [
        "certifications and publications",
        "certifications publications",
    ],
}

SKILL_KEYWORDS = {
    "python",
    "sql",
    "aws",
    "gcp",
    "azure",
    "docker",
    "kubernetes",
    "tensorflow",
    "pytorch",
    "scikit-learn",
    "machine learning",
    "deep learning",
    "nlp",
    "llm",
    "llms",
    "langchain",
    "rag",
    "vector db",
    "postgresql",
    "fastapi",
    "streamlit",
    "redis",
    "celery",
    "transformers",
    "openai",
    "anthropic",
    "pandas",
}

SOFT_SKILLS = {
    "communication",
    "collaboration",
    "leadership",
    "stakeholder management",
    "problem solving",
    "mentoring",
}

SENIORITY_KEYWORDS = {
    "junior": "junior",
    "mid": "mid",
    "senior": "senior",
    "lead": "lead",
    "staff": "staff",
    "principal": "principal",
}


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text).strip()


def slugify_heading(value: str) -> str:
    value = value.strip().lower().strip(":")
    return re.sub(r"[^a-z]+", " ", value).strip()


def canonical_section_name(line: str) -> str | None:
    normalized = slugify_heading(line)
    for section, headings in SECTION_HEADERS.items():
        if normalized in headings:
            return section
    return None


def split_lines(text: str) -> list[str]:
    return [line.rstrip() for line in normalize_whitespace(text).split("\n")]


def bullet_text(line: str) -> str:
    return re.sub(r"^\s*[-*•◦–]+\s*", "", line).strip()


def is_bullet(line: str) -> bool:
    return bool(re.match(r"^\s*[-*•◦–]+\s+", line))


def extract_numbers(text: str) -> list[str]:
    return re.findall(r"\b\d+(?:\.\d+)?%?\+?\b", text)


def find_keywords(text: str, candidates: set[str]) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for keyword in candidates:
        if " " in keyword:
            if keyword in lowered:
                matches.append(keyword)
            continue
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, lowered):
            matches.append(keyword)
    return sorted(set(matches))
