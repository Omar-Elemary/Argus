"""Intent parsing + investigation planning.

The orchestrator turns a natural-language request into an ordered list
of tool calls. Parsing is deterministic (keyword + regex based) so it
is testable and independent of model availability; an explicit
``address`` parameter always takes priority over one embedded in the
query.
"""

from __future__ import annotations

import re

from app.models.agent import InvestigationPlan, ToolRequest

_ADDRESS_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")

CORE_TOOLS = [
    "get_wallet_balance",
    "get_transaction_count",
    "get_recent_transactions",
    "get_token_transfers",
    "get_contract_interactions",
]

CATEGORY_HINTS: list[tuple[str, str, list[str]]] = [
    # (keyword, intent name, extra tools beyond core)
    ("token", "token activity", ["get_token_transfers"]),
    ("contract", "contract interactions", ["get_contract_interactions"]),
    ("balance", "wallet funds", ["get_wallet_balance"]),
    ("hold", "wallet funds", ["get_wallet_balance"]),
    ("transfers", "token activity", ["get_token_transfers"]),
    ("transactions", "transaction history", []),
    ("activity", "activity profile", []),
    ("active", "activity profile", []),
    ("unusual", "risk screening", []),
    ("suspicious", "risk screening", []),
    ("anomal", "risk screening", []),
    ("risk", "risk screening", []),
    ("large", "risk screening", []),
    ("recent", "light profile", ["get_recent_transactions"]),
]


def extract_address(text: str) -> str | None:
    """Pull the first 0x...-style address out of free text."""
    match = _ADDRESS_RE.search(text or "")
    return match.group(0) if match else None


def infer_intent(query: str) -> str:
    lowered = (query or "").lower()
    for keyword, intent, _ in CATEGORY_HINTS:
        if keyword in lowered:
            return intent
    return "general investigation"


def plan_investigation(query: str, address: str) -> InvestigationPlan:
    """Design the first-round tool plan for a subject address."""
    intent = infer_intent(query)
    tools = list(CORE_TOOLS)

    # Keep the light profile genuinely light.
    if intent == "light profile":
        tools = ["get_recent_transactions"]

    requests = [
        ToolRequest(tool=name, args={"address": address}, purpose=intent, iteration=1)
        for name in tools
    ]
    return InvestigationPlan(
        address=address,
        intent=intent,
        requests=requests,
        reasoning=f"Request focuses on {intent}; scheduling {len(requests)} retrieval tools.",
        iteration=1,
    )