"""AI diagnostic assistant: semantic search over the fault library and confirmed past cases.

Default backend "hybrid": ranks by an equal blend of BAAI/bge-small-en-v1.5 sentence embeddings
(open weights, CPU) and TF-IDF keyword similarity; confidence comes from the raw embedding cosine.
"bge" uses embeddings only. "tfidf" needs no model and is the automatic fallback.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

import numpy as np
from django.conf import settings

log = logging.getLogger(__name__)

MIN_CHARS, MAX_CHARS = 10, 1000
TOP_K = 3
# Below this cosine similarity the assistant says it is not confident instead of guessing.
MIN_SCORE = {"hybrid": 0.55, "bge": 0.55, "tfidf": 0.08}
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class AssistantError(ValueError):
    """Invalid input. The message is safe to show to users."""


def clean_query(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) < MIN_CHARS:
        raise AssistantError(f"Describe the symptoms in at least {MIN_CHARS} characters.")
    if len(text) > MAX_CHARS:
        raise AssistantError(f"Keep the description under {MAX_CHARS} characters.")
    if len(re.findall(r"[a-zA-Z]{3,}", text)) < 2:
        raise AssistantError("Use words to describe what you observed, for example 'supply air too warm'.")
    return text


@lru_cache(maxsize=1)
def _bge_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.AI_EMBEDDING_MODEL, device="cpu")


def backend_name() -> str:
    if settings.AI_EMBEDDINGS not in ("hybrid", "bge"):
        return "tfidf"
    try:
        _bge_model()
        return settings.AI_EMBEDDINGS
    except Exception:  # missing package, no network on first download, out of memory
        log.exception("Embedding model unavailable, falling back to TF-IDF")
        return "tfidf"


def warm_up():
    """Load the model ahead of the first request (cold load measured at about 10 s)."""
    if backend_name() != "tfidf":
        _similarities("warm up query", ["warm up document"], "bge")


def _minmax(x: np.ndarray) -> np.ndarray:
    return (x - x.min()) / (x.max() - x.min() + 1e-9)


def _rank(query: str, docs: list[str], backend: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (ranking scores, confidence scores) for each document."""
    if backend == "hybrid":
        emb = _similarities(query, docs, "bge")
        return 0.5 * _minmax(emb) + 0.5 * _minmax(_similarities(query, docs, "tfidf")), emb
    sims = _similarities(query, docs, backend)
    return sims, sims


def _similarities(query: str, docs: list[str], backend: str) -> np.ndarray:
    if backend == "bge":
        model = _bge_model()
        q = model.encode([QUERY_PREFIX + query], normalize_embeddings=True)
        d = model.encode(docs, normalize_embeddings=True)
        return (d @ q.T).ravel()
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    m = vec.fit_transform(docs + [query])
    return (m[:-1] @ m[-1].T).toarray().ravel()


def diagnose(query: str, faults: list[dict], cases: list[dict]) -> dict:
    """Rank fault library entries and similar confirmed cases for a symptom description.

    faults: dicts with code, name, symptoms, causes, checks. cases: dicts with id, label, notes.
    """
    query = clean_query(query)
    if not faults:
        raise AssistantError("The fault library is empty. Run the seed command first.")
    backend = backend_name()
    docs = [f"{f['name']}. {f['symptoms']} Causes: {f['causes']}" for f in faults]
    case_docs = [f"{c['label']}. {c['notes']}" for c in cases]
    try:
        rank, conf = _rank(query, docs + case_docs, backend)
    except Exception:
        if backend == "tfidf":
            raise
        log.exception("Embedding inference failed, retrying with TF-IDF")
        backend = "tfidf"
        rank, conf = _rank(query, docs + case_docs, backend)

    n = len(docs)
    matches = [
        {"code": faults[i]["code"], "name": faults[i]["name"], "score": round(float(conf[i]), 3),
         "checks": faults[i]["checks"]}
        for i in np.argsort(-rank[:n])[:TOP_K]
    ]
    similar = [
        {"id": cases[i]["id"], "label": cases[i]["label"], "score": round(float(conf[n + i]), 3)}
        for i in np.argsort(-rank[n:])[:TOP_K]
        if conf[n + i] >= MIN_SCORE[backend]
    ]
    confident = matches[0]["score"] >= MIN_SCORE[backend]
    return {"backend": backend, "confident": bool(confident), "matches": matches, "similar_cases": similar}
