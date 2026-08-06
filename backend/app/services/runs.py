"""
The single service both the REST API and the MCP server call — neither
surface contains any orchestration logic of its own (behavior 4: "a machine
can drive it end to end", same operations either way).

`start_run` and `resume_run` both funnel into `_invoke_graph`, which is the
only place that talks to the compiled LangGraph. `start_run` is idempotent on
`idempotency_key`: calling it twice with the same key returns the existing
run instead of creating a second one racing the first (part of behavior 9).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.graph.build import get_compiled_graph
from app.graph.state import GraphState
from app.ingestion.parsers import parse, sha256_of
from app.models import Document, DocumentStatus, Pile, Run, RunStatus, Rule


def create_pile(session: Session, name: str, domain: str = "contract") -> Pile:
    pile = Pile(name=name, domain=domain)
    session.add(pile)
    session.commit()
    session.refresh(pile)
    return pile


def add_rule(session: Session, pile_id: str, text: str) -> Rule:
    rule = Rule(pile_id=pile_id, text=text)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def upload_document(session: Session, pile_id: str, filename: str, data: bytes) -> Document:
    """Idempotent on (pile_id, content_hash): re-uploading the same bytes
    returns the existing Document instead of duplicating it."""
    content_hash = sha256_of(data)
    existing = (
        session.query(Document)
        .filter(Document.pile_id == pile_id, Document.content_hash == content_hash)
        .first()
    )
    if existing:
        return existing

    parsed = parse(filename, data)
    doc = Document(
        pile_id=pile_id, filename=filename, format=parsed.format,
        content_hash=content_hash, raw_text=parsed.text, status=DocumentStatus.PENDING.value,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def start_run(session: Session, pile_id: str, document_ids: list[str], idempotency_key: str | None = None,
              run_type: str = "full") -> Run:
    idempotency_key = idempotency_key or str(uuid.uuid4())

    existing = session.query(Run).filter(Run.idempotency_key == idempotency_key).first()
    if existing:
        return existing

    pile = session.get(Pile, pile_id)
    run = Run(
        pile_id=pile_id, run_type=run_type, status=RunStatus.RUNNING.value,
        idempotency_key=idempotency_key, base_pile_version=pile.version,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    initial_state: GraphState = {
        "run_id": run.id, "pile_id": pile_id, "document_ids": document_ids,
    }
    _invoke_graph(run.id, initial_state, fresh=True)

    session.refresh(run)
    return run


def resume_run(session: Session, run_id: str) -> Run:
    """
    Behavior 2. Call this after a crash: same thread_id, no new input.
    LangGraph reads its last checkpoint for this thread and continues from
    the first node that never completed — completed nodes are not re-run.
    """
    run = session.get(Run, run_id)
    if run.status not in (RunStatus.RUNNING.value, RunStatus.PENDING.value):
        return run  # nothing to resume: already past the point of failure

    _invoke_graph(run.id, None, fresh=False)
    session.refresh(run)
    return run


def _invoke_graph(thread_id: str, state: GraphState | None, fresh: bool):
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(state, config)
