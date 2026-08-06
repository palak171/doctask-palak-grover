"""
The final step: turn a run's draft deliverable plus whatever gate decisions
have been made so far into the pile's next committed version.

Approved contradictions get their proposed resolution applied to the section
content (and say so, with the source). Rejected ones are marked explicitly
rejected-and-open — not silently dropped. Still-pending ones stay exactly as
the examine stage left them; nothing here forces a decision that was never
made (see app/services/gate.py docstring for why that's the intended
design, not an oversight).
"""
from __future__ import annotations

import copy

from sqlalchemy.orm import Session

from app.domain.deliverable import diff_sections
from app.models import DeliverableVersion, Finding, FindingStatus, Run, RunStatus
from app.services.concurrency import ConcurrentUpdateConflict, commit_deliverable
from app.services.steps import complete_step, start_step


def commit_run(session: Session, run_id: str) -> dict:
    run = session.get(Run, run_id)
    draft = (
        session.query(DeliverableVersion)
        .filter(DeliverableVersion.run_id == run_id, DeliverableVersion.is_committed.is_(False))
        .order_by(DeliverableVersion.created_at.desc())
        .first()
    )
    if draft is None:
        raise ValueError(f"No draft deliverable found for run {run_id}; has 'examine' completed?")

    content = copy.deepcopy(draft.content_json)
    findings = session.query(Finding).filter(Finding.run_id == run_id).all()

    for finding in findings:
        if finding.kind == "contradiction":
            _apply_contradiction_decision(content, finding)
        elif finding.kind in ("rule_violation", "unsupported_rule"):
            _annotate_rule_check(content, finding)

    step = start_step(session, run_id, "commit")
    try:
        previous_committed = (
            session.query(DeliverableVersion)
            .filter(DeliverableVersion.pile_id == run.pile_id, DeliverableVersion.is_committed.is_(True))
            .order_by(DeliverableVersion.version_number.desc())
            .first()
        )
        changed, carried_over = diff_sections(
            previous_committed.content_json if previous_committed else None, content, None
        )

        result = commit_deliverable(
            session, run.pile_id, run_id, run.base_pile_version, draft.id, content, changed, carried_over,
        )
        run.status = RunStatus.COMPLETED.value
        session.add(run)
        complete_step(session, step, "proceed", {"committed_version": result.version_number})
        session.commit()
        return {"version_number": result.version_number, "deliverable_version_id": result.deliverable_version_id}

    except ConcurrentUpdateConflict as exc:
        complete_step(session, step, "escalate", {"error": str(exc)})
        run.error = str(exc)
        session.add(run)
        session.commit()
        raise


def _apply_contradiction_decision(content: dict, finding: Finding):
    subject = _subject_from_description(finding)
    section = content.get("sections", {}).get(subject)
    if section is None:
        return

    if finding.status == FindingStatus.APPROVED.value:
        section["status"] = "resolved"
        section["resolution_applied"] = finding.proposed_resolution
        section["resolved_by_finding_id"] = finding.id
    elif finding.status == FindingStatus.REJECTED.value:
        section["status"] = "contradiction_open_rejected"
        section["rejection_reason"] = finding.decision_reason
    # pending: leave section["status"] == "contradiction" as examine_node set it


def _subject_from_description(finding: Finding) -> str | None:
    # description is built as: "Conflicting values for '<subject>': ..."
    marker = "Conflicting values for '"
    if finding.description.startswith(marker):
        return finding.description[len(marker):].split("'", 1)[0]
    return None


def _annotate_rule_check(content: dict, finding: Finding):
    for check in content.get("rule_checks", []):
        if check.get("rule_id") == finding.rule_id:
            check["gate_status"] = finding.status
