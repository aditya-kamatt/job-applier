from __future__ import annotations

import io
import tempfile
import unittest
import zipfile

from backend.ingestion import extract_text_from_docx_bytes, extract_text_from_upload
from backend.gemini_client import GeminiRewriteError
from backend.parsers import parse_cv, parse_job_description
from backend.pipeline import ApplyAIPipeline
from backend.rewrite import generate_rewrite
from backend.scoring import analyze_fit
from backend.storage import ApplicationRepository
from backend.messaging import _compose_hiring_manager_message, generate_linkedin_messages
from shared.models import AnalyzeRequest


SAMPLE_CV = """
Summary
AI/ML engineer building NLP systems with Python, FastAPI, AWS, and LLM workflows.

Experience
- Built production APIs for model inference and evaluation.
- Improved model quality by 18% across ranking experiments.

Education
B.Tech in Computer Science

Projects
- Designed a RAG assistant using OpenAI embeddings and vector db retrieval.

Skills
Python, FastAPI, AWS, NLP, OpenAI, SQL

Certifications
AWS Certified Cloud Practitioner

Publications
Efficient Retrieval for Domain QA
"""


SAMPLE_JD = """
We are hiring a Senior Machine Learning Engineer to build LLM products.
Required: Python, AWS, FastAPI, RAG, NLP.
Preferred: LangChain, PostgreSQL.
You will design and deploy production AI systems and collaborate across teams.
"""


PDF_STYLE_CV = """
Aditya Ajit Kamat

Summary
AI Engineer specialising in LLM-powered systems, RAG pipelines, and healthcare AI workflows using Python and AWS.

Experience
AI Engineer
March 2024 - Present
i3 Simulations (Luton, UK)
◦ Developed real-time ML inference pipelines for decision-making systems.
◦ Designed and implemented RESTful APIs and Python microservices(FastAPI based).

Projects
PDF Converter Web App
GitHub 2
◦ Designed a document intelligence pipeline in Python.
◦ Built automation logic to handle diverse file types via Flask APIs.

Skills
◦ Programming & Software Engineering:
– Python (production-grade development)
– API development (Flask, FastAPI)
◦ Machine Learning:
– PyTorch
◦ LLM & Agentic AI:
– Retrieval augmented generation (RAG) pipelines
– LangChain, LangGraph, LLamaIndex
◦ Cloud & Infrastructure:
– AWS
– Docker

Certifications And Publications
◦ Machine Learning Operations Specialisation by Duke University.
◦ Published research on Assessment of Waste Management using Deep Learning and Edge Computing.
"""


class FakeRewriteClient:
    def __init__(self, payload: dict | None = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.enabled = True

    def rewrite(self, prompt: str) -> dict:
        if self.error:
            raise self.error
        assert self.payload is not None
        return self.payload


class ParserTests(unittest.TestCase):
    def test_cv_parser_extracts_expected_headers(self) -> None:
        document = parse_cv(SAMPLE_CV)
        self.assertEqual(document.summary.heading.lower(), "summary")
        self.assertTrue(document.experience.bullets)
        self.assertIn("python", {item.skill for item in document.technologies})
        self.assertTrue(document.publications.text)

    def test_cv_parser_handles_pdf_style_bullets_and_combined_headers(self) -> None:
        document = parse_cv(PDF_STYLE_CV)
        self.assertTrue(document.experience.bullets)
        self.assertIn("Developed real-time ML inference pipelines", document.experience.bullets[0])
        self.assertTrue(document.projects.bullets)
        self.assertTrue(document.skills.bullets)
        self.assertTrue(document.certifications.bullets)
        self.assertTrue(document.publications.bullets)
        self.assertIn("Published research", document.publications.bullets[0])
        headings = [item.heading for item in document.skills_subsections]
        self.assertEqual(
            headings,
            [
                "Programming & Software Engineering",
                "Machine Learning",
                "LLM & Agentic AI",
                "Cloud & Infrastructure",
            ],
        )
        self.assertIn("Python (production-grade development)", document.skills_subsections[0].tools)


class IngestionTests(unittest.TestCase):
    def test_pdf_like_cleanup_removes_known_cv_artifacts(self) -> None:
        noisy = (
            "Aditya Ajit Kamat\n"
            "+ Birmingham, UK \x80 Skilled Worker Visa # kamataditya2000@gmail.com \x84 +44 7405327920 ð adityakamatt § aditya-kamatt\n"
            "GitHub 2\n"
            "Published research 2 on Assessment of Waste Management\n"
        )
        from backend.ingestion import _clean_pdf_artifacts

        cleaned = _clean_pdf_artifacts(noisy)
        self.assertNotIn("\x80", cleaned)
        self.assertNotIn("ð", cleaned)
        self.assertNotIn("§", cleaned)
        self.assertIn("GitHub", cleaned)
        self.assertNotIn("GitHub 2", cleaned)
        self.assertIn("Published research on Assessment", cleaned)

    def test_docx_upload_extracts_document_xml_text(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8"?>
                <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>""",
            )
            archive.writestr(
                "word/document.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                  <w:body>
                    <w:p><w:r><w:t>Summary</w:t></w:r></w:p>
                    <w:p><w:r><w:t>AI Engineer with Python experience</w:t></w:r></w:p>
                  </w:body>
                </w:document>""",
            )
        text = extract_text_from_docx_bytes(buffer.getvalue())
        self.assertIn("Summary", text)
        self.assertIn("AI Engineer with Python experience", text)

    def test_upload_rejects_non_pdf_formats(self) -> None:
        with self.assertRaises(ValueError):
            extract_text_from_upload("resume.txt", b"Summary\nPython engineer")

    def test_jd_parser_extracts_skills_and_seniority(self) -> None:
        jd = parse_job_description(SAMPLE_JD, job_title="ML Engineer", company_name="Acme")
        self.assertIn("python", jd.required_skills)
        self.assertIn("senior", jd.seniority_indicators)
        self.assertEqual(jd.company_name, "Acme")


class AnalysisAndRewriteTests(unittest.TestCase):
    def test_rewrite_only_changes_summary_and_skills(self) -> None:
        cv = parse_cv(PDF_STYLE_CV)
        jd = parse_job_description(SAMPLE_JD)
        fit = analyze_fit(cv, jd)
        rewrite = generate_rewrite(cv, jd, fit)

        self.assertTrue(rewrite.rewritten_summary)
        self.assertEqual(rewrite.suggested_skills_section, {})
        self.assertEqual(rewrite.skills_change_message, "No changes required in the Skills section.")
        self.assertIn("experience", rewrite.locked_sections)
        self.assertNotIn("experience", rewrite.editable_sections)
        self.assertIn("PostgreSQL", rewrite.missing_but_not_inserted)
        self.assertFalse(rewrite.used_llm)
        self.assertIsNotNone(rewrite.fallback_reason)

    def test_analysis_produces_scores_and_missing_keywords(self) -> None:
        cv = parse_cv(SAMPLE_CV)
        jd = parse_job_description(SAMPLE_JD)
        fit = analyze_fit(cv, jd)

        self.assertGreater(fit.overall_fit_score, 0)
        self.assertGreater(fit.estimated_ats_score, 0)
        self.assertIn("LangChain", fit.missing_keywords)
        self.assertIn("summary", fit.editable_recommendations)

    def test_missing_keywords_use_canonical_synonyms(self) -> None:
        cv_text = """
Summary
AI engineer building LLM systems and RAG workflows.

Experience
- Built production-grade AI services.

Education
B.Tech in Computer Science

Projects
- Developed retrieval workflows for knowledge systems.

Skills
◦ LLM & Agentic AI:
– LLMs
– RAG
"""
        jd_text = """
Required: Large Language Models, Retrieval-Augmented Generation, PostgreSQL, PostgreSQL.
Preferred: LangChain.
"""
        cv = parse_cv(cv_text)
        jd = parse_job_description(jd_text)
        fit = analyze_fit(cv, jd)
        self.assertNotIn("Large Language Models", fit.missing_keywords)
        self.assertNotIn("Retrieval-Augmented Generation", fit.missing_keywords)
        self.assertIn("PostgreSQL", fit.missing_keywords)
        self.assertEqual(fit.missing_keywords.count("PostgreSQL"), 1)

    def test_llm_path_preserves_existing_subsections_only(self) -> None:
        cv = parse_cv(PDF_STYLE_CV)
        jd = parse_job_description(SAMPLE_JD)
        fit = analyze_fit(cv, jd)
        client = FakeRewriteClient(
            payload={
                "rewritten_summary": "AI Engineer with Python, FastAPI, AWS, and RAG experience in production systems.",
                "suggested_skills_section": {
                    "Programming & Software Engineering": ["Python (production-grade development)", "API development (Flask, FastAPI)"],
                    "LLM & Agentic AI": ["Retrieval augmented generation (RAG) pipelines", "LangChain", "LangGraph", "LLamaIndex"],
                },
            }
        )
        rewrite = generate_rewrite(cv, jd, fit, client=client)
        self.assertTrue(rewrite.used_llm)
        self.assertIsNone(rewrite.fallback_reason)
        self.assertNotIn("postgresql", ",".join(sum(rewrite.suggested_skills_section.values(), [])))

    def test_no_skills_output_when_no_changes_required(self) -> None:
        cv = parse_cv(PDF_STYLE_CV)
        jd = parse_job_description(SAMPLE_JD)
        fit = analyze_fit(cv, jd)
        client = FakeRewriteClient(
            payload={
                "rewritten_summary": "AI Engineer with Python, FastAPI, AWS, and RAG experience in production systems.",
                "suggested_skills_section": {
                    "Programming & Software Engineering": ["Python (production-grade development)", "API development (Flask, FastAPI)"],
                    "Machine Learning": ["PyTorch"],
                    "LLM & Agentic AI": ["Retrieval augmented generation (RAG) pipelines", "LangChain", "LangGraph", "LLamaIndex"],
                    "Cloud & Infrastructure": ["AWS", "Docker"],
                },
            }
        )
        rewrite = generate_rewrite(cv, jd, fit, client=client)
        self.assertEqual(rewrite.suggested_skills_section, {})
        self.assertEqual(rewrite.skills_change_message, "No changes required in the Skills section.")

    def test_invalid_llm_output_falls_back(self) -> None:
        cv = parse_cv(PDF_STYLE_CV)
        jd = parse_job_description(SAMPLE_JD)
        fit = analyze_fit(cv, jd)
        client = FakeRewriteClient(
            payload={
                "rewritten_summary": "AI Engineer with PostgreSQL expertise.",
                "suggested_skills_section": {
                    "New Section": ["PostgreSQL"],
                },
            }
        )
        rewrite = generate_rewrite(cv, jd, fit, client=client)
        self.assertFalse(rewrite.used_llm)
        self.assertIn("unsupported skills subsection headings", rewrite.fallback_reason)

    def test_hiring_manager_message_uses_requested_structure(self) -> None:
        cv = parse_cv(PDF_STYLE_CV)
        jd = parse_job_description(SAMPLE_JD, job_title="AI Engineer", company_name="Amtis")
        fit = analyze_fit(cv, jd)
        message = generate_linkedin_messages(cv, jd, fit)
        self.assertIn("Hi [Hiring manager's name],", message.hiring_manager_message)
        self.assertIn("I hope you are doing well.", message.hiring_manager_message)
        self.assertIn("I came across the AI Engineer role at Amtis and wanted to reach out directly.", message.hiring_manager_message)
        self.assertIn("I have applied for the job on LinkedIn", message.hiring_manager_message)
        self.assertIn("Best regards,\nAditya Ajit Kamat", message.hiring_manager_message)

    def test_compose_hiring_manager_message_only_wraps_body(self) -> None:
        jd = parse_job_description(SAMPLE_JD, job_title="AI Engineer", company_name="Amtis")
        body = "I’m currently working as an AI Engineer where I build production-grade LLM systems, FastAPI services, and RAG pipelines aligned with the requirements of this role."
        message = _compose_hiring_manager_message(body, jd)
        self.assertTrue(message.startswith("Hi [Hiring manager's name],"))
        self.assertIn(body, message)
        self.assertEqual(message.count("Best regards,"), 1)
        self.assertIn("I came across the AI Engineer role at Amtis and wanted to reach out directly.", message)

    def test_openai_error_falls_back(self) -> None:
        cv = parse_cv(PDF_STYLE_CV)
        jd = parse_job_description(SAMPLE_JD)
        fit = analyze_fit(cv, jd)
        client = FakeRewriteClient(error=GeminiRewriteError("boom"))
        rewrite = generate_rewrite(cv, jd, fit, client=client)
        self.assertFalse(rewrite.used_llm)
        self.assertEqual(rewrite.fallback_reason, "boom")


class ConfigFilesTests(unittest.TestCase):
    def test_env_example_contains_blank_gemini_key(self) -> None:
        with open(".env.example", encoding="utf-8") as env_file:
            content = env_file.read()
        self.assertIn("GEMINI_API_KEY=", content)
        self.assertIn("GEMINI_MODEL=gemini-2.5-flash", content)

    def test_gitignore_excludes_env_file(self) -> None:
        with open(".gitignore", encoding="utf-8") as ignore_file:
            content = ignore_file.read()
        self.assertIn(".env", content)
        self.assertIn("!.env.example", content)


class PipelineIntegrationTests(unittest.TestCase):
    def test_analyze_persists_application(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repository = ApplicationRepository(storage_path=f"{tempdir}/applications.json")
            pipeline = ApplyAIPipeline(repository=repository)
            result = pipeline.analyze(
                AnalyzeRequest(
                    cv_text=SAMPLE_CV,
                    job_description_text=SAMPLE_JD,
                    job_title="Senior ML Engineer",
                    company_name="Acme AI",
                    seniority_level="senior",
                )
            )

            self.assertIn("application_id", result)
            saved = pipeline.get_application(result["application_id"])
            self.assertIsNotNone(saved)
            self.assertEqual(saved.job_description.company_name, "Acme AI")
            self.assertTrue(saved.linkedin_message.hiring_manager_message)
            self.assertFalse(hasattr(saved.linkedin_message, "recruiter_message"))


if __name__ == "__main__":
    unittest.main()
