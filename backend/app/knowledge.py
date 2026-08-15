"""Knowledge base: Markdown docs → chunks → hybrid retrieval (dense + sparse) → rerank → Chroma."""
import asyncio
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

import chromadb
from dotenv import load_dotenv

from .llm import get_client

load_dotenv()

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"
CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", "../chroma_db")).resolve()
COLLECTION = "baseline_knowledge"
RERANK_MODEL = os.getenv("RERANK_MODEL", os.getenv("CHAT_MODEL", "gpt-4o-mini"))

_chroma_client = None
_chroma_pool: ThreadPoolExecutor | None = None
_chunks_cache: list[tuple[str, str, str]] | None = None
_id_to_index: dict[str, int] | None = None
_bm25: "_BM25 | None" = None


def _chunk(text: str, size: int = 650) -> list[str]:
    """Paragraph-aware splitter. Docs are short, so this is plenty."""
    parts: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        if current and len(current) + len(para) > size:
            parts.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        parts.append(current.strip())
    return parts


def _load_chunks() -> list[tuple[str, str, str]]:
    """(chunk_text, title, source) for every chunk across the docs."""
    out: list[tuple[str, str, str]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        title = path.stem.replace("-", " ").title()
        for chunk in _chunk(path.read_text(encoding="utf-8")):
            out.append((chunk, title, path.stem))
    return out


def _chunks() -> list[tuple[str, str, str]]:
    global _chunks_cache, _id_to_index
    if _chunks_cache is None:
        _chunks_cache = _load_chunks()
        _id_to_index = {f"{stem}-{i}": i for i, (_, _, stem) in enumerate(_chunks_cache)}
    return _chunks_cache


def _chunk_index(chunk_id: str) -> int:
    _chunks()
    return _id_to_index[chunk_id]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class _BM25:
    """Minimal BM25 (sparse/lexical) scorer over the in-memory chunk corpus."""

    def __init__(self, corpus: list[list[str]]):
        self.corpus = corpus
        self.n = len(corpus)
        self.doc_len = [len(d) for d in corpus]
        self.avgdl = sum(self.doc_len) / self.n if self.n else 0.0
        self.k1 = 1.5
        self.b = 0.75
        df: dict[str, int] = {}
        self.doc_freqs: list[dict[str, int]] = []
        for doc in corpus:
            freqs: dict[str, int] = {}
            for w in doc:
                freqs[w] = freqs.get(w, 0) + 1
            self.doc_freqs.append(freqs)
            for w in freqs:
                df[w] = df.get(w, 0) + 1
        self.idf = {w: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def score(self, query: list[str]) -> list[float]:
        scores: list[float] = []
        for i in range(self.n):
            freqs = self.doc_freqs[i]
            s = 0.0
            for w in query:
                f = freqs.get(w)
                if not f:
                    continue
                idf = self.idf[w]
                s += idf * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                )
            scores.append(s)
        return scores


def _get_bm25() -> _BM25:
    global _bm25
    if _bm25 is None:
        _bm25 = _BM25([_tokenize(c) for c, _, _ in _chunks()])
    return _bm25


async def _embeddings(texts: list[str]) -> list[list[float]]:
    res = await get_client().embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"), input=texts
    )
    return [d.embedding for d in res.data]


def _get_chroma_client():
    """Singleton client, created/used only on the dedicated chroma thread."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def _pool() -> ThreadPoolExecutor:
    """Single-worker executor: serializes Chroma (SQLite) access on one thread."""
    global _chroma_pool
    if _chroma_pool is None:
        _chroma_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chroma")
    return _chroma_pool


def _run_chroma(fn, *args):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(_pool(), partial(fn, *args))


def _index_exists() -> bool:
    return _get_chroma_client().get_or_create_collection(COLLECTION).count() > 0


def _add_sync(embeddings, ids, documents, metadatas):
    col = _get_chroma_client().get_or_create_collection(COLLECTION)
    col.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    return len(documents)


def _query_sync(query_embeddings, k):
    col = _get_chroma_client().get_or_create_collection(COLLECTION)
    return col.query(query_embeddings=query_embeddings, n_results=k)


async def build_index() -> None:
    """Build the knowledge index once (idempotent — safe to call on every startup)."""
    if await _run_chroma(_index_exists):
        return
    chunks = _load_chunks()
    embeddings = await _embeddings([c for c, _, _ in chunks])
    n = await _run_chroma(
        _add_sync,
        embeddings,
        [f"{stem}-{i}" for i, (_, _, stem) in enumerate(chunks)],
        [c for c, _, _ in chunks],
        [{"title": title, "source": stem} for _, title, stem in chunks],
    )
    print(f"built knowledge index ({n} chunks) at {CHROMA_DIR}")


async def search_knowledge(query: str, k: int = 4, rerank: bool = True) -> list[dict]:
    """Hybrid retrieval + optional rerank.

    Reciprocal-rank fusion of dense (embeddings) + sparse (BM25), then an LLM rerank
    over the fused candidates. Returns [{text, title, source, score}] where score is
    the fused RRF value (higher = better).
    """
    chunks = _chunks()
    if not chunks:
        return []

    pool = max(k * 3, min(12, len(chunks)))
    query_embeddings = await _embeddings([query])
    res = await _run_chroma(_query_sync, query_embeddings, pool)
    dense_rank = [_chunk_index(i) for i in res["ids"][0]]

    sparse_scores = _get_bm25().score(_tokenize(query))
    sparse_rank = sorted(range(len(sparse_scores)), key=lambda j: sparse_scores[j], reverse=True)[:pool]

    fused: dict[int, float] = {}
    for rank, j in enumerate(dense_rank):
        fused[j] = fused.get(j, 0.0) + 1.0 / (60 + rank + 1)
    for rank, j in enumerate(sparse_rank):
        fused[j] = fused.get(j, 0.0) + 1.0 / (60 + rank + 1)

    top = sorted(fused, key=fused.get, reverse=True)[:pool]
    candidates = [
        {"text": chunks[j][0], "title": chunks[j][1], "source": chunks[j][2], "score": round(fused[j], 4)}
        for j in top
    ]

    if rerank and _can_rerank():
        candidates = await _rerank(query, candidates)

    return candidates[:k]


def _can_rerank() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and os.getenv("BASELINE_RERANK", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _parse_rank_order(content: str, n: int) -> list[int]:
    """Parse a JSON array of integers from the model; fall back to identity order."""
    m = re.search(r"\[[^\]]*\]", content)
    nums = [int(x) for x in re.findall(r"\d+", m.group(0))] if m else []
    order: list[int] = []
    seen: set[int] = set()
    for x in nums:
        if 1 <= x <= n and x not in seen:
            order.append(x)
            seen.add(x)
    for x in range(1, n + 1):
        if x not in seen:
            order.append(x)
    return order


async def _rerank(query: str, candidates: list[dict]) -> list[dict]:
    """LLM cross-encoder-style rerank: reorder candidates by relevance to the query.

    Falls back to the input (RRF) order on any error so retrieval never hard-fails.
    """
    if len(candidates) <= 1:
        return candidates
    numbered = "\n".join(f"[{i + 1}] {c['text']}" for i, c in enumerate(candidates))
    prompt = (
        "You are a retrieval reranker. Rank the passages below by relevance to the query. "
        "Return ONLY a JSON array of passage numbers in descending order of relevance, "
        "including every number exactly once.\n\n"
        f"Query: {query}\n\nPassages:\n{numbered}\n\n"
        "Ranked order (JSON array of integers):"
    )
    try:
        res = await get_client().chat.completions.create(
            model=RERANK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = res.choices[0].message.content or ""
        order = _parse_rank_order(content, len(candidates))
    except Exception:
        return candidates
    return [candidates[i - 1] for i in order if 1 <= i <= len(candidates)]
