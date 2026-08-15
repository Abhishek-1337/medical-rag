"""Baseline Assist — FastAPI entry point."""
import json
import os
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sse_starlette.sse import EventSourceResponse

from . import chat, data, knowledge

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if chat.has_llm_key():
        await knowledge.build_index()
    yield


app = FastAPI(title="Baseline Assist", version="1.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = (os.getenv("ALLOWED_ORIGINS") or "http://localhost:5174,http://127.0.0.1:5174").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


ALLOWED_HISTORY_ROLES = {"user", "assistant"}
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CONTENT = 2000
_PATIENT_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    patientId: str | None = None
    history: list[dict] = Field(default_factory=list)

    @field_validator("patientId")
    @classmethod
    def _check_patient_id(cls, v: str | None) -> str | None:
        if v is not None and not _PATIENT_ID_RE.fullmatch(v):
            raise ValueError("patientId must be alphanumeric with hyphens (<=64 chars)")
        return v

    @field_validator("history", mode="before")
    @classmethod
    def _sanitize_history(cls, v):
        if not isinstance(v, list):
            return []
        clean: list[dict] = []
        for m in v[:MAX_HISTORY_MESSAGES]:
            if not isinstance(m, dict):
                continue
            role = m.get("role") if m.get("role") in ALLOWED_HISTORY_ROLES else "user"
            content = m.get("content")
            if not isinstance(content, str):
                content = ""
            clean.append({"role": role, "content": content[:MAX_HISTORY_CONTENT]})
        return clean


CHAT_RATE_LIMIT = int(os.getenv("CHAT_RATE_LIMIT", "10"))
CHAT_RATE_WINDOW = float(os.getenv("CHAT_RATE_WINDOW", "60"))
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(key: str) -> bool:
    now = time.monotonic()
    dq = _hits[key]
    while dq and dq[0] <= now - CHAT_RATE_WINDOW:
        dq.popleft()
    if len(dq) >= CHAT_RATE_LIMIT:
        return True
    dq.append(now)
    return False


@app.get("/api/health")
def health():
    return {"ok": True, "llmConfigured": chat.has_llm_key(), "fakeStream": chat.FAKE_STREAM}


@app.get("/api/patients")
def list_patients(q: str | None = None):
    return [data.list_summary(p) for p in data.search_patients(q)]


@app.get("/api/patients/{patient_id}")
def patient_detail(patient_id: str):
    p = data.get_patient(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="patient not found")
    return data.patient_snapshot(p)


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload)}


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    if _rate_limited(request.client.host if request.client else "unknown"):
        return JSONResponse(status_code=429, content={"error": "rate limit exceeded, try again shortly"})
    if not chat.has_llm_key() and not chat.FAKE_STREAM:
        return JSONResponse(
            status_code=503,
            content={
                "error": "OPENAI_API_KEY is not set. Add it to backend/.env (or set BASELINE_FAKE_STREAM=true to test streaming without a key)."
            },
        )

    async def gen():
        try:
            async for item in chat.stream_answer(req.message, req.patientId, req.history):
                t = item["type"]
                if t == "token":
                    yield _sse("token", {"text": item["text"]})
                elif t == "chart":
                    yield _sse("chart", {"chart": item["chart"]})
                elif t == "sources":
                    yield _sse("sources", {"sources": item["sources"]})
                elif t == "error":
                    yield _sse("error", {"message": item["message"]})
                else:
                    yield _sse("done", {})
        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return EventSourceResponse(gen())
