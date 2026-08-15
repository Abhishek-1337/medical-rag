"""Knowledge base: Markdown docs → chunks → embeddings → Chroma (built at startup)."""
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"
CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", "../chroma_db")).resolve()
COLLECTION = "baseline_knowledge"


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


_client: OpenAI | None = None


def _embeddings(texts: list[str]) -> list[list[float]]:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or None)
    res = _client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"), input=texts
    )
    return [d.embedding for d in res.data]


def build_index() -> None:
    """Build the knowledge index once (idempotent — safe to call on every startup)."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = client.get_or_create_collection(COLLECTION)
    if col.count() > 0:
        return
    chunks = _load_chunks()
    col.add(
        ids=[f"{stem}-{i}" for i, (_, _, stem) in enumerate(chunks)],
        documents=[c for c, _, _ in chunks],
        metadatas=[{"title": title, "source": stem} for _, title, stem in chunks],
        embeddings=_embeddings([c for c, _, _ in chunks]),
    )
    print(f"built knowledge index ({len(chunks)} chunks) at {CHROMA_DIR}")


def _collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(COLLECTION)


def search_knowledge(query: str, k: int = 4) -> list[dict]:
    """Top-k chunks for the query: [{text, title, source, score}]."""
    col = _collection()
    res = col.query(query_embeddings=_embeddings([query]), n_results=k, include=["documents", "metadatas", "distances"])
    out = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"text": text, "title": meta["title"], "source": meta["source"], "score": round(dist, 4)})
    return out
