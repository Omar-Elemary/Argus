# Argus — Architecture Notes

This document describes the internal architecture, the important design decisions,
and the extension points for the planned RAG (Phase 2) and smart-contract security
(Phase 3) capabilities.

## 1. Layering

Everything is separated so that each concern can change independently:

```
┌──────────────────────────────────────────────────────────────┐
│ presentation layer  FastAPI routes ⇄ static dashboard        │
├──────────────────────────────────────────────────────────────┤
│ orchestration layer  LangGraph StateGraph + agent nodes      │
│                       (agents/orchestrator.py & nodes)       │
├──────────────────────────────────────────────────────────────┤
│ tool layer           ToolExecutor / ToolSpec / evidence      │
│                       builders (tools/)                      │
├──────────────────────────────────────────────────────────────┤
│ data-access layer    BlockchainProvider + TransactionIndexer │
│                       (blockchain/)                          │
├──────────────────────────────────────────────────────────────┤
│ domain layer         pydantic models incl. Evidence          │
├──────────────────────────────────────────────────────────────┤
│ external             Ethereum JSON-RPC · LLM endpoint        │
└──────────────────────────────────────────────────────────────┘
```

### Provider isolation
The agents never import `web3`. They speak only to the `BlockchainProvider` protocol
(`get_balance`, `get_transaction`, `get_block_full`, `get_logs`, …) and the
`TransactionIndexer` protocol (`list_transactions`, `list_token_transfers`). A new node
type, an archive, or a light client is a drop-in implementation of these protocols.

### LLM isolation
Business logic never calls a model directly. Agents depend on the tiny `LLM` protocol
(`chat(system, user)`). The OpenAI-compatible provider and the deterministic fallback
are both interchangeable via `LLM_PROVIDER`/`LLM_API_KEY`. The fallback means the whole
pipeline — orchestration, tools, analysis, evidence, report — is fully executable and
testable without any API key.

## 2. The LangGraph control flow

State (`AgentState`) carries: the query/address, the plan, a pending tool-request queue,
accumulated tool results, tool-call & iteration counters, budget caps, public events,
findings, metrics, and the final report.

```
START
  │ plan                      (orchestrator: intent → tool request queue)
  ▼ retrieve                  (blockchain agent: drain queue via ToolExecutor)
  │ analyze                   (analysis agent: metrics → findings)
  ▼ decide                    (orchestrator: more evidence needed?)
  ├─ pending & budget left ─▶ retrieve      (bounded loop)
  └─ otherwise      ───────▶ report         (report agent: assemble, validate refs)
                              END
```

Every hop out of `retrieve`, `plan`, and `decide` is guarded by `router_after_work` /
`router_after_decide` which short-circuit to `END` on error and only loop while the
iteration/tool-call budget remains.

### Why a real loop?
The demo shows it: after the first analysis pass flags a 50 ETH inbound transfer, the
orchestrator queues `get_transaction(0xffff…)` on iteration 2 to pull its receipt and
input data before finalizing. That is tool-driven, budgeted adaptation — the definitional
"agentic" behaviour.

## 3. Blockchain data access

- `EthereumNodeProvider` wraps Web3.py and adds: request timeouts, retries with
  exponential backoff, a minimum interval between calls (rate-limit protection), chain-id
  validation, and conversion of raw payloads into typed pydantic models.
- `BlockScanIndexer` implements `TransactionIndexer` on plain RPC by scanning a bounded
  window of recent blocks for transactions involving the address and by querying
  `eth_getLogs` for ERC-20 `Transfer` events. Bounded ⇒ predictable cost.
- `EtherscanIndexer` is a ready-to-enable alternative that returns full address history
  when `ETHERSCAN_API_KEY` is configured. `build_indexer()` picks the best available.
- Token metadata (`symbol`/`decimals`) is best-effort `eth_call`; failures degrade
  gracefully and are never fabricated.

## 4. Analysis semantics

All metrics are deterministic, computed from retrieved data only:

- transaction frequency / volume and ETH in/out/net flow
- unique and repeated counterparties
- unusually large transfers (threshold from config, plus statistical outlier detection
  when the sample is large enough)
- revert/failure ratio
- burst detection (single-block concentration)
- token activity (distinct tokens, transfer counts, volume)
- contract interaction focus

Language rules encoded in `build_findings`:
- severity labels inform the reader, they do not accuse (`medium` "Potentially unusually
  large", never "malicious").
- phrases such as "observed pattern", "requires further investigation", "risk indicator"
  are used deliberately.
- every finding is paired with evidence ids; `report_node` fails hard if a referenced id
  doesn't exist.

## 5. Extension points

### Phase 2 — RAG (planned)
The report/analysis agents already consume data via typed models, and knowledge lookup
would slot in as a new tool (`documentation_lookup(query)`) available to the orchestrator,
backed by a `KnowledgeRetriever` protocol:

```
KnowledgeRetriever (protocol)
 ├── PgVectorRetriever      # pgvector + Postgres
 └── (future) EmbeddedIndex
```

This is deliberately *not* faked in the MVP: until a retriever implementation exists,
the orchestrator simply never schedules the tool. See `.env.example` → `DATABASE_URL`.

### Phase 3 — Smart-contract security (planned)
A `SecurityAnalyzer` protocol with a Slither-backed implementation can later be exposed
as tools (`analyze_contract_source`, `consume_slither_report`). Findings would flow
through the same `Finding` model and attach source/evidence. Until then:

- the report's Limitations section explicitly states that automated security analysis is
  **planned and not included**;
- no pretend vulnerability detector ships.

## 6. Reliability & security controls

| Control | Where |
| --- | --- |
| EIP-55 address validation | `blockchain/validators.py`, every tool, API |
| RPC retry + exponential backoff | `EthereumNodeProvider._call` |
| Request timeouts | HTTPProvider `request_kwargs` |
| RPC rate-limit spacing | `_min_interval` mutex in provider |
| Max iterations / max tool calls | state budgets + router guards |
| Tool input validation | `ToolExecutor._validate_args` |
| Unsupported claim prevention | `EvidenceStore.validate_references` before report |
| No secrets in code | settings fully environment-driven |
| Read-only | no signing/creation code paths exist at all |