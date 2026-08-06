"""
Behavior 3: "A human holds the gate." Findings are decided one at a time;
rejecting one never touches the others (each is its own row, its own
transaction, its own audit entry in `gate_decisions`).

Design call (logged in PROGRESS.md): commit is allowed with findings still
`pending`. Approving/rejecting is not mandatory before commit — a pending
finding simply isn't applied to the deliverable and will resurface next run,
same as the brief's "you do not need to finish every part to submit." What
*is* enforced: an already-decided finding cannot be silently redecided by a
second call without a new explicit decision (idempotent, not sticky-locked —
see `decide_finding`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Finding, FindingStatus, GateDecisionLog


class FindingNotFound(Exception):
    pass


def decide_finding(session: Session, finding_id: str, decision: str, actor: str = "human",
                    reason: str | None = None) -> Finding:
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be 'approve' or 'reject'")

    finding = session.get(Finding, finding_id)
    if finding is None:
        raise FindingNotFound(finding_id)

    finding.status = FindingStatus.APPROVED.value if decision == "approve" else FindingStatus.REJECTED.value
    finding.decided_by = actor
    finding.decided_at = datetime.now(timezone.utc)
    finding.decision_reason = reason

    session.add(GateDecisionLog(finding_id=finding.id, decision=decision, actor=actor, reason=reason))
    session.commit()
    session.refresh(finding)
    return finding


def list_findings(session: Session, run_id: str) -> list[Finding]:
    return session.query(Finding).filter(Finding.run_id == run_id).order_by(Finding.created_at).all()
