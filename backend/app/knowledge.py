"""Knowledge base: Markdown docs → chunks → embeddings → Chroma (built at startup)."""
import asyncio
import os
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

_chroma_client = None
_chroma_pool: ThreadPoolExecutor | None = None


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
    return col.query(
        query_embeddings=query_embeddings, n_results=k, include=["documents", "metadatas", "distances"]
    )


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


async def search_knowledge(query: str, k: int = 4) -> list[dict]:
    """Top-k chunks for the query: [{text, title, source, score}]."""
    query_embeddings = await _embeddings([query])
    res = await _run_chroma(_query_sync, query_embeddings, k)
    out = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"text": text, "title": meta["title"], "source": meta["source"], "score": round(dist, 4)})
    return out
