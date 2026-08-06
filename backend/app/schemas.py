from __future__ import annotations

from pydantic import BaseModel


class CreatePileRequest(BaseModel):
    name: str
    domain: str = "contract"


class AddRuleRequest(BaseModel):
    text: str


class StartRunRequest(BaseModel):
    document_ids: list[str]
    idempotency_key: str | None = None
    run_type: str = "full"


class GateDecisionRequest(BaseModel):
    decision: str  # "approve" | "reject"
    actor: str = "human"
    reason: str | None = None
