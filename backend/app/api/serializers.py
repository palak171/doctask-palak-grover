from __future__ import annotations

from app.models import DeliverableVersion, Document, Finding, Pile, Run, RunStep, Rule


def pile_dict(p: Pile) -> dict:
    return {"id": p.id, "name": p.name, "domain": p.domain, "version": p.version,
            "created_at": p.created_at.isoformat()}


def rule_dict(r: Rule) -> dict:
    return {"id": r.id, "pile_id": r.pile_id, "text": r.text}


def document_dict(d: Document) -> dict:
    return {"id": d.id, "pile_id": d.pile_id, "filename": d.filename, "format": d.format,
            "status": d.status, "uploaded_at": d.uploaded_at.isoformat()}


def run_dict(r: Run) -> dict:
    return {
        "id": r.id, "pile_id": r.pile_id, "run_type": r.run_type, "status": r.status,
        "idempotency_key": r.idempotency_key, "thread_id": r.thread_id,
        "base_pile_version": r.base_pile_version, "error": r.error,
        "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
    }


def run_step_dict(s: RunStep) -> dict:
    return {
        "id": s.id, "run_id": s.run_id, "stage_name": s.stage_name, "status": s.status,
        "decision": s.decision, "detail": s.detail,
        "started_at": s.started_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
    }


def finding_dict(f: Finding) -> dict:
    return {
        "id": f.id, "run_id": f.run_id, "pile_id": f.pile_id, "rule_id": f.rule_id,
        "kind": f.kind, "severity": f.severity, "description": f.description,
        "source_refs": f.source_refs, "proposed_resolution": f.proposed_resolution,
        "status": f.status, "decided_by": f.decided_by,
        "decided_at": f.decided_at.isoformat() if f.decided_at else None,
        "decision_reason": f.decision_reason,
    }


def deliverable_dict(d: DeliverableVersion) -> dict:
    return {
        "id": d.id, "pile_id": d.pile_id, "run_id": d.run_id, "version_number": d.version_number,
        "content": d.content_json, "changed_sections": d.changed_sections,
        "carried_over_sections": d.carried_over_sections, "is_committed": d.is_committed,
        "created_at": d.created_at.isoformat(),
    }
