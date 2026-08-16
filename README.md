# Argus — Agentic Blockchain Intelligence

Investigate an Ethereum **wallet or smart contract** in natural language and get an
**evidence-backed intelligence report** — produced by a genuine multi-agent pipeline,
not a chatbot.

```
User request                     Argus
"Investigate 0x…"          ─▶    FastAPI ─▶ LangGraph Orchesstror ─▶ Blockchain Agent
                                                                        ▶ Analysis Agent
                                                                        ▶ Report Agent
                                                                    ─▶ Evidence-backed report
```

Argus plans an investigation, decides which blockchain tools it needs, retrieves **real
on-chain data** from Ethereum JSON-RPC, analyzes the evidence, loops back for a deeper
look when something is flagged, and writes a structured report where every factual claim
references the evidence that supports it.

> **Important**: Argus is a read-only investigator. It never creates or signs a real
> transaction, never asks for private keys or seed phrases, and never fabricates data.
> Findings use cautious language — "potentially", "requires further investigation" —
> because pointing a finger is not what an investigator does.

This is an independent portfolio project. It is not affiliated with or endorsed by any
company or protocol mentioned in this document.

---

## Why is this an *agentic* system, not a chatbot?

A chatbot answers from memory and pattern-matching. Argus **performs work**: it chooses
tools, retrieves ground truth from the chain, computes metrics from that data, decides
whether more evidence is needed, and only then writes a report — with citations.

| Capability | Chatbot | Argus |
| --- | --- | --- |
| Decides which data to fetch | Often none | Orchestrator plans tool calls per request |
| Retrieves real chain data | Rarely | Yes — via Web3.py / JSON-RPC (never invented) |
| Loops to retrieve more | No | Yes — bounded "decide → retrieve again" cycle |
| Cites its sources | Rarely | Every finding and report bullet carries `EVID-xxxx` refs |
| Guard-rails / budgets | No | Max iterations, max tool calls, retries, timeouts, rate limiting |

The agents have **distinct, testable responsibilities**:

1. **Orchestrator Agent** — plans, delegates, and decides when more investigation is due.
2. **Blockchain Agent** — the *only* component that talks to the chain; executes typed tools.
3. **Analysis Agent** — computes real metrics (flow, frequency, outliers, failed-tx ratio,
   repeated counterparties, token activity) and produces cautious, evidence-linked findings.
4. **Report Agent** — assembles the structured report; every bullet references evidence ids.

```
                     ┌───────────────────────────────────────────────┐
                     │        Orchestrator Agent (LangGraph)          │
                     └───────▲─────────────────────────────┬─────────┘
        plan / decide tasks  │                             │  findings + evidence
                             │                             ▼
   ┌────────────────────┐    │           ┌────────────────────────────┐
   │   Blockchain Agent │◄───┘           │      Analysis Agent        │
   │   (tools only)     │  retrieve      └─────────────▲──────────────┘
   └─────────┬──────────┘               report data    │
             │ JSON-RPC / Web3.py                ┌──────┴────────────────┐
             ▼                                    │     Report Agent     │
   Ethereum node (Sepolia / Mainnet)              │  + Evidence Store    │
                                                  └──────────────────────┘
```

### Agentic loop (bounded by construction)

```
plan → retrieve → analyze → decide ──(needs more data)──▶ retrieve ──(loop)──▶ …
                              └──(no more work)──▶ report
```

Iterations and tool calls are hard-capped by `MAX_ITERATIONS` / `MAX_TOOL_CALLS` from the
environment, so runaway behaviour is impossible by design.

---

## Technology stack

- **Python 3.11+**, **FastAPI**, **Pydantic v2**, **LangGraph**
- **Web3.py** over **Ethereum JSON-RPC** (Sepolia by default; Mainnet via config)
- Pluggable **LLM layer** (OpenAI / any OpenAI-compatible endpoint; deterministic fallback
  when no API key is set, so the pipeline runs fully offline in tests)
- **pytest** + mocked RPC for a hermetic test suite
- **Docker / docker-compose**, **python-dotenv**, **pgvector-ready** design for Phase 2

---

## Project layout

```
argus/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes (investigate, health)
│   │   ├── agents/         # LangGraph orchestration + per-agent logic
│   │   ├── blockchain/     # provider (Web3.py) + transaction indexers
│   │   ├── tools/          # typed tools, executor, evidence builders
│   │   ├── models/         # pydantic domain models (incl. Evidence)
│   │   ├── services/       # investigation lifecycle + LLM provider
│   │   ├── config/         # environment-driven settings
│   │   └── main.py
│   └── tests/              # 60+ hermetic tests (mocked RPC)
├── frontend/               # static investigation dashboard (served by FastAPI)
├── docs/                   # architecture notes, extension points
├── scripts/                # dev / test / demo helpers
├── docker/
├── docker-compose.yml
├── .env.example
└── pyproject.toml
```

---

## Setup

Requires Python 3.11+ (tested on 3.11) and an Ethereum RPC endpoint for live data.

```bash
# 1. install
pip install -e ".[dev]"

# 2. configure (copy and fill in)
Copy-Item .env.example backend/.env      # Windows
# cp .env.example backend/.env           # Unix/macOS

# 3. run the test suite (hermetic - no RPC or API keys needed)
python -m pytest backend/tests

# 4. run the server, then open http://127.0.0.1:8000
python -m uvicorn app.main:app --app-dir backend --reload
# or: scripts/dev.ps1 / scripts/dev.sh
```

### Docker

```bash
docker compose up --build     # serves the API + dashboard on :8000
```

### Environment variables

| Variable | Purpose |
| --- | --- |
| `ETH_RPC_URL` | Ethereum JSON-RPC endpoint (required for live data). |
| `ETH_NETWORK` | `sepolia` (default) or `mainnet`. |
| `ETH_CHAIN_ID` | Optional explicit chain-id override; else auto-detected/derived. |
| `RPC_TIMEOUT_SECONDS`, `RPC_RETRIES`, `RPC_RETRY_BACKOFF`, `RPC_MIN_INTERVAL_MS` | Reliability: request timeouts, exponential-backoff retries, rate-limit spacing between RPC calls. |
| `MAX_ITERATIONS`, `MAX_TOOL_CALLS` | Hard agent-loop caps. |
| `MAX_TRANSACTIONS`, `MAX_BLOCKS_SCAN` | Investigation window bounds. |
| `ETHERS..AN_API_KEY` | Optional — enables the Etherscan-backed indexer for full history (MVP uses a bounded block-scan indexer). |
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_BASE_URL` | Pluggable model backend. `none` ⇒ deterministic fallback (works without keys). |
| `LARGE_TX_THRESHOLD_ETH`, `REPEATED_COUNTERPARTY_MIN` | Analysis thresholds. |

See `.env.example` for the complete list. **No secrets are hard-coded** — ever.

---

## Using Argus

### API

```
POST /api/investigate      { "query": "Investigate this wallet and flag unusual activity",
                             "address": "0x…" }
GET  /api/investigation/{id}   # poll progress: events, findings, evidence, report
GET  /api/health
```

### Example

```json
POST /api/investigate
{ "query": "Investigate this wallet and summarize its recent activity, important
            transactions, token transfers, and unusual behavior.",
  "address": "0x0f52fD2320D48E4f2cBdF29196BdBAa65e0E1D04" }
```

Driven purely by a stub/Demo (no RPC) to show the pipeline:

```
[orchestrator] Planned investigation (activity profile) - 5 retrieval tool(s)
[orchestrator] Delegating blockchain retrieval to the blockchain agent
[  blockchain] Retrieved get_wallet_balance (...) - {address, wei, eth}
[  blockchain] Retrieved get_recent_transactions (...) - 5 item(s)
[    analysis] Analyzing transaction patterns
[    analysis] Computed 5 evidence-backed finding(s) from 5 transaction(s)
[orchestrator] Requesting transaction details for 1 flagged transaction(s)
[  blockchain] Retrieved get_transaction (...) - {hash, from_address, to_address}
[      report] Generating evidence-backed report (5 finding(s), 11 evidence record(s))

FIND-001 [medium] Potentially unusually large ETH transfer
        Incoming transfer of 50.0000 ETH in transaction 0xffff… (block 115) is
        potentially unusually large for this wallet's typical activity and
        requires further investigation.
        evidence: EVID-0007
FIND-002 [low] Repeated counterparty observed
        Address repeatedly transacts with 0xbbbb… (3 occurrences in the window).
        This is an observed pattern, not itself an indicator of wrongdoing.
        evidence: EVID-0003, EVID-0005, EVID-0007
```

Try it without any RPC/keys:

```bash
python scripts/demo_agent.py
```

---

## Evidence system

No claim stands on its own. Every retrieved fact becomes an `Evidence` record:

```json
{
  "id": "EVID-0007",
  "type": "transaction",
  "source": "Ethereum RPC",
  "transaction_hash": "0xffff…",
  "block_number": 115,
  "value_eth": 50.0,
  "description": "Transaction 0xffff… to 0x0f52… of 50.000000 ETH (block 115)."
}
```

Findings and report bullets reference these ids (`EVID-0007`). The report node **refuses to
finish** if any finding references evidence that does not exist, so the LLM never gets to
invent support.

## Security considerations

- Read-only by design: no transaction creation, signing, or key material, ever.
- Addresses validated (`EIP-55` checksummed) before any RPC call.
- Inputs validated in every tool; unknown arguments are rejected.
- RPC failures handled with retries + exponential backoff and bounded timeouts.
- Rate-limit spacing between RPC calls; tool-call and iteration ceilings.
- Findings use cautious, evidence-linked language; unusual ≠ criminal.
- No secrets in the repository, config fully environment-driven.

## Limitations (honest)

- The MVP transaction indexer scans a **bounded block window** from a public RPC; it is
  not a full archive search. (The indexer interface is designed for Etherscan/BlockScout
  to be plugged in — enabled today with `EtherscanIndexer`.)
- ERC-20 `Transfer` events only; no NFT/ERC-1155 or internal-call tracing.
- Analysis is statistical pattern-screening, not a verdict.

## Roadmap

- **Phase 2 — RAG**: retrieval over Ethereum/protocol/smart-contract documentation with
  **pgvector**. The retrieval boundary is isolated so it can be added without touching the
  agent core (see `docs/ARCHITECTURE.md`).
- **Phase 3 — Smart-contract security**: Slither static analysis integration, source-code
  ingestion, and evidence-attached vulnerability findings. Currently **planned**, not
  faked.
- **Persistence**: Postgres adapter for investigation history (interface stubbed).

## Development

```bash
ruff check backend/app backend/tests     # lint
python scripts/test.ps1                  # lint + full hermetic test suite
python scripts/demo_agent.py             # offline agent demo
```

## License

MIT — see the repository.