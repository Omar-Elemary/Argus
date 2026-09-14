# Fellows Architecture

Fellows is an **AI company operating system**. A human founder creates a company, hires AI employees (Fellows), gives them roles, tools, permissions, and work, and observes real collaboration. A 3D office visualizes **backend events only**. It is not a chatbot demo and not a simulated office.

This document is the source of architectural truth for implementation. Phase 1 implements foundation only. Later phases must extend these contracts rather than invent parallel ones.

---

## 0. What already existed in this repository

The repo previously shipped **Argus**, an agentic Ethereum investigation service (FastAPI + LangGraph + static dashboard). Fellows replaces the product domain. The following Argus patterns are **sound and reused**:

| Pattern | Why it stays |
| --- | --- |
| Environment-driven `Settings` (`pydantic-settings`, no hard-coded secrets) | Spec rule 6 |
| `LLM` protocol + OpenAI-compatible + Cursor + deterministic fallback | Spec §26; tests without keys |
| FastAPI app factory, CORS, health route, dependency bag | Modular API |
| Public `AgentEvent` as activity, explicitly **not** chain-of-thought | Spec §35 |
| LangGraph-shaped graph state + budget caps | Spec §9 (Phase 4) |
| pytest + ruff + Docker/Compose | Spec §29, §37 |
| Provider isolation (agents never talk to a vendor SDK directly) | Extensibility |

Argus-specific blockchain RPC, investigation reports, and the static HTML dashboard are **not** Fellows. They are removed as domain code. The Next.js app required by Phase 1 replaces the static frontend.

---

## 1. System layers

Two connected layers; one source of truth.

```
Human Founder
      │
      ▼
   Fellows
      │
      ├──────────────────────────┐
      ▼                          ▼
AI Company Engine         Virtual Office
(source of truth)         (projection only)
      │                          │
      ▼                          ▼
Users, Companies,           Characters, rooms,
Agents, Tasks, Memory,      desks, animation,
Tools, Projects,            camera, activity labels
Permissions, Approvals,
Orchestration, Events
      │                          │
      └────────────┬─────────────┘
                   ▼
            Activity Events
         (typed, persisted)
```

### 1.1 AI Company layer (source of truth)

Owns identity, tenancy, agents, tasks, projects, memory, tools, messages, executions, approvals, LLM usage, and **all** activity events. Business rules and permissions live here. The UI never decides that work happened.

### 1.2 Virtual Office layer (projection)

Owns presentation: GLB assets, React Three Fiber scene, camera, animation clips. It **derives** occupant pose/animation from application state that was produced from events. It never writes company/agent/task records. It never invents activity to look busy.

**Invariant:** `3D state = f(backend events + current entity rows)`. Never the reverse.

---

## 2. Stack

| Concern | Choice | Phase |
| --- | --- | --- |
| Frontend | Next.js (App Router), React, TypeScript **strict** (`any` forbidden), Tailwind, shadcn/ui | 1 |
| 3D | React Three Fiber, Three.js, Drei; Blender → `.glb` (browser never runs Blender) | 6 |
| Backend | Python 3.11+, FastAPI, Pydantic v2 | 1 |
| DB | PostgreSQL 16 + **pgvector** | 1 infra / 8 vectors |
| Cache / realtime fan-out | Redis | 1 infra / 5 use |
| ORM / migrations | SQLAlchemy 2 (async) + Alembic | 1 |
| Auth | Email/password, JWT access tokens, password hashes (bcrypt) | 1 |
| Orchestration | LangGraph state machine, structured Pydantic state, tool calling | 4 |
| Realtime | SSE or WebSocket on `/api/v1/ws/companies/{company_id}` | 5 |
| Infra | Docker, Docker Compose, GitHub Actions | 1 |

Secrets live in environment variables (see `.env.example`). Provider API keys never ship to the browser.

---

## 3. Repository layout

```
.
├── backend/
│   ├── alembic/                  # migrations (Phase 1: users, companies, memberships)
│   ├── app/
│   │   ├── main.py
│   │   ├── config/settings.py    # evolved from Argus Settings
│   │   ├── db/                   # engine, session, mixins
│   │   ├── security/             # password hashing, JWT
│   │   ├── api/routes/           # health, auth, companies (Phase 1)
│   │   ├── models/               # SQLAlchemy tables
│   │   ├── schemas/              # Pydantic API + event + office + orchestration contracts
│   │   ├── services/             # auth, company; llm/ reused
│   │   ├── orchestration/        # LangGraph contracts (executed in Phase 4)
│   │   └── office/               # pure projection helpers (no Three.js)
│   └── tests/
├── frontend/                     # Next.js App Router (replaces Argus static HTML)
├── docker/
├── docs/                         # this file + ADRs
├── docker-compose.yml
├── pyproject.toml
└── .github/workflows/ci.yml
```

Modules stay small. Routes parse/authorize/call services. Services own transactions. Pydantic schemas are the HTTP and event contracts. SQLAlchemy models are persistence only.

---

## 4. Multi-tenant security

Every business row is scoped by `company_id` (except `users`). Access is **never** “hide it in the UI”.

Rules:

1. Authenticated user is resolved from JWT on the backend.
2. A user may only read/write a company if a `company_memberships` row exists for `(user_id, company_id)`.
3. Cross-tenant reads return **404** (do not leak existence).
4. Agent, task, memory, file, and API-key rows (later phases) always include `company_id` and are queried with the membership predicate.
5. Founder/owner role is required to change company settings, billing-like actions, and (later) production deploy / spend policies.
6. Secrets (LLM keys, tool credentials) are stored server-side, encrypted at rest in later phases; Phase 1 has no tenant keys.

Phase 1 enforcement: all company routes load membership inside the service, not the client.

---

## 5. Database schemas

UUIDs, `created_at` / `updated_at`, foreign keys, indexes on tenant + lookup columns.

### 5.1 Phase 1 (implemented)

```text
users
  id            UUID PK
  email         CITEXT UNIQUE NOT NULL
  password_hash TEXT NOT NULL
  full_name     TEXT NOT NULL
  created_at    TIMESTAMPTZ NOT NULL
  updated_at    TIMESTAMPTZ NOT NULL

companies
  id            UUID PK
  name          TEXT NOT NULL
  slug          TEXT NOT NULL UNIQUE
  description   TEXT NOT NULL DEFAULT ''
  mission       TEXT NOT NULL DEFAULT ''
  industry      TEXT NOT NULL DEFAULT ''
  logo_url      TEXT
  settings      JSONB NOT NULL DEFAULT '{}'
  created_by    UUID NOT NULL FK users(id)
  created_at    TIMESTAMPTZ NOT NULL
  updated_at    TIMESTAMPTZ NOT NULL

company_memberships
  id            UUID PK
  company_id    UUID NOT NULL FK companies(id) ON DELETE CASCADE
  user_id       UUID NOT NULL FK users(id) ON DELETE CASCADE
  role          TEXT NOT NULL  -- owner | admin | member | viewer
  created_at    TIMESTAMPTZ NOT NULL
  UNIQUE (company_id, user_id)
```

`companies.settings` Phase 1 shape:

```json
{
  "timezone": "UTC",
  "locale": "en-US",
  "work_days": ["mon", "tue", "wed", "thu", "fri"]
}
```

pgvector is enabled in the database image/migration (`CREATE EXTENSION IF NOT EXISTS vector`) so Phase 8 can add embedding columns without a platform change. No embeddings are written in Phase 1.

### 5.2 Later phases (contract only — do not create unused feature code)

```text
agents, agent_skills, agent_tools, agent_memories
company_memories
projects, tasks, task_dependencies
agent_messages, agent_executions
approvals
activity_events
tool_executions, llm_usage
offices, office_rooms, office_objects, agent_office_states
```

Minimum columns (all UUID + timestamps + `company_id` unless noted):

| Entity | Notable fields |
| --- | --- |
| Agent | name, role, department, description, avatar_url, personality[], instructions, provider, model, temperature, max_tokens, status |
| Task | title, description, status, priority, creator_id, assignee_agent_id, parent_task_id, project_id, deadline, outputs JSONB |
| Task status | `BACKLOG ASSIGNED QUEUED WORKING WAITING BLOCKED REVIEW COMPLETED FAILED CANCELLED` |
| ActivityEvent | agent_id?, event_type, task_id?, payload JSONB, timestamp |
| AgentOfficeState | agent_id, model, position, rotation, current_room, current_state, current_task_id, target_position, animation — **derived cache**, not an independent authority |
| Approval | task_id?, requested_by_agent_id, policy, status, reason, risk, estimated_cost |

Demo seed **ACME AI** (Alex/Maya/Adam/Sara/Omar) is **Phase 10 / unblocker**, not Phase 1.

---

## 6. API contracts (Pydantic)

Version prefix: `/api/v1`. JSON in/out. Auth: `Authorization: Bearer <jwt>`.

### 6.1 Phase 1

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | `{ email, password, full_name }` → `{ access_token, token_type, user }` |
| POST | `/api/v1/auth/login` | `{ email, password }` → same |
| POST | `/api/v1/auth/logout` | Client discards token (stateless JWT) |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/companies` | Create company (caller becomes `owner`) |
| GET | `/api/v1/companies` | Companies the user belongs to |
| GET | `/api/v1/companies/{id}` | Company detail (member) |
| PATCH | `/api/v1/companies/{id}` | Update profile/settings (owner/admin) |
| GET | `/api/v1/companies/{id}/overview` | Dashboard payload from **real** rows |
| GET | `/api/v1/health` | Liveness |
| GET | `/api/v1/health/ready` | DB (and optional Redis) readiness |

Company create/update body:

```text
name, description, mission, industry, logo_url?, settings?
```

Overview response contains company profile, membership list, and counts that exist. Phase 1: `members` is queried. Agent/task/approval counts are omitted or reported only when those tables exist — **never invented analytics**.

### 6.2 Later (stable paths — implement when the phase lands)

```text
POST/GET  /api/v1/companies/{id}/agents
GET/PATCH /api/v1/agents/{id}
POST/GET  /api/v1/companies/{id}/tasks
GET       /api/v1/tasks/{id}
POST      /api/v1/tasks/{id}/execute
POST      /api/v1/tasks/{id}/cancel
POST      /api/v1/agents/{id}/message
GET       /api/v1/companies/{id}/activity
POST      /api/v1/approvals/{id}/approve
POST      /api/v1/approvals/{id}/reject
GET/PATCH /api/v1/companies/{id}/office
WS/SSE    /api/v1/ws/companies/{company_id}
```

Errors: `{ "detail": string }` (FastAPI default). 401 unauthenticated, 404 cross-tenant or missing.

---

## 7. Frontend routes

| Route | Phase | Notes |
| --- | --- | --- |
| `/` | 1 | Landing. Hero copy from spec. **No fake live office.** Decorative art is labeled as product visual, not live agents. |
| `/login` `/register` | 1 | Auth |
| `/app` | 1 | Redirect to overview or company create |
| `/app/companies/new` | 1 | Create company |
| `/app/companies/[companyId]` | 1 | Company overview dashboard |
| `/app/companies/[companyId]/settings` | 1 | Edit name/mission/industry/logo/settings |
| `/app/companies/[companyId]/agents` | 2 | |
| `/app/companies/[companyId]/tasks` | 3 | |
| `/app/companies/[companyId]/projects` | 3 | |
| `/app/companies/[companyId]/memory` | 8 | |
| `/app/companies/[companyId]/activity` | 5 | |
| `/app/companies/[companyId]/office` | 6 | R3F canvas; reads office state API |
| `/app/companies/[companyId]/analytics` | 10 | Real aggregates only |
| `/app/companies/[companyId]/founder` | 9 | Founder Mode |

SaaS chrome (spec §19): Company, Agents, Tasks, Projects, Memory, Activity, Office, Analytics, Settings. Phase 1 shows upcoming nav items as **disabled**, not as fake screens.

Server state: fetch from REST. Realtime (Phase 5): event stream reducer. 3D (Phase 6): derived from server + realtime, no business logic in canvas components.

---

## 8. Event schema

Events are the source of truth for activity UI and the input to office projection.

```python
class EventType(StrEnum):
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_STARTED_TASK = "AGENT_STARTED_TASK"
    AGENT_COMPLETED_TASK = "AGENT_COMPLETED_TASK"
    AGENT_REQUESTED_HELP = "AGENT_REQUESTED_HELP"
    AGENT_SENT_MESSAGE = "AGENT_SENT_MESSAGE"
    AGENT_RECEIVED_MESSAGE = "AGENT_RECEIVED_MESSAGE"
    AGENT_DELEGATED_TASK = "AGENT_DELEGATED_TASK"
    AGENT_ENTERED_REVIEW = "AGENT_ENTERED_REVIEW"
    AGENT_BLOCKED = "AGENT_BLOCKED"
    AGENT_FAILED = "AGENT_FAILED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    COMPANY_CREATED = "COMPANY_CREATED"  # Phase 1

class ActivityEvent(BaseModel):
    id: UUID
    company_id: UUID
    agent_id: UUID | None = None
    event_type: EventType
    task_id: UUID | None = None
    payload: dict[str, Any] = {}
    timestamp: datetime
```

Events describe **what happened**, not hidden chain-of-thought. Founder-visible reasoning is a short summary of decisions/actions/evidence (Phase 9).

Phase 1 persists `COMPANY_CREATED` so the dashboard activity list is real from day one.

---

## 9. 3D state model (derived)

Character record (spec §15) is a **view model**:

```text
agent_id, model, position, rotation, current_room,
current_state, current_task, target_position, animation
```

Animation map (spec §16): backend agent/task status → clip. Examples: `IDLE` → sit/idle, `WORKING` → typing, `BLOCKED` → concerned, `OFFLINE` → away from desk.

Help request (spec §17) is event-driven:

```text
MAYA → REQUEST_HELP → ADAM
  → frontend receives AGENT_REQUESTED_HELP
  → Maya state TALKING, pathfind to Adam, face, conversation UI, return to desk
```

The canvas does not decide Maya needs help.

Office rooms (spec §14): Reception, CEO, desks, Research, Engineering, Design, Meeting, presentation screen, whiteboard, break, optional server room. Style: readable, modern startup, subtle sci-fi — not a game HUD wrapping the SaaS app.

Phase 1 ships a **pure function** `project_office_state(events, agents) -> OfficeState` with tests. No Three.js until Phase 6.

---

## 10. LLM provider abstraction

Agents never import a vendor SDK. They depend on:

```text
LLMProvider
  ├── OpenAICompatibleProvider   # implemented (reused from Argus)
  ├── CursorCloudAgentProvider   # implemented (reused from Argus)
  ├── AnthropicProvider          # Phase 4
  ├── GeminiProvider             # Phase 4
  ├── LocalProvider              # Phase 4
  └── DeterministicFallback      # tests / no key — not fake agent work
```

Per-agent (Phase 2+): `provider`, `model`, `temperature`, `max_tokens`. Routing stays in the backend.

Fallback must **not** be presented as an AI employee working. If no provider is configured, agent execution (Phase 4) fails closed with a clear error rather than inventing research.

---

## 11. Orchestration (LangGraph)

Executed in **Phase 4**. Contracts live now so Phase 2–3 persist the right task/agent fields.

State machine:

```text
PLAN → DELEGATE → EXECUTE → REVIEW → REVISE → COMPLETE
```

Every run has: task, context, allowed tools, permissions, budget/limits, expected output, explicit transition. No unbounded agent chatter. Caps: `MAX_ITERATIONS`, `MAX_TOOL_CALLS` (settings already used this pattern in Argus).

Tools (MCP-shaped later): `web_search`, `browser`, `python`, `github`, `filesystem`, `database`, `company_memory`, `calendar`, `email`, `custom_api`. An agent only receives tools granted by `agent_tools` ∩ company policy ∩ permissions. Permissions are enforced in the tool executor, not the prompt.

---

## 12. Frontend state rules

```text
Backend entity + event
        ↓
REST / WebSocket
        ↓
Application state (React, not the canvas)
        ↓
3D character visual state
```

Bad: a character “decides” it is working. Good: backend says working → event → app state → clip.

---

## 13. MVP phases

| Phase | Scope | This assignment |
| --- | --- | --- |
| 1 Foundation | Next.js, FastAPI, Postgres, auth, company, basic dashboard | **Yes** |
| 2 Agents | Agent studio persistence and UI | No |
| 3 Tasks | Task CRUD, assign, status, output | No |
| 4 Orchestration | LangGraph, tools, delegation | No |
| 5 Real-time | Event bus, WS/SSE, live feed | No |
| 6 3D office | R3F office, characters, movement | No |
| 7 AI/3D integration | Wire events → characters | No |
| 8 Memory | pgvector memories | No |
| 9 Human approval | Approvals, pause/resume, Founder Mode | No |
| 10 Polish | Analytics (real), avatars, demo seed | No |

---

## 14. Phase 1 user journey

1. Create account (email, password, name).
2. Create company (name, description, mission, industry, logo URL, settings).
3. Land on a dark-first dashboard: company overview from the API (profile, founder membership, real activity including `COMPANY_CREATED`). Upcoming surfaces are disabled empty states — not mock metrics.

---

## 15. Design

Dark-first SaaS: AI startup + creative studio + professional. Subtle gradient, restrained glass, clean type, rounded cards. The 3D office (later) must not make the rest of the product feel like a game.

Landing hero (spec §39):

```text
Build Your AI Company.
Create AI employees.
Give them work.
Watch them build.
[Create Your Company]  [Explore Demo]
```

Explore Demo stays disabled until ACME seed exists. Do not show fake working agents on the landing canvas.

---

## 16. ADRs

Short records live in `docs/adr/`:

1. Backend is source of truth; office is a projection.
2. Multi-tenant isolation via membership + company_id on every business row.
3. LLM provider protocol; no vendor lock-in in domain code.
4. Public events are actions, not chain-of-thought.

---

## 17. Testing and CI

Phase 1 backend tests: register/login, duplicate email, company CRUD, **cross-tenant 404**, overview reflects persisted data, office projector unit test, LLM provider selection (reused). Lint: ruff. Frontend: `tsc --noEmit` + eslint. GitHub Actions runs both.
