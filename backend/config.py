from __future__ import annotations

import os
from dataclasses import dataclass, field


def load_local_env(env_path: str = ".env") -> None:
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_local_env()


@dataclass(slots=True)
class ScoringWeights:
    skill_match: float = 0.30
    experience_relevance: float = 0.25
    project_relevance: float = 0.15
    keyword_coverage: float = 0.20
    seniority_fit: float = 0.10


@dataclass(slots=True)
class Settings:
    application_storage_path: str = "data/applications.json"
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))


settings = Settings()
