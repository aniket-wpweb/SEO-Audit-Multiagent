"""OSS-friendly embeddings + optional Ollama chat (Task 0.6)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from sentence_transformers import SentenceTransformer


class LLMProvider:
    def __init__(self) -> None:
        model_id = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self._embedder = SentenceTransformer(model_id)
        self._ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self._ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2")
        self._rules_only = os.environ.get("SOP_RULES_ONLY", "0") == "1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._embedder.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    def ollama_json_chat(self, system: str, user: str, timeout: float = 60.0) -> dict[str, Any] | None:
        if self._rules_only:
            return None
        payload = {
            "model": self._ollama_model,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(f"{self._ollama_host}/api/chat", json=payload)
                r.raise_for_status()
                data = r.json()
                content = data["message"]["content"]
                return json.loads(content)
        except Exception:
            return None
