
# job-applier

# ApplyAI

ApplyAI is a greenfield MVP for optimizing job applications. It parses a CV and job description, scores role fit and ATS alignment, suggests grounded improvements to the `Summary` and `Skills` sections only, and generates outreach messages.

## Project layout

- `backend/`: pipeline logic, storage adapter, and FastAPI app
- `frontend/`: Streamlit MVP
- `shared/`: common models and DTO conversion helpers
- `tests/`: unit tests for parser, scoring, and rewrite safety

## Run locally

1. Install dependencies: `python3 -m pip install -e .`
2. Start the API: `uvicorn backend.app:app --reload`
3. Start the frontend: `streamlit run frontend/app.py`
4. Run tests: `python3 -m unittest discover -s tests -v`

## Notes

- The core pipeline is deterministic-first and dependency-light.
- LLM integration points are isolated behind a provider client so Gemini-backed rewriting can fall back safely when no API key is configured.
- Only `Summary` and `Skills` are editable outputs. All other CV sections are locked.
>>>>>>> 71f2376 (Initial commit)
