from __future__ import annotations

import json
import os

from .config import load_local_env, settings


class GeminiRewriteError(RuntimeError):
    """Raised when the Gemini rewrite call fails or returns invalid content."""


class GeminiRewriteClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        load_local_env()
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", settings.gemini_api_key)
        self.model = model if model is not None else os.getenv("GEMINI_MODEL", settings.gemini_model)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def rewrite(self, prompt: str) -> dict:
        if not self.enabled:
            raise GeminiRewriteError("Missing GEMINI_API_KEY.")
        try:
            import httpx
        except ModuleNotFoundError as exc:
            raise GeminiRewriteError("httpx is not installed for Gemini calls.") from exc

        instruction = (
            "Return valid JSON only with keys: "
            "rewritten_summary (string) and suggested_skills_sections "
            "(array of objects with heading:string and tools:string[]). "
            "Do not include markdown fences or extra commentary."
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"{instruction}\n\n{prompt}"
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error", {}).get("message", response.text)
            except Exception:
                message = response.text
            raise GeminiRewriteError(f"Gemini request failed: {response.status_code} - {message}")
        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiRewriteError("Gemini response did not include candidate text.") from exc
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiRewriteError("Gemini returned invalid JSON.") from exc
        sections = parsed.get("suggested_skills_sections", [])
        parsed["suggested_skills_section"] = {
            item["heading"]: item["tools"]
            for item in sections
            if isinstance(item, dict) and "heading" in item and "tools" in item
        }
        return parsed

    def generate_hiring_manager_message_body(self, prompt: str) -> str:
        if not self.enabled:
            raise GeminiRewriteError("Missing GEMINI_API_KEY.")
        try:
            import httpx
        except ModuleNotFoundError as exc:
            raise GeminiRewriteError("httpx is not installed for Gemini calls.") from exc

        instruction = (
            "Return only the body paragraph text for a LinkedIn message. "
            "Do not include greeting, sign-off, placeholders, or surrounding template text. "
            "Keep the tone natural and professional, and do not invent unsupported experience."
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"{instruction}\n\n{prompt}"
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
            },
        }
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error", {}).get("message", response.text)
            except Exception:
                message = response.text
            raise GeminiRewriteError(f"Gemini request failed: {response.status_code} - {message}")
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiRewriteError("Gemini response did not include candidate text.") from exc
