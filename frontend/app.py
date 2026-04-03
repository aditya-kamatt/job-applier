from __future__ import annotations

import streamlit as st

from backend.ingestion import UnsupportedFileTypeError, extract_text_from_upload
from shared.models import AnalyzeRequest

from backend.pipeline import ApplyAIPipeline


def render() -> None:
    st.set_page_config(page_title="ApplyAI", layout="wide")
    pipeline = ApplyAIPipeline()

    st.title("ApplyAI")
    st.caption("Grounded job application optimisation with locked non-editable CV sections.")
    uploaded_cv = st.file_uploader("Upload CV (PDF only)", type=["pdf"])

    cv_text = ""
    if uploaded_cv is not None:
        try:
            cv_text = extract_text_from_upload(uploaded_cv.name, uploaded_cv.getvalue())
        except (UnsupportedFileTypeError, ValueError) as exc:
            st.error(str(exc))
            cv_text = ""
    #else:
    #    cv_text = st.text_area("Paste CV text", height=250)

    jd_text = st.text_area("Paste Job Description", height=300)

    if st.button("Analyze Application", type="primary") and cv_text.strip() and jd_text.strip():
        result = pipeline.analyze(
            AnalyzeRequest(
                cv_text=cv_text,
                job_description_text=jd_text,
            )
        )

        tab_input, tab_fit, tab_rewrite, tab_message = st.tabs(
            ["Upload/Input", "Fit Analysis", "CV Improvements", "Outreach Message"]
        )

        with tab_input:
            st.subheader("Parsed CV")
            st.json(result["cv_document"])
            st.subheader("Parsed Job Description")
            st.json(result["job_description"])

        with tab_fit:
            fit = result["fit_analysis"]
            col1, col2 = st.columns(2)
            col1.metric("Overall Fit", fit["overall_fit_score"])
            col2.metric("Estimated ATS Score", fit["estimated_ats_score"])
            st.write("Strong sections:", ", ".join(fit["strong_sections"]) or "None")
            st.write("Weak sections:", ", ".join(fit["weak_sections"]) or "None")
            st.write("Missing keywords:", ", ".join(fit["missing_keywords"]) or "None")
            st.json(fit["editable_recommendations"])

        with tab_rewrite:
            rewrite = result["rewrite_suggestion"]
            skills_change_message = rewrite.get("skills_change_message")
            st.info("Only Summary and Skills are editable. All other CV sections are locked.")
            if rewrite.get("used_llm"):
                st.success("Rewrite mode: Gemini-assisted hybrid rewrite")
            else:
                st.warning(
                    f"Rewrite mode: deterministic fallback"
                    + (
                        f" ({rewrite['fallback_reason']})"
                        if rewrite.get("fallback_reason")
                        else ""
                    )
                )
            st.subheader("Rewritten Summary")
            st.write(rewrite["rewritten_summary"])
            if rewrite["suggested_skills_section"]:
                st.subheader("Suggested Skills Changes")
                for heading, tools in rewrite["suggested_skills_section"].items():
                    st.markdown(f"**{heading}**")
                    for tool in tools:
                        st.markdown(f"- {tool}")
            elif skills_change_message:
                st.subheader("Skills Section")
                st.write(skills_change_message)
            st.metric("Improved ATS Estimate", rewrite["improved_ats_estimate"])
            st.subheader("Evidence")
            st.json(rewrite["evidence_map"])

        with tab_message:
            message = result["linkedin_message"]
            if message.get("used_llm"):
                st.success("Outreach mode: Gemini-assisted message")
            elif message.get("fallback_reason"):
                st.warning(f"Outreach mode: deterministic fallback ({message['fallback_reason']})")
            st.subheader("Hiring Manager Message")
            st.caption("Use the built-in copy icon in the top-right of the message box.")
            st.code(message["hiring_manager_message"], language=None, wrap_lines=True)


if __name__ == "__main__":
    render()
