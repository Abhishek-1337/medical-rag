"""Chat: route the question, gather grounded context, stream the answer.

One flow, no framework: deterministic routing → context (patient facts + knowledge
retrieval) → single LLM call that must answer from the context only.
"""
import asyncio
import os
from typing import AsyncGenerator

from dotenv import load_dotenv

from . import tools
from .data import get_patient, load_patients
from .knowledge import search_knowledge
from .llm import get_client

load_dotenv()

FAKE_STREAM = os.getenv("BASELINE_FAKE_STREAM", "false").lower() in ("1", "true", "yes")

SYSTEM_PROMPT = """You are Baseline Assist, a decision-support assistant for a doctor reviewing
longitudinal biomarker data.

Rules:
1. Answer ONLY from the CONTEXT below. Never invent values, dates, or findings.
2. Ground every number with its date and unit. If a fact is not in the context, say you don't have it.
3. Doctor-facing tone. Never issue a direct instruction to a patient.
4. Be concise — under 180 words unless asked for detail."""


def has_llm_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


_ALLOWED_ROLES = {"user", "assistant"}


def _sanitize_history(history: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for m in (history or [])[-8:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role") if m.get("role") in _ALLOWED_ROLES else "user"
        content = m.get("content")
        if not isinstance(content, str):
            content = ""
        out.append({"role": role, "content": content})
    return out


def _resolve(patient_id: str | None) -> str | None:
    """Accept internal id or member id (e.g. MK-1042)."""
    if not patient_id:
        return None
    for p in load_patients():
        if p["id"] == patient_id or p["memberId"].lower() == patient_id.lower():
            return p["id"]
    return None


async def build_context(message: str, patient_id: str | None) -> tuple[str, list[dict], dict | None]:
    """Deterministic retrieval: returns (context_text, sources, chart)."""
    lowered = message.lower()
    parts: list[str] = []
    sources: list[dict] = []
    chart = None
    pid = _resolve(patient_id)

    if "queue" in lowered or "pending" in lowered:
        text, src = tools.queue_facts()
        parts.append(text)
        sources += src

    if "compare" in lowered or " vs " in lowered:
        biomarker = next((t for t in ("LDL", "HbA1c", "HDL") if t in message), "LDL")
        patients = [p for p in load_patients() if not pid or p["id"] == pid]
        if len(patients) >= 2:
            text, src = tools.compare_facts(patients, biomarker)
            parts.append(text)
            sources += src

    if pid and (patient := get_patient(pid)):
        if any(w in lowered for w in ("graph", "chart", "plot", "visualize")) or (
            "show" in lowered and "trend" in lowered
        ):
            biomarker = next((t for t in ("LDL", "HbA1c", "HDL") if t in message), None)
            chart = tools.chart_facts(patient, biomarker)
        text, src = tools.patient_facts(patient)
        parts.append(text)
        sources += src
        text, src = tools.summary_facts(patient)
        parts.append(text)
        sources += src

    try:
        chunks = await search_knowledge(message)
        if chunks:
            parts.append("\n".join(f"From '{c['title']}':\n{c['text']}" for c in chunks))
            sources += [{"type": "knowledge", "label": c["title"], "source": c["source"]} for c in chunks]
    except Exception as e:  # index or key missing — patient facts still answer
        parts.append(f"(clinical knowledge unavailable: {e})")

    return "\n\n".join(parts), sources, chart


def _fake_reply(context: str) -> str:
    bullets = [l.strip() for l in context.splitlines() if l.strip().startswith(("- ", "**", "From '"))][:3]
    return (
        "Streaming test — BASELINE_FAKE_STREAM=true is on (add OPENAI_API_KEY for real answers). "
        "Grounded in the retrieved context: " + " ".join(bullets)
    )


async def stream_answer(
    message: str, patient_id: str | None, history: list[dict]
) -> AsyncGenerator[dict, None]:
    context, sources, chart = await build_context(message, patient_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _sanitize_history(history)
    messages.append({"role": "system", "content": f"CONTEXT:\n{context}"})
    messages.append({"role": "user", "content": message})

    if FAKE_STREAM:
        for word in _fake_reply(context).split(" "):
            yield {"type": "token", "text": word + " "}
            await asyncio.sleep(0.015)
        if chart:
            yield {"type": "chart", "chart": chart}
        yield {"type": "sources", "sources": sources}
        yield {"type": "done"}
        return

    try:
        client = get_client()
        stream = await client.chat.completions.create(
            model=os.getenv("CHAT_MODEL", "gpt-4o-mini"), messages=messages, stream=True
        )
        async for chunk in stream:
            text = chunk.choices[0].delta.content or ""
            if text:
                yield {"type": "token", "text": text}
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return
    if chart:
        yield {"type": "chart", "chart": chart}
    yield {"type": "sources", "sources": sources}
    yield {"type": "done"}
