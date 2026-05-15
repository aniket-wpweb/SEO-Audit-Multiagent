"""Local SOP vector store (numpy + JSON). Avoids native Chroma/hnsw build issues on Windows."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import numpy as np

from app.services.llm_provider import LLMProvider


class ChromaSopStore:
    """Ingest markdown SOP files and run cosine similarity search (workshop-scale)."""

    COLLECTION = "seo_sop_rules"

    def __init__(self, persist_dir: str | None = None, llm: LLMProvider | None = None) -> None:
        base = Path(__file__).resolve().parent.parent.parent
        self._persist = Path(persist_dir or os.environ.get("CHROMA_PERSIST_DIR", ".chroma_data"))
        if not self._persist.is_absolute():
            self._persist = (base / self._persist).resolve()
        self._persist.mkdir(parents=True, exist_ok=True)
        self._llm = llm or LLMProvider()
        self._index_path = self._persist / "sop_index.json"
        self._docs: list[dict] = []
        self._embeddings: np.ndarray | None = None
        self._load()

    def _load(self) -> None:
        if not self._index_path.is_file():
            return
        data = json.loads(self._index_path.read_text(encoding="utf-8"))
        self._docs = data.get("documents", [])
        emb = data.get("embeddings", [])
        self._embeddings = np.array(emb, dtype=np.float32) if emb else None

    def _save(self) -> None:
        payload = {
            "documents": self._docs,
            "embeddings": self._embeddings.tolist() if self._embeddings is not None else [],
        }
        self._index_path.write_text(json.dumps(payload), encoding="utf-8")

    def ingest_markdown_dir(self, directory: Path) -> int:
        ids: list[str] = []
        texts: list[str] = []
        metas: list[dict] = []
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            ids.append(str(uuid.uuid5(uuid.NAMESPACE_URL, str(path))))
            texts.append(text)
            metas.append({"source": path.name})
        if not texts:
            self._docs = []
            self._embeddings = None
            self._save()
            return 0
        embs = np.array(self._llm.embed(texts), dtype=np.float32)
        self._docs = [{"id": ids[i], "text": texts[i], "metadata": metas[i]} for i in range(len(ids))]
        self._embeddings = embs
        self._save()
        return len(texts)

    def similarity_search(self, query: str, k: int = 3) -> list[dict]:
        if not self._docs or self._embeddings is None:
            return []
        q = np.array(self._llm.embed([query]), dtype=np.float32)[0]
        mat = self._embeddings
        norms = np.linalg.norm(mat, axis=1) * np.linalg.norm(q)
        sims = (mat @ q) / np.clip(norms, 1e-9, None)
        idx = np.argsort(-sims)[:k]
        out: list[dict] = []
        for i in idx:
            d = self._docs[int(i)]
            out.append({"text": d["text"], "metadata": d.get("metadata", {}), "distance": float(1.0 - sims[int(i)])})
        return out
