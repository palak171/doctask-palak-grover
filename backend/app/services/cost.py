"""Behavior 10: "It knows what it cost." One row per LLM call, stage-tagged."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CostEvent


def record_cost(session: Session, run_id: str, stage_name: str, tokens_in: int, tokens_out: int,
                 usd_cost: float, duration_ms: int):
    session.add(CostEvent(
        run_id=run_id, stage_name=stage_name, tokens_in=tokens_in, tokens_out=tokens_out,
        usd_cost=usd_cost, duration_ms=duration_ms,
    ))
    session.commit()


def cost_report(session: Session, run_id: str) -> dict:
    rows = session.query(
        CostEvent.stage_name,
        func.sum(CostEvent.tokens_in).label("tokens_in"),
        func.sum(CostEvent.tokens_out).label("tokens_out"),
        func.sum(CostEvent.usd_cost).label("usd_cost"),
        func.sum(CostEvent.duration_ms).label("duration_ms"),
        func.count(CostEvent.id).label("call_count"),
    ).filter(CostEvent.run_id == run_id).group_by(CostEvent.stage_name).all()

    by_stage = [
        {
            "stage": r.stage_name, "tokens_in": r.tokens_in or 0, "tokens_out": r.tokens_out or 0,
            "usd_cost": round(r.usd_cost or 0.0, 6), "duration_ms": r.duration_ms or 0,
            "call_count": r.call_count,
        }
        for r in rows
    ]
    return {
        "run_id": run_id,
        "by_stage": by_stage,
        "total_usd_cost": round(sum(r["usd_cost"] for r in by_stage), 6),
        "total_tokens": sum(r["tokens_in"] + r["tokens_out"] for r in by_stage),
        "total_duration_ms": sum(r["duration_ms"] for r in by_stage),
    }
