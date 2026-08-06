"""
The audit log behind behavior 1 ("it works in steps we can watch"). Every
graph node starts a RunStep, does its work, and closes the RunStep — always
in that order, always as the outermost thing the node does, so a step that
never closes is proof positive the process died mid-node (and, combined with
no LangGraph checkpoint for that node, proof it's safe to re-run from
scratch: see app/graph/nodes.py module docstring).
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.models import RunStep


def start_step(session: Session, run_id: str, stage_name: str) -> RunStep:
    step = RunStep(run_id=run_id, stage_name=stage_name, status="started")
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


def complete_step(session: Session, step: RunStep, decision: str, detail: dict | None = None):
    step.status = "completed"
    step.decision = decision
    step.detail = detail or {}
    step.ended_at = datetime.now(timezone.utc)
    session.commit()


def fail_step(session: Session, step: RunStep, error: str):
    step.status = "failed"
    step.decision = "escalate"
    step.detail = {"error": error}
    step.ended_at = datetime.now(timezone.utc)
    session.commit()


@contextmanager
def step_scope(session: Session, run_id: str, stage_name: str):
    """
    Wraps a node body: commits everything the node did if it succeeds,
    rolls back entirely if it raises, and always leaves a RunStep record
    reflecting which happened. See app/graph/nodes.py for why this — plus
    LangGraph's own checkpoint-after-success — is what makes resume safe.
    """
    step = start_step(session, run_id, stage_name)
    try:
        yield step
    except Exception as exc:  # noqa: BLE001 - intentionally broad, re-raised below
        session.rollback()
        # fail_step needs its own transaction since the one above just rolled back.
        fail_step(session, step, str(exc))
        raise
    else:
        pass  # caller calls complete_step explicitly once it knows the `decision`
