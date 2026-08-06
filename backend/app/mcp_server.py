"""
Behavior 4: "A machine can drive it end to end." Every tool here is a thin
wrapper around the exact same app.services functions the REST API in app/api
calls — there is no orchestration logic that lives only on one side. Approval
is exposed as a tool (`decide_finding`) exactly like every other operation:
whoever drives the system, human via the API or a program via MCP, makes that
call explicitly, and it goes through the identical code path either way.

Run with: python -m app.mcp_server
"""
from __future__ import annotations

import base64

from mcp.server.mcpserver import MCPServer

from app.db import SessionLocal, init_db
from app.api.serializers import (
    deliverable_dict, document_dict, finding_dict, pile_dict, rule_dict, run_dict, run_step_dict,
)
from app.models import DeliverableVersion, Document, Pile, Run, RunStep, Rule
from app.services.commit import commit_run as _commit_run
from app.services.concurrency import ConcurrentUpdateConflict
from app.services.cost import cost_report
from app.services.gate import decide_finding as _decide_finding, list_findings
from app.services.runs import add_rule as _add_rule, create_pile as _create_pile
from app.services.runs import resume_run as _resume_run, start_run as _start_run
from app.services.runs import upload_document as _upload_document

server = MCPServer(
    name="docpile-agent",
    title="DocPile Agent",
    description="Owns a pile of documents end to end: ingest, extract, detect "
                "contradictions, examine against rules, and gate every commit "
                "through a human — driven here as MCP tools instead of a UI.",
)


@server.tool()
def create_pile(name: str, domain: str = "contract") -> dict:
    """Create a new document pile (a watched collection of related documents)."""
    with SessionLocal() as session:
        return pile_dict(_create_pile(session, name, domain))


@server.tool()
def add_rule(pile_id: str, text: str) -> dict:
    """Add one rule (a compliance checklist line, a playbook clause, a style guide rule) to a pile."""
    with SessionLocal() as session:
        return rule_dict(_add_rule(session, pile_id, text))


@server.tool()
def upload_document(pile_id: str, filename: str, content_base64: str) -> dict:
    """Upload a document into a pile. content_base64 is the raw file bytes, base64-encoded."""
    with SessionLocal() as session:
        data = base64.b64decode(content_base64)
        doc = _upload_document(session, pile_id, filename, data)
        return document_dict(doc)


@server.tool()
def list_documents(pile_id: str) -> list[dict]:
    """List every document uploaded into a pile, with its ingestion status."""
    with SessionLocal() as session:
        docs = session.query(Document).filter(Document.pile_id == pile_id).all()
        return [document_dict(d) for d in docs]


@server.tool()
def start_run(pile_id: str, document_ids: list[str], idempotency_key: str | None = None,
              run_type: str = "full") -> dict:
    """
    Start (or, if idempotency_key was already used, fetch) a run that ingests
    the given documents, extracts facts, and produces a draft deliverable
    awaiting human gate decisions.
    """
    with SessionLocal() as session:
        run = _start_run(session, pile_id, document_ids, idempotency_key, run_type)
        return run_dict(run)


@server.tool()
def resume_run(run_id: str) -> dict:
    """Resume a run that was interrupted mid-execution (process killed, etc). Safe to call on a finished run: it's a no-op."""
    with SessionLocal() as session:
        run = _resume_run(session, run_id)
        return run_dict(run)


@server.tool()
def get_run(run_id: str) -> dict:
    """Get a run's current status."""
    with SessionLocal() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError(f"run {run_id} not found")
        return run_dict(run)


@server.tool()
def get_run_steps(run_id: str) -> list[dict]:
    """List every stage a run has gone through, in order, with what it decided."""
    with SessionLocal() as session:
        steps = session.query(RunStep).filter(RunStep.run_id == run_id).order_by(RunStep.started_at).all()
        return [run_step_dict(s) for s in steps]


@server.tool()
def list_run_findings(run_id: str) -> list[dict]:
    """List every finding (contradiction, rule violation, injection attempt, or clean-pass) a run produced."""
    with SessionLocal() as session:
        return [finding_dict(f) for f in list_findings(session, run_id)]


@server.tool()
def decide_finding(finding_id: str, decision: str, actor: str = "agent", reason: str | None = None) -> dict:
    """
    Approve or reject a single finding. This IS the human gate operation
    (behavior 3): whoever calls this, human or machine, makes the call
    explicitly, one finding at a time. Rejecting one never discards the rest.
    """
    with SessionLocal() as session:
        finding = _decide_finding(session, finding_id, decision, actor, reason)
        return finding_dict(finding)


@server.tool()
def get_run_draft(run_id: str) -> dict:
    """Get the draft deliverable a run produced, before it's committed."""
    with SessionLocal() as session:
        draft = (
            session.query(DeliverableVersion)
            .filter(DeliverableVersion.run_id == run_id, DeliverableVersion.is_committed.is_(False))
            .order_by(DeliverableVersion.created_at.desc())
            .first()
        )
        if draft is None:
            raise ValueError(f"no draft deliverable for run {run_id}")
        return deliverable_dict(draft)


@server.tool()
def commit_run(run_id: str) -> dict:
    """
    Commit a run's deliverable, applying whatever gate decisions have been
    made so far. Fails with a clear conflict message (not a silent overwrite)
    if another run committed to the same pile first.
    """
    with SessionLocal() as session:
        try:
            return _commit_run(session, run_id)
        except ConcurrentUpdateConflict as exc:
            raise ValueError(str(exc)) from exc


@server.tool()
def get_run_cost(run_id: str) -> dict:
    """Get what a run cost: tokens, USD, and wall-clock time, broken down by stage."""
    with SessionLocal() as session:
        return cost_report(session, run_id)


@server.tool()
def get_pile_deliverable(pile_id: str) -> dict:
    """Get the latest committed deliverable for a pile."""
    with SessionLocal() as session:
        deliverable = (
            session.query(DeliverableVersion)
            .filter(DeliverableVersion.pile_id == pile_id, DeliverableVersion.is_committed.is_(True))
            .order_by(DeliverableVersion.version_number.desc())
            .first()
        )
        if deliverable is None:
            raise ValueError(f"pile {pile_id} has no committed deliverable yet")
        return deliverable_dict(deliverable)


if __name__ == "__main__":
    init_db()
    server.run()
