from __future__ import annotations

import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class UnsupportedFileTypeError(ValueError):
    """Raised when an uploaded file format is not supported."""


def _clean_pdf_artifacts(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line
        line = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", " ", line)
        line = re.sub(r"[§ð]+", " ", line)
        line = re.sub(r"\bGitHub\s+\d+\b", "GitHub", line)
        line = re.sub(r"\bresearch\s+\d+\s+on\b", "research on", line, flags=re.IGNORECASE)
        line = re.sub(r"\s{2,}", " ", line).strip()
        lines.append(line)
    return "\n".join(lines)


def _normalize_extracted_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_upload(file_name: str, raw_bytes: bytes) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf_bytes(raw_bytes)
    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix or 'unknown'}")


def extract_text_from_pdf_bytes(raw_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(raw_bytes)
        temp_pdf.flush()
        result = subprocess.run(
            ["pdftotext", temp_pdf.name, "-"],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown pdftotext error"
        raise ValueError(f"Failed to extract PDF text: {stderr}")
    text = _normalize_extracted_text(_clean_pdf_artifacts(result.stdout))
    if not text:
        raise ValueError("PDF extraction returned empty text.")
    return text


def extract_text_from_docx_bytes(raw_bytes: bytes) -> str:
    with tempfile.SpooledTemporaryFile() as temp_docx:
        temp_docx.write(raw_bytes)
        temp_docx.seek(0)
        with zipfile.ZipFile(temp_docx) as archive:
            xml_bytes = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    paragraphs: list[str] = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for paragraph in root.findall(".//w:p", namespace):
        text_parts = [
            node.text
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        line = "".join(text_parts).strip()
        if line:
            paragraphs.append(line)
    text = _normalize_extracted_text("\n".join(paragraphs))
    if not text:
        raise ValueError("DOCX extraction returned empty text.")
    return text
