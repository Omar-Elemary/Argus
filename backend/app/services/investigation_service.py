"""Investigation service - owns the lifecycle of an investigation.

Each request gets its own LangGraph run, its own evidence store (so
concurrent investigations never share citations) and a background
thread that executes the agent pipeline. The API polls the resulting
:class:`InvestigationRecord` for progress.
"""

from __future__ import annotations

import logging
import threading
import uuid

from app.agents.orchestrator import GraphContext, run_investigation
from app.models.evidence import EvidenceStore
from app.models.investigation import InvestigationRecord, InvestigationStatus
from app.services.llm.llm_provider import LLM
from app.tools.blockchain_tools import ToolRuntime
from app.tools.specs import ToolExecutor

logger = logging.getLogger("argus.services.investigation")


class InvestigationService:
    def __init__(self, runtime: ToolRuntime, llm: LLM | None, settings: object, chain: str = "sepolia"):
        self._runtime = runtime
        self._llm = llm
        self._settings = settings
        self._chain = chain
        self._records: dict[str, InvestigationRecord] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    def start(self, query: str, address: str) -> InvestigationRecord:
        record = InvestigationRecord(
            id=uuid.uuid4().hex,
            query=query,
            address=address,
            status=InvestigationStatus.QUEUED,
        )
        with self._lock:
            self._records[record.id] = record
        thread = threading.Thread(
            target=self._run,
            args=(record.id,),
            name=f"investigation-{record.id[:8]}",
            daemon=True,
        )
        thread.start()
        return record

    def get(self, investigation_id: str) -> InvestigationRecord | None:
        with self._lock:
            return self._records.get(investigation_id)

    # ------------------------------------------------------------------
    def _run(self, investigation_id: str) -> None:
        with self._lock:
            record = self._records[investigation_id]
        record.status = InvestigationStatus.RUNNING
        record.touch()

        evidence_store = EvidenceStore()
        executor = ToolExecutor(self._runtime, evidence_store)
        ctx = GraphContext(
            executor=executor,
            llm=self._llm,
            settings=self._settings,
            chain=self._chain,
        )

        try:
            final_state = run_investigation(ctx, investigation_id, record.query, record.address)
            record.events = final_state.get("events", [])
            record.plan = final_state.get("plan")
            record.findings = final_state.get("findings", [])
            record.report = final_state.get("report")
            record.tool_calls = int(final_state.get("tool_calls", 0))
            record.iterations = int(final_state.get("iteration", 1))
            record.evidence = evidence_store.to_records()

            if final_state.get("error"):
                record.status = InvestigationStatus.FAILED
                record.error = final_state["error"]
            else:
                record.status = InvestigationStatus.COMPLETED
            logger.info(
                "investigation %s finished: %s (%d findings, %d evidence, %d tool calls)",
                investigation_id[:8],
                record.status.value,
                len(record.findings),
                len(record.evidence),
                record.tool_calls,
            )
        except Exception as exc:  # noqa: BLE001 - report any pipeline failure
            logger.exception("investigation %s failed", investigation_id[:8])
            record.status = InvestigationStatus.FAILED
            record.error = f"{type(exc).__name__}: {exc}"
        finally:
            record.touch()