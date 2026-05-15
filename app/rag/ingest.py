"""One-shot SOP ingest from markdown files (called at startup)."""

from pathlib import Path

from app.rag.chroma_store import ChromaSopStore
from app.services.llm_provider import LLMProvider


def sop_dir() -> Path:
    return Path(__file__).resolve().parent / "sop"


def ensure_sop_ingested(store: ChromaSopStore | None = None) -> int:
    st = store or ChromaSopStore(llm=LLMProvider())
    return st.ingest_markdown_dir(sop_dir())
