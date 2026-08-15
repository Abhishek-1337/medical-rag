# Baseline Assist — doctor RAG assistant

A patient-scoped RAG chatbot for clinicians, inspired by the **Baseline** biomarker platform
(`../app`). The doctor searches a patient, opens their chart, and asks questions grounded in
**that patient's exact record** plus a small clinical knowledge base.

Answers are:
- **Grounded** — patient numbers come from structured retrieval over the record (no invented values)
- **Cited** — every answer returns sources (clinical doc titles / result refs) rendered as chips
- **Doctor-facing** — never issues direct patient instructions

## Architecture

```
assistant/
  backend/               Python · FastAPI · openai SDK · chromadb (no framework)
    app/
      main.py            API + SSE streaming · /api/patients · /api/chat · rate limiting
      chat.py            route question → build context → stream LLM answer (one flow)
      tools.py           structured retrieval + trend math (ported from Baseline's generator)
      knowledge.py       knowledge base → chunks → hybrid retrieval (embeddings + BM25) + rerank → Chroma (built at startup)
      data.py            patient dataset load / search / snapshot (in-memory cached)
      llm.py             shared AsyncOpenAI client (chat + embeddings, with timeout)
    data/
      knowledge/*.md     8 clinical docs (LDL, HbA1c, HDL, APOB, trends, flags, guidelines…)
      patients.json      4 demo patients (quarterly panels, summaries + status)
  frontend/              Vite + React + TS (hospital clinical theme)
    /patients            searchable list (name / member id, pending badges)
    /patients/:id        two tabs: Vitals & records (filterable table) + Assistant (scoped chat)
```

**How a chat works** (`chat.py`):
1. Deterministic routing — queue/compare keywords decide which tools run
2. Context = patient trend facts (exact numbers from the record) + summary + queue/compare + top-k knowledge chunks
3. One LLM call, system prompt: *answer only from the context*; tokens stream back over SSE, then `sources`, then `done`

Knowledge retrieval is **hybrid + reranked**: dense embeddings (Chroma) and sparse BM25 over the same
chunks are fused with reciprocal-rank fusion (RRF), then an LLM rerank pass orders the top candidates by
relevance. Keyword-specific queries (e.g. "APOB") and semantic queries both land on the right doc; the
rerank can be disabled with `BASELINE_RERANK=false`.

The UI uses a **hospital clinical theme** — calm white/medical-blue surfaces, IBM Plex type,
pill-shaped actions, a soft ECG pulse in the brand mark, and patient rows styled like wristbands.

## Run it

### Backend (Python 3.11+)

```bash
cd backend
python3.11 -m venv .venv          # or any python3.11/3.12
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # add OPENAI_API_KEY (+ base URL/model if not OpenAI)
.venv/bin/uvicorn app.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5174  (/api proxied → :8000)
```

Open **http://localhost:5174**, search a patient (e.g. `Meera` or `MK-1042`), open the chart, and ask.

### Requirements

- An OpenAI-compatible **API key with chat + embeddings** (OpenAI works out of the box;
  OpenRouter/Groq work by setting `OPENAI_BASE_URL` and model names in `.env`).
- The knowledge index builds into `backend/chroma_db/` at startup (once, idempotent).
- `BASELINE_FAKE_STREAM=true` streams a canned, context-grounded reply without a key — handy
  for testing the SSE pipeline before adding a key.

## Scalability & concurrency

The request path is non-blocking by design:

- **Async embeddings + LLM streaming** — both go through a single shared `AsyncOpenAI` client
  (`llm.py`), so no request creates a client or blocks the event loop.
- **Single Chroma client** — one `PersistentClient` is reused, with all SQLite access serialized
  on a dedicated single-worker executor (`knowledge.py`) so it's safe under concurrency.
- **In-memory patient cache** — `data.py` loads `patients.json` once and reloads only when the
  file's mtime changes.
- **Rate limiting** — `/api/chat` is capped per client IP with a sliding window
  (`CHAT_RATE_LIMIT` requests per `CHAT_RATE_WINDOW` seconds, default `10`/`60`).

Tunables (`.env`):

| Var | Default | Meaning |
| --- | --- | --- |
| `OPENAI_TIMEOUT` | `60` | seconds before OpenAI chat/embedding calls time out |
| `CHAT_RATE_LIMIT` | `10` | max `/api/chat` requests per window, per IP |
| `CHAT_RATE_WINDOW` | `60` | sliding window size in seconds |
| `RERANK_MODEL` | `gpt-4o-mini` | model used for the retrieval rerank pass |
| `BASELINE_RERANK` | `true` | enable/disable the LLM rerank step |

Known limits: the rate limiter and caches are in-memory (per-process), so they don't span
multiple uvicorn workers — fine for one worker, but use Redis/shared state if you scale out.

## Demo prompts

- "Summarize the last 12 months" *(patient scoped)*
- "Any threshold crossings?" *(exact readings)*
- "How should the APOB flag be read here?" *(knowledge + patient)*
- "What is in the review queue?" *(doctor-level, global)*
- "Compare LDL with Ravi Deshmukh" *(side-by-side, exact)*

## Explicitly not in v1

Evaluation harness · reranking · index freshness on write · real auth (no gate) · member scope ·
live Firestore linkup (data is a bundled seed).
