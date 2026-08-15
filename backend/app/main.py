"""Baseline Assist — FastAPI entry point."""
import asyncio
import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from . import chat, data, knowledge

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if chat.has_llm_key():
        await asyncio.to_thread(knowledge.build_index)
    yield


app = FastAPI(title="Baseline Assist", version="1.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = (os.getenv("ALLOWED_ORIGINS") or "http://localhost:5174,http://127.0.0.1:5174").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    patientId: str | None = None
    history: list[dict] = Field(default_factory=list)


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
async def chat_endpoint(req: ChatRequest):
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
