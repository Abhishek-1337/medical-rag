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
      main.py            API + SSE streaming · /api/patients · /api/chat
      chat.py            route question → build context → stream LLM answer (one flow)
      tools.py           structured retrieval + trend math (ported from Baseline's generator)
      knowledge.py       knowledge base → chunks → embeddings → Chroma (built lazily)
      data.py            patient dataset load / search / snapshot
    data/
      knowledge/*.md     8 clinical docs (LDL, HbA1c, HDL, APOB, trends, flags, guidelines…)
      patients.json      4 demo patients (quarterly panels, summaries + status)
  frontend/              Vite + React + TS (hospital clinical theme)
    /patients            searchable list (name / member id, pending badges)
    /patients/:id        two tabs: Vitals & records (filterable table) + Assistant (scoped chat)
```

**How a chat works** (`chat.py`, ~90 lines):
1. Deterministic routing — queue/compare keywords decide which tools run
2. Context = patient trend facts (exact numbers from the record) + summary + queue/compare + top-k knowledge chunks
3. One LLM call, system prompt: *answer only from the context*; tokens stream back over SSE, then `sources`, then `done`

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
- On first chat the knowledge index builds into `backend/chroma_db/` automatically.
- `BASELINE_FAKE_STREAM=true` streams a canned, context-grounded reply without a key — handy
  for testing the SSE pipeline before adding a key.

## Demo prompts

- "Summarize the last 12 months" *(patient scoped)*
- "Any threshold crossings?" *(exact readings)*
- "How should the APOB flag be read here?" *(knowledge + patient)*
- "What is in the review queue?" *(doctor-level, global)*
- "Compare LDL with Ravi Deshmukh" *(side-by-side, exact)*

## Explicitly not in v1

Evaluation harness · reranking · index freshness on write · real auth (no gate) · member scope ·
live Firestore linkup (data is a bundled seed).
