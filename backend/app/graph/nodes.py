"""
Graph nodes. Each one is wrapped in `step_scope` (app/services/steps.py): a
single DB transaction that either fully commits or fully rolls back, closed
out with a RunStep row recording what happened and what was decided.

Why this + LangGraph's checkpoint-after-success together is what makes
"kill the process, start it again" (behavior 2) safe rather than merely
possible: if the process dies mid-node, the node's transaction never
committed (so the DB has no partial writes) and LangGraph never saved a
checkpoint for it (so resuming re-runs the *whole* node from its original
input, which is safe precisely because nothing partial was left behind).
Nodes that already completed are never re-run at all — LangGraph skips
straight to the first incomplete one.
"""
from __future__ import annotations

from app.db import SessionLocal
from app.domain.chunking import chunk_document
from app.domain.contradictions import Contradiction, detect_contradictions
from app.domain.deliverable import build_deliverable, diff_sections
from app.domain.facts import Fact, SourceRef
from app.domain.injection import detect_injection_attempts
from app.domain.rules import check_rule
from app.graph.state import GraphState
from app.llm.base import get_llm_client
from app.models import (
    Chunk, DeliverableVersion, Document, DocumentStatus, Finding, FindingStatus,
    FactRecord, Pile, Rule,
)
from app.services.cost import record_cost
from app.services.steps import complete_step, step_scope


def ingest_node(state: GraphState) -> GraphState:
    run_id = state["run_id"]
    ingested, failed = [], []

    with SessionLocal() as session:
        with step_scope(session, run_id, "ingest") as step:
            documents = (
                session.query(Document)
                .filter(Document.id.in_(state["document_ids"]))
                .all()
            )
            for doc in documents:
                try:
                    if doc.status == DocumentStatus.INGESTED.value:
                        ingested.append(doc.id)
                        continue
                    existing = session.query(Chunk).filter(Chunk.document_id == doc.id).count()
                    if existing == 0:
                        chunks = chunk_document(doc.raw_text)
                        if not chunks:
                            raise ValueError("no extractable text")
                        for c in chunks:
                            session.add(Chunk(document_id=doc.id, ordinal=c.ordinal,
                                               clause_ref=c.clause_ref, text=c.text))
                    doc.status = DocumentStatus.INGESTED.value
                    ingested.append(doc.id)
                except Exception as exc:  # a bad single document should not sink the whole run
                    doc.status = DocumentStatus.ERROR.value
                    failed.append(doc.id)
                    session.add(Finding(
                        run_id=run_id, pile_id=state["pile_id"], kind="ingestion_error",
                        severity="high", description=f"Could not ingest {doc.filename}: {exc}",
                        source_refs=[{"document_id": doc.id, "clause_ref": None, "quote": ""}],
                        status=FindingStatus.PENDING.value,
                    ))

            decision = "proceed" if ingested else "escalate"
            complete_step(session, step, decision,
                           {"ingested": ingested, "failed": failed})

    return {"ingested_document_ids": ingested, "failed_document_ids": failed}


def extract_facts_node(state: GraphState) -> GraphState:
    run_id, pile_id = state["run_id"], state["pile_id"]
    llm = get_llm_client()
    injection_hits = 0

    with SessionLocal() as session:
        with step_scope(session, run_id, "extract_facts") as step:
            documents = (
                session.query(Document)
                .filter(Document.id.in_(state["ingested_document_ids"]))
                .all()
            )
            for doc in documents:
                hits = detect_injection_attempts(doc.raw_text)
                if hits:
                    injection_hits += 1
                    session.add(Finding(
                        run_id=run_id, pile_id=pile_id, kind="injection_attempt", severity="high",
                        description=(
                            f"{doc.filename} contains text resembling an instruction aimed at this "
                            f"system. Treated as data, not followed. Matched: {hits!r}"
                        ),
                        source_refs=[{"document_id": doc.id, "clause_ref": None, "quote": h} for h in hits],
                        status=FindingStatus.PENDING.value,
                    ))

                chunks = session.query(Chunk).filter(Chunk.document_id == doc.id).all()
                for chunk in chunks:
                    already_cached = (
                        session.query(FactRecord).filter(FactRecord.chunk_id == chunk.id).count() > 0
                    )
                    if already_cached:
                        continue  # incremental: only new chunks incur extraction cost

                    result = llm.extract_facts(doc.id, doc.filename, chunk.clause_ref, chunk.text)
                    record_cost(session, run_id, "extract_facts", result.tokens_in,
                                result.tokens_out, result.usd_cost, result.duration_ms)
                    for fact in result.facts:
                        session.add(FactRecord(
                            pile_id=pile_id, document_id=doc.id, chunk_id=chunk.id,
                            subject=fact.subject, value=fact.value, unit=fact.unit,
                            clause_ref=fact.source.clause_ref, document_filename=fact.source.document_filename,
                            quote=fact.raw_span,
                        ))

            complete_step(session, step, "proceed", {"injection_hits": injection_hits})

    return {"injection_hit_count": injection_hits}


def examine_node(state: GraphState) -> GraphState:
    run_id, pile_id = state["run_id"], state["pile_id"]

    with SessionLocal() as session:
        with step_scope(session, run_id, "examine") as step:
            pile = session.get(Pile, pile_id)
            records = session.query(FactRecord).filter(FactRecord.pile_id == pile_id).all()
            facts = [
                Fact(
                    subject=r.subject, value=r.value, unit=r.unit,
                    source=SourceRef(document_id=r.document_id, document_filename=r.document_filename,
                                      clause_ref=r.clause_ref, quote=r.quote),
                    raw_span=r.quote,
                )
                for r in records
            ]

            contradictions: list[Contradiction] = detect_contradictions(facts)
            uploaded_at_by_doc = {
                d.id: d.uploaded_at.isoformat()
                for d in session.query(Document).filter(Document.pile_id == pile_id).all()
            }
            for c in contradictions:
                session.add(Finding(
                    run_id=run_id, pile_id=pile_id, kind="contradiction", severity="high",
                    description=c.description,
                    source_refs=[f.source.to_dict() for f in c.conflicting_facts],
                    proposed_resolution=c.proposed_resolution(uploaded_at_by_doc),
                    status=FindingStatus.PENDING.value,
                ))

            rules = session.query(Rule).filter(Rule.pile_id == pile_id).all()
            rule_violations = 0
            escalations = 0
            for rule in rules:
                res = check_rule(rule.id, rule.text, facts)
                if res.status == "violation":
                    rule_violations += 1
                    session.add(Finding(
                        run_id=run_id, pile_id=pile_id, rule_id=rule.id, kind="rule_violation",
                        severity="high", description=res.detail,
                        source_refs=[f.source.to_dict() for f in res.violating_facts],
                        status=FindingStatus.PENDING.value,
                    ))
                elif res.status == "unsupported":
                    escalations += 1
                    session.add(Finding(
                        run_id=run_id, pile_id=pile_id, rule_id=rule.id, kind="unsupported_rule",
                        severity="medium", description=res.detail, source_refs=[],
                        status=FindingStatus.PENDING.value,
                    ))

            if not contradictions and rule_violations == 0:
                session.add(Finding(
                    run_id=run_id, pile_id=pile_id, kind="no_findings", severity="low",
                    description="Clean pass: no contradictions and no rule violations found in this pile.",
                    source_refs=[], status=FindingStatus.PENDING.value,
                ))

            rule_results = [check_rule(r.id, r.text, facts) for r in rules]
            content = build_deliverable(facts, rule_results)

            previous = (
                session.query(DeliverableVersion)
                .filter(DeliverableVersion.pile_id == pile_id, DeliverableVersion.is_committed.is_(True))
                .order_by(DeliverableVersion.version_number.desc())
                .first()
            )
            changed_doc_id = state["document_ids"][-1] if state.get("document_ids") else None
            changed, carried_over = diff_sections(
                previous.content_json if previous else None, content, changed_doc_id
            )

            draft = DeliverableVersion(
                pile_id=pile_id, run_id=run_id,
                version_number=None,  # assigned at commit time; see model docstring
                content_json=content, changed_sections=changed, carried_over_sections=carried_over,
                is_committed=False,
            )
            session.add(draft)

            decision = "escalate" if escalations else "proceed"
            complete_step(session, step, decision, {
                "contradictions": len(contradictions), "rule_violations": rule_violations,
                "unsupported_rules": escalations,
            })
            session.flush()
            draft_id = draft.id

    return {
        "contradiction_count": len(contradictions),
        "rule_violation_count": rule_violations,
        "deliverable_version_id": draft_id,
    }


def await_gate_node(state: GraphState) -> GraphState:
    from app.models import Run, RunStatus

    with SessionLocal() as session:
        with step_scope(session, state["run_id"], "await_gate") as step:
            run = session.get(Run, state["run_id"])
            run.status = RunStatus.AWAITING_GATE.value
            complete_step(session, step, "proceed", {"message": "Waiting for human gate decisions."})

    return {"status": RunStatus.AWAITING_GATE.value}


def route_after_ingest(state: GraphState) -> str:
    """The one real branch point: if every document failed to ingest, do not
    waste an extraction pass on nothing — go straight to a terminal failure."""
    return "extract_facts" if state.get("ingested_document_ids") else "ingest_failed"


def ingest_failed_node(state: GraphState) -> GraphState:
    from app.models import Run, RunStatus

    with SessionLocal() as session:
        with step_scope(session, state["run_id"], "ingest_failed") as step:
            run = session.get(Run, state["run_id"])
            run.status = RunStatus.FAILED.value
            run.error = "All documents in this run failed to ingest."
            complete_step(session, step, "escalate", {})

    return {"status": RunStatus.FAILED.value, "error": "All documents in this run failed to ingest."}
