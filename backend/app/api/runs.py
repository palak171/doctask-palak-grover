from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.serializers import deliverable_dict, finding_dict, run_dict, run_step_dict
from app.models import DeliverableVersion, Run, RunStep
from app.schemas import GateDecisionRequest, StartRunRequest
from app.services.commit import commit_run
from app.services.concurrency import ConcurrentUpdateConflict
from app.services.cost import cost_report
from app.services.gate import FindingNotFound, decide_finding, list_findings
from app.services.runs import resume_run, start_run

router = APIRouter(tags=["runs"])


@router.post("/piles/{pile_id}/runs")
def start_run_endpoint(pile_id: str, body: StartRunRequest, db: Session = Depends(get_db)):
    run = start_run(db, pile_id, body.document_ids, body.idempotency_key, body.run_type)
    return run_dict(run)


@router.post("/runs/{run_id}/resume")
def resume_run_endpoint(run_id: str, db: Session = Depends(get_db)):
    if not db.get(Run, run_id):
        raise HTTPException(404, "run not found")
    run = resume_run(db, run_id)
    return run_dict(run)


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run_dict(run)


@router.get("/runs/{run_id}/steps")
def get_run_steps(run_id: str, db: Session = Depends(get_db)):
    steps = db.query(RunStep).filter(RunStep.run_id == run_id).order_by(RunStep.started_at).all()
    return [run_step_dict(s) for s in steps]


@router.get("/runs/{run_id}/findings")
def get_run_findings(run_id: str, db: Session = Depends(get_db)):
    return [finding_dict(f) for f in list_findings(db, run_id)]


@router.get("/runs/{run_id}/draft")
def get_run_draft(run_id: str, db: Session = Depends(get_db)):
    draft = (
        db.query(DeliverableVersion)
        .filter(DeliverableVersion.run_id == run_id, DeliverableVersion.is_committed.is_(False))
        .order_by(DeliverableVersion.created_at.desc())
        .first()
    )
    if not draft:
        raise HTTPException(404, "no draft deliverable for this run")
    return deliverable_dict(draft)


@router.post("/findings/{finding_id}/decision")
def decide_finding_endpoint(finding_id: str, body: GateDecisionRequest, db: Session = Depends(get_db)):
    try:
        finding = decide_finding(db, finding_id, body.decision, body.actor, body.reason)
    except FindingNotFound:
        raise HTTPException(404, "finding not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return finding_dict(finding)


@router.post("/runs/{run_id}/commit")
def commit_run_endpoint(run_id: str, db: Session = Depends(get_db)):
    try:
        result = commit_run(db, run_id)
    except ConcurrentUpdateConflict as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return result


@router.get("/runs/{run_id}/cost")
def get_run_cost(run_id: str, db: Session = Depends(get_db)):
    return cost_report(db, run_id)
