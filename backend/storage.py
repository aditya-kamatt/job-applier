from __future__ import annotations

import json
import uuid
from pathlib import Path

from shared.models import (
    ApplicationRecord,
    CVDocument,
    FitAnalysis,
    JobDescription,
    LinkedInMessageResult,
    RewriteSuggestion,
    dataclass_to_dict,
)

from .config import settings
from .dto import application_record_from_dict


class ApplicationRepository:
    """JSON-backed repository with a PostgreSQL-compatible boundary for MVP development."""

    def __init__(self, storage_path: str | None = None) -> None:
        self.storage_path = Path(storage_path or settings.application_storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text("{}", encoding="utf-8")

    def save(
        self,
        cv_document: CVDocument,
        job_description: JobDescription,
        fit_analysis: FitAnalysis,
        rewrite_suggestion: RewriteSuggestion,
        linkedin_message: LinkedInMessageResult,
    ) -> ApplicationRecord:
        application_id = str(uuid.uuid4())
        record = ApplicationRecord(
            application_id=application_id,
            cv_document=cv_document,
            job_description=job_description,
            fit_analysis=fit_analysis,
            rewrite_suggestion=rewrite_suggestion,
            linkedin_message=linkedin_message,
        )
        payload = self._read()
        payload[application_id] = dataclass_to_dict(record)
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return record

    def get(self, application_id: str) -> ApplicationRecord | None:
        payload = self._read()
        raw = payload.get(application_id)
        if not raw:
            return None
        return application_record_from_dict(raw)

    def _read(self) -> dict:
        return json.loads(self.storage_path.read_text(encoding="utf-8"))
