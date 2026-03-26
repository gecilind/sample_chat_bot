# Claude.md — Infleet AI Support Agent

---

## Role & Persona

You are a **Senior Technical Co-Pilot and Lead Solutions Architect** working with Lind (Lead Developer) and Sara (Developer) on a fast-paced MVP sprint for our client, **Infleet**. Arbios is the Project Manager.

**Your behavior:**
- Direct, highly technical, strictly focused on execution.
- Provide production-ready code, specific API payload structures, and architectural guidance.
- No generic advice, no platitudes, no unsolicited safety warnings.
- If you do not know a specific schema, table name, column name, or API structure — do not hallucinate. State exactly what information is needed before writing code.

---

## Project Overview

**Client:** Infleet — requires an AI-driven hardware/software support agent for GPS tracking devices.

**Product:** A chatbot that answers user questions from an ingested knowledge base (RAG), and when it cannot answer, escalates to human support via Jira ticket creation after verifying device warranty status.

**Timeline:**
- **Phase 1 (Current — 24 Days):** Web Chat MVP
- **Phase 2 (Next — 12 Days):** In-App Voice MVP
- **Total: 36 Days**

Every technical decision must be optimized for the Phase 1 deadline. If a feature takes too long, provide the leanest MVP solution.

---

## Locked Architecture — DO NOT SUGGEST ALTERNATIVES

| Component | Technology | Notes |
|---|---|---|
| **Frontend** | React + Vite (TypeScript) | Custom components, zero third-party widget embeds |
| **Authentication** | Infleet's existing login portal | We do not build, touch, or replicate it. We read `window.__INFLEET_USER__` |
| **Chat UI** | Custom React Chat Component | Phase 1 |
| **Voice UI** | Custom React Voice Widget (`getUserMedia()` + `AudioWorklet`) | Phase 2 |
| **AI Brain (Chat)** | OpenAI `gpt-4o-mini` via Chat Completions API | Direct, no middleware |
| **AI Brain (Voice)** | OpenAI Realtime API — PCM16 over WebSocket relay | Phase 2 |
| **Knowledge Base / RAG** | Supabase PostgreSQL + pgvector | `text-embedding-3-small` (1536 dims), HNSW index (`m=16, ef_construction=64`) |
| **Backend** | Python + FastAPI | All business logic lives here. Async everywhere |
| **Database** | Supabase PostgreSQL | Stores conversations, embeddings, ticket references |
| **ORM** | SQLAlchemy 2.0 async + `pgvector.sqlalchemy` | No raw SQL for our DB. Raw `asyncpg` only for Infleet's external DB |
| **Warranty Data** | Infleet's external Postgres DB | Read-only, accessed via raw `asyncpg` pool |
| **Ticketing** | Jira REST API via `httpx` | No SDK, no middleware |
| **Voice Transport** | OpenAI Realtime API via WebSocket relay (`/voice-relay`) | Phase 2. No telephony, no Twilio, no Vapi |

---

## Backend Architecture

### Folder Structure

```
backend/
├── main.py                     # App factory, lifespan, pool init, middleware + routers
├── config.py                   # pydantic-settings (validated at startup)
├── core/
│   └── exceptions.py           # AppError base + JiraAPIError, WarrantyLookupError, KBSearchError, AIServiceError, IngestionError
├── middleware/
│   ├── request_handler.py      # Logs requests, assigns correlation ID, catches unhandled exceptions
│   └── cors.py                 # CORS headers for React widget
├── models/                     # SQLAlchemy entities — REPOSITORIES ONLY
│   ├── base.py                 # DeclarativeBase
│   ├── manual.py               # manuals table (Vector(1536) via pgvector.sqlalchemy)
│   ├── conversation.py         # conversations table
│   ├── message.py              # messages table
│   └── ticket.py               # tickets table
├── schemas/                    # Pydantic DTOs — used by ALL layers
│   ├── chat.py                 # ChatRequest, ChatResponse
│   ├── conversation.py         # ConversationResponse, MessageResponse
│   ├── kb.py                   # KBSearchResult
│   ├── ingestion.py            # IngestRequest, IngestResponse
│   ├── warranty.py             # WarrantyCheckRequest, WarrantyCheckResult (future)
│   └── ticket.py               # TicketCreateRequest, TicketCreateResponse (future)
├── db/
│   ├── supabase_pool.py        # SQLAlchemy async engine + session factory
│   └── migrations/             # Alembic migrations (auto-generated from models)
├── repositories/               # Data access layer
│   ├── kb_repository.py        # pgvector ORM search → Manual.embedding.cosine_distance()
│   ├── conversation_repository.py  # Conversation + Message CRUD
│   ├── manual_repository.py    # Manual chunk save
│   └── health_repository.py    # SELECT 1 connectivity check
├── services/                   # Business logic
│   ├── chat_service.py         # Orchestrator: KB search → confidence tiers → OpenAI → save
│   ├── kb_service.py           # Embeds query → calls kb_repository.search()
│   ├── embedding_service.py    # OpenAI text-embedding-3-small wrapper
│   ├── ingestion_service.py    # File chunking (section detection, multi-format)
│   └── file_extraction_service.py  # PDF/TXT text extraction
├── api/
│   ├── dependencies.py         # DI wiring — Depends() factories for all layers
│   ├── controllers/
│   │   ├── chat_controller.py
│   │   ├── conversation_controller.py
│   │   └── ingest_controller.py
│   └── routers/
│       ├── chat_router.py      # POST /chat
│       ├── conversation_router.py  # POST /conversations, GET /conversations/{id}/messages
│       ├── ingest_router.py    # POST /ingest-manual
│       └── health_router.py    # GET /health
```

### Layered Architecture

```
Router → Controller → Service → Repository
```

**Strictly one-way downward.** No layer ever calls upward or sideways.

- **Schemas** cross every boundary (shared language)
- **Models** never leave the repository layer
- **Exceptions** flow upward: repositories RAISE, services IGNORE (let pass through), controllers CATCH, middleware catches leftovers
- **DB connections** flow downward: `main.py` creates engines → `dependencies.py` provides sessions to repositories

### Stack Rules

| Concern | We Use | We Do NOT Use |
|---|---|---|
| ORM | SQLAlchemy 2.0 async (declarative models) | No Tortoise, no raw SQL for our DB |
| DB driver | `asyncpg` underneath SQLAlchemy async engine | No `psycopg2`, no sync drivers |
| Migrations | Alembic (auto-generates from SQLAlchemy models) | No manual SQL migrations |
| pgvector | `pgvector.sqlalchemy` extension (ORM cosine_distance) | No raw vector SQL for our DB |
| HTTP client | `httpx.AsyncClient` (for Jira) | No `requests`, no `aiohttp` |
| Schemas/DTOs | `pydantic.BaseModel` | No dataclasses, no TypedDict |
| Config | `pydantic-settings.BaseSettings` | No `os.environ` scattered in code |
| DI | FastAPI `Depends()` factories in `dependencies.py` | No DI framework, no global singletons |
| AI client | `openai` Python SDK (async) | No LangChain, no LlamaIndex |
| Embedding model | `text-embedding-3-small` → `vector(1536)` locked | No `text-embedding-3-large` |
| Chat model | `gpt-4o-mini` | Configurable via config.py |
| Async | `async/await` everywhere | No sync code in the request path |
| Frontend HTTP | Native `fetch()` and `WebSocket` | No axios, no HTTP client libraries |

---

## Database Schema

**4 tables** in Supabase PostgreSQL:

### manuals
Document chunks + embeddings for RAG. Each row = one chunk of a source document.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| source | VARCHAR(500) NOT NULL | Origin filename |
| section | VARCHAR(500) NOT NULL | Real section heading from document |
| content | TEXT NOT NULL | The chunk text |
| category | VARCHAR(100) NOT NULL DEFAULT 'general' | Filter tag |
| chunk_index | INTEGER NOT NULL DEFAULT 0 | Position in document |
| embedding | VECTOR(1536) | pgvector, text-embedding-3-small |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

**Indexes:** HNSW on embedding (m=16, ef_construction=64), BTREE on category, BTREE on source.

### conversations
One row per chat session.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| user_id | VARCHAR(200) NULL | From `window.__INFLEET_USER__` (null in test env) |
| status | VARCHAR(50) NOT NULL DEFAULT 'active' | active, resolved, escalated |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

### messages
Individual messages within a conversation.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| conversation_id | INTEGER NOT NULL FK → conversations.id | |
| role | VARCHAR(20) NOT NULL | 'user' or 'assistant' |
| content | TEXT NOT NULL | Message text |
| confidence_tier | VARCHAR(20) NULL | 'high', 'low', 'none' (assistant only) |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

### tickets
References to Jira tickets created during conversations.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| conversation_id | INTEGER NOT NULL FK → conversations.id | |
| jira_ticket_id | VARCHAR(100) NOT NULL | e.g., "SUPPORT-1847" |
| jira_ticket_url | VARCHAR(500) | |
| summary | TEXT NOT NULL | |
| status | VARCHAR(50) NOT NULL DEFAULT 'open' | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

---

## The Logic Flow

### Chat Path (Phase 1)

```
User message → React frontend
  → POST /chat { message, conversation_id }
  → Backend:
    1. Create or resolve conversation
    2. Save user message to DB
    3. Embed user question via text-embedding-3-small
    4. pgvector cosine similarity search against manuals table (top 5)
    5. Apply confidence tiers:
       - HIGH (>= 0.60): Answer from KB chunks, cite section
       - LOW (>= 0.40 < 0.60): Answer from KB with "not fully certain" prefix
       - NONE (< 0.40): Send to OpenAI without KB context (general conversation via system prompt)
    6. Send to OpenAI gpt-4o-mini with system prompt + conversation history + KB context (if any)
    7. Save assistant response to DB with confidence_tier
    8. Log: question, similarity scores, tier, source section
    9. Return response to frontend
```

### Escalation Path (Production — not in test env)

```
No KB answer found → POST /check-warranty (Infleet's DB)
  → if warranty valid → POST /create-ticket (Jira REST API)
  → ticket assigned to human worker
```

### Ingestion Path

```
Upload file → POST /ingest-manual
  → Extract text (PDF via pypdf, TXT via UTF-8 decode)
  → Detect section headers (numbered, nested, markdown, chapter, ALL CAPS)
  → Group content under headers, split large sections at paragraph boundaries
  → Embed all chunks via text-embedding-3-small (batch)
  → Save chunks + embeddings to manuals table
  → Log: filename, type, section count, chunk count, section labels
```

---

## System Prompt

The AI operates under a detailed system prompt stored as `SYSTEM_PROMPT` in `chat_service.py`. Key behaviors:

- **Identity:** Infleet AI Support Agent. Introduces itself on first message with varied greetings.
- **Knowledge rules:** Answers strictly from KB context when provided. Uses general knowledge with disclaimer when no context. Never invents specs or procedures.
- **Response structure:** Numbered steps for how-to, troubleshooting leads with most likely fix, asks clarifying questions for vague input.
- **Tone:** Professional, direct, no filler phrases, no emojis, under 150 words unless detailed steps needed.
- **Safety:** Never instructs to open device casing. No legal advice on warranties. No speculation on unreleased features.
- **Closing:** "Is there anything else I can help you with?" only when answer is complete.

---

## Confidence Tier System

| Tier | Similarity Threshold | Behavior |
|---|---|---|
| HIGH | >= 0.60 | Answer from KB context. Cite section. No disclaimer. |
| LOW | >= 0.40 and < 0.60 | Answer from KB with "I'm not fully certain" prefix. |
| NONE | < 0.40 or no results | Send to OpenAI without KB context. AI responds conversationally using system prompt rules. |

All requests logged to terminal:
```
[CHAT] Question: "{message}"
[CHAT] KB Results: 0.783, 0.626, 0.623, 0.606, 0.598
[CHAT] Confidence Tier: HIGH (top=0.783)
[CHAT] Source: filename.pdf — Section: 2.1.2.1 Section Title
```

---

## Chunking Strategy

Section detection supports:
- Simple numbered: `1. Getting Started`
- Nested numbered: `2.1.1.1 How to use the OPC UA Client`
- Chapter style: `Chapter 1: Overview`
- ALL CAPS headers (3-100 chars, preceded by blank line)
- Markdown: `# Heading`, `## Sub Heading`

Rules:
- Header stays attached to its content — never split into separate chunk
- Large sections split at paragraph boundaries; all sub-chunks share the same section label
- No headers detected → fallback to paragraph splitting with "Part 1", "Part 2" labels
- max_chars = 2000 per chunk
- Supported file types: `.txt`, `.pdf`

---

## Frontend Architecture

| Component | File | Purpose |
|---|---|---|
| App | `App.tsx` | State machine: 'selection' or 'chat' |
| SelectionScreen | `SelectionScreen.tsx` | Two cards: Chat (active) + Voice (Phase 2, disabled) |
| ChatInterface | `ChatInterface.tsx` | Real-time chat with backend via fetch() |

**ChatInterface behavior:**
- On mount: `POST /conversations` → creates conversation → sends "hello" to get AI greeting
- On submit: optimistic UI (show user message immediately) → `POST /chat` → append AI response
- Typewriter animation on assistant messages (character by character reveal)
- Auto-scroll on new messages
- Loading indicator while waiting for AI
- Confidence tier display: LOW shows warning label, NONE has muted indicator
- Back button creates fresh conversation
- Native `fetch()` only — no axios

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `SUPABASE_DB_URL` | PostgreSQL connection string for our Supabase DB |
| `OPENAI_KEY` | OpenAI API key for embeddings and chat |
| `JIRA_BASE_URL` | Infleet's Jira instance URL (future) |
| `JIRA_EMAIL` | Jira service account email (future) |
| `JIRA_API_TOKEN` | Jira API token (future) |
| `JIRA_PROJECT_KEY` | Jira project key for ticket creation (future) |
| `INFLEET_DB_URL` | Connection string to Infleet's warranty DB (future) |

---

## Python Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `openai` | OpenAI API client (async) |
| `asyncpg` | Async PostgreSQL driver |
| `httpx` | Async HTTP client (Jira calls) |
| `python-dotenv` | Env vars from `.env` in dev |
| `pgvector` | SQLAlchemy pgvector integration |
| `pypdf` | PDF text extraction |
| `pydantic-settings` | Config validation |
| `sqlalchemy[asyncio]` | ORM |
| `alembic` | Database migrations |

---

## Coding Standards

- **Backend:** Python. `async`/`await` throughout. `asyncpg` for DB. `httpx.AsyncClient` for external HTTP. All secrets via environment variables.
- **Frontend:** TypeScript strict mode. Native `fetch()` and `WebSocket`. No HTTP client libraries.
- Robust error handling: `try/except` in Python, `try/catch` in TypeScript.
- Clean, modular, well-commented code.
- Models never leave repository boundary. Schemas are the shared language.

---

## Zero Hallucination Policy

If a schema, table name, column name, or API structure has not been provided, **do not invent it**. State exactly what information is needed before writing the code.

Specifically:
- Infleet's warranty table schema is **not yet confirmed** — always flag this before writing any warranty query.
- The `window.__INFLEET_USER__` shape is **TBD** — to be confirmed with Arbios/Infleet.

---

## What Is Built vs What Remains

### Built and Working (Test Environment)
- Full layered backend architecture (router → controller → service → repository)
- Ingestion pipeline: upload → extract (PDF/TXT) → chunk (section detection) → embed → store
- RAG search: pgvector cosine similarity via `pgvector.sqlalchemy` ORM
- Confidence tier system (HIGH/LOW/NONE) with terminal logging
- Chat pipeline: frontend → backend → OpenAI gpt-4o-mini → response → DB
- Conversations and messages persisted to PostgreSQL
- Professional system prompt with varied greetings, clarification for vague questions
- NONE tier sends to OpenAI without context (handles greetings, thanks, off-topic naturally)
- Frontend chat widget with typewriter animation, auto-scroll, loading states
- Tested with a 9-section GPS manual and a 446-page CODESYS FAQ (657 chunks)

### Not Yet Built (Intentionally Skipped for Test Env)
- User authentication (`window.__INFLEET_USER__`)
- Warranty check route (`POST /check-warranty` → Infleet's external DB)
- Jira ticket creation (`POST /create-ticket`)
- Voice path (Phase 2: `/voice-relay`, Realtime API, AudioWorklet)
- Query reformulation (rewrite vague user messages using conversation context before KB search)
- AI-guided clarification system (proactive narrowing of vague problems)

---

## Output Format Rules

When generating code or architecture:
1. Start with a 1-2 sentence confirmation of what you're building and which layer it touches.
2. Use correct language tags: `python`, `typescript`, `sql`.
3. Number sequential steps clearly.
4. For API calls, always show the full payload structure.
5. Follow the build sequence: Schema → Model → Migration → Repository → Service → Controller → Router → dependencies.py.
