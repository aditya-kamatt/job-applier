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

CANONICAL_TECH_TERMS = {
    "python": {"python"},
    "sql": {"sql"},
    "aws": {"aws", "amazon web services"},
    "gcp": {"gcp", "google cloud", "google cloud platform"},
    "azure": {"azure", "microsoft azure"},
    "docker": {"docker"},
    "kubernetes": {"kubernetes", "k8s"},
    "tensorflow": {"tensorflow"},
    "pytorch": {"pytorch"},
    "scikit-learn": {"scikit-learn", "sklearn"},
    "machine learning": {"machine learning", "ml"},
    "deep learning": {"deep learning"},
    "nlp": {"nlp", "natural language processing"},
    "llm": {"llm", "llms", "large language model", "large language models"},
    "langchain": {"langchain"},
    "rag": {"rag", "retrieval augmented generation", "retrieval-augmented generation"},
    "vector db": {"vector db", "vector database", "vector databases"},
    "postgresql": {"postgresql", "postgres"},
    "fastapi": {"fastapi", "fastapi-based", "fastapi based"},
    "streamlit": {"streamlit"},
    "redis": {"redis"},
    "celery": {"celery"},
    "transformers": {"transformers", "transformer architectures", "transformer models"},
    "openai": {"openai", "openai api", "openai embeddings"},
    "anthropic": {"anthropic", "claude"},
    "pandas": {"pandas"},
}

CANONICAL_DISPLAY_LABELS = {
    "python": "Python",
    "sql": "SQL",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "scikit-learn": "Scikit-learn",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "nlp": "Natural Language Processing",
    "llm": "Large Language Models",
    "langchain": "LangChain",
    "rag": "Retrieval-Augmented Generation",
    "vector db": "Vector Database",
    "postgresql": "PostgreSQL",
    "fastapi": "FastAPI",
    "streamlit": "Streamlit",
    "redis": "Redis",
    "celery": "Celery",
    "transformers": "Transformers",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "pandas": "Pandas",
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


def canonicalize_technical_terms(text: str) -> set[str]:
    lowered = text.lower()
    matches: set[str] = set()
    for canonical, variants in CANONICAL_TECH_TERMS.items():
        for variant in variants:
            if " " in variant or "-" in variant:
                if variant in lowered:
                    matches.add(canonical)
                    break
            else:
                pattern = rf"\b{re.escape(variant)}\b"
                if re.search(pattern, lowered):
                    matches.add(canonical)
                    break
    return matches


def canonicalize_term_list(values: list[str]) -> set[str]:
    matches: set[str] = set()
    for value in values:
        matches.update(canonicalize_technical_terms(value))
    return matches


def display_label_for_term(canonical_term: str) -> str:
    return CANONICAL_DISPLAY_LABELS.get(canonical_term, canonical_term.title())
