"""FastAPI dependency bag.

Services are constructed lazily so the API can boot even when the RPC
endpoint is misconfigured; the health endpoint reports the real state
and investigate endpoints return a clear 503 until it is fixed.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from functools import lru_cache

from app.blockchain.indexer import build_indexer
from app.blockchain.provider import (
    BlockchainProvider,
    EthereumNodeProvider,
    NodeMisconfigured,
    NoopProvider,
)
from app.config.settings import Settings
from app.services.investigation_service import InvestigationService
from app.services.llm.llm_provider import LLM, build_llm
from app.tools.blockchain_tools import ToolRuntime

logger = logging.getLogger("argus.api.dependencies")


@dataclass
class DependencyBag:
    settings: Settings
    llm: LLM | None = None
    chain: str = "sepolia"
    _runtime: ToolRuntime | None = None
    _service: InvestigationService | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _runtime_error: str | None = None

    @classmethod
    def build(cls, settings: Settings) -> DependencyBag:
        return cls(settings=settings, llm=build_llm(settings), chain=settings.eth_network)

    def runtime_last_error(self) -> str | None:
        return self._runtime_error

    def get_runtime(self) -> ToolRuntime:
        """Create (once) and return the tool runtime; raises on failure."""
        if self._runtime is not None:
            return self._runtime
        with self._lock:
            if self._runtime is not None:
                return self._runtime
            try:
                provider: BlockchainProvider = EthereumNodeProvider(self.settings)
                indexer = build_indexer(self.settings, provider)
                self._runtime = ToolRuntime(
                    provider=provider,
                    indexer=indexer,
                    settings=self.settings,
                )
                self._runtime_error = None
            except NodeMisconfigured as exc:  # noqa: BLE001
                # If no RPC is configured, fall back to a noop provider so the
                # API can still run (features will be limited/offline).
                if not self.settings.eth_rpc_url:
                    provider = NoopProvider(self.settings)
                    indexer = build_indexer(self.settings, provider)
                    self._runtime = ToolRuntime(
                        provider=provider,
                        indexer=indexer,
                        settings=self.settings,
                    )
                    self._runtime_error = None
                else:
                    self._runtime_error = str(exc)
                    raise
            except Exception as exc:  # noqa: BLE001
                self._runtime_error = str(exc)
                raise
        return self._runtime

    def get_service(self) -> InvestigationService:
        if self._service is None:
            runtime = self.get_runtime()
            self._service = InvestigationService(
                runtime=runtime,
                llm=self.llm,
                settings=self.settings,
                chain=self.settings.eth_network,
            )
        return self._service


@lru_cache(maxsize=1)
def build_bag() -> DependencyBag:
    """Return a singleton DependencyBag so services (and investigations)
    persist across requests during a single server process.
    """
    from app.config.settings import get_settings

    return DependencyBag.build(get_settings())