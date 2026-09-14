# Fellows

An **AI company operating system**. You are the founder. You create a company, hire AI employees, give them roles, tools, permissions, and work, and a 3D office visualizes **real backend events only**.

This repository is in **Phase 1 — Foundation**: accounts, companies, and a basic dashboard. It is not a chatbot demo.

Architecture: [`docs/architecture.md`](docs/architecture.md)

## What was here before

This Git history started as **Argus**, an Ethereum investigation service. Fellows keeps the sound bits (env-driven settings, LLM provider protocol, FastAPI layout, public events that are not chain-of-thought, pytest/ruff/Docker) and replaces the product domain.

## Phase 1 journey

1. Create an account  
2. Create a company (name, description, mission, industry, logo URL, settings)  
3. Open the company overview (real membership + `COMPANY_CREATED` activity)

Later nav items (Agents, Tasks, Office, …) are visible but disabled. Empty metrics are labeled as not yet available — nothing is faked.

## Stack

- **Frontend:** Next.js, React, TypeScript (strict), Tailwind, shadcn-style UI  
- **Backend:** FastAPI, Pydantic, SQLAlchemy, PostgreSQL (pgvector image), Redis  
- **Auth:** email/password, JWT  

## Setup

```bash
# backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example backend/.env   # optional; SQLite is the default if DATABASE_URL is unset

# tests + lint
./scripts/test.sh

# API  http://127.0.0.1:8000
./scripts/dev.sh

# frontend
cd frontend
cp .env.local.example .env.local   # or set NEXT_PUBLIC_API_URL
npm install
npm run dev                        # http://localhost:3000
```

### Docker

```bash
docker compose up --build
```

API on `:8000`, web on `:3000`, Postgres (pgvector) and Redis included.

## API (Phase 1)

```
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/companies
GET  /api/v1/companies
GET  /api/v1/companies/{id}
PATCH /api/v1/companies/{id}
GET  /api/v1/companies/{id}/overview
GET  /api/v1/health
```

## License

MIT
