"""
Schema notes on the two hard requirements this file exists to satisfy:

Resumability (behavior 2): a Run's progress lives in `run_steps`, one row per
graph node execution, plus a `thread_id` that LangGraph's checkpointer keys
its own state snapshots on. Killing the process loses nothing because nothing
was ever only in memory.

Concurrency safety (behavior 9): `Pile.version` is an optimistic-concurrency
counter. Any writer that wants to publish a new `DeliverableVersion` must
present the `version` it read; the commit UPDATE includes `WHERE version =
:expected` and only proceeds if it matched. Two runs racing on the same pile
therefore cannot both win — one always finds `rowcount == 0`, detects the
conflict, and re-bases (see app/services/concurrency.py). This works
identically on SQLite and Postgres, which is why it's the mechanism instead of
a SELECT ... FOR UPDATE that SQLite can't really give us.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Float, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Pile(Base):
    __tablename__ = "piles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, default="contract")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Optimistic-concurrency counter for the pile's published deliverable state.
    version: Mapped[int] = mapped_column(Integer, default=0)

    documents: Mapped[list["Document"]] = relationship(back_populates="pile")
    rules: Mapped[list["Rule"]] = relationship(back_populates="pile")


class Rule(Base):
    """A single line of the compliance checklist / contract playbook / style guide."""
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    pile_id: Mapped[str] = mapped_column(ForeignKey("piles.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    pile: Mapped["Pile"] = relationship(back_populates="rules")


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    INGESTED = "ingested"
    ERROR = "error"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("pile_id", "content_hash", name="uq_pile_content_hash"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    pile_id: Mapped[str] = mapped_column(ForeignKey("piles.id"))
    filename: Mapped[str] = mapped_column(String)
    format: Mapped[str] = mapped_column(String)  # txt | pdf | docx | md
    content_hash: Mapped[str] = mapped_column(String, index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default=DocumentStatus.PENDING.value)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    pile: Mapped["Pile"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    clause_ref: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "Clause 7"
    text: Mapped[str] = mapped_column(Text)
    # JSON-encoded float list on SQLite; a real pgvector column in the Postgres
    # variant (see app/domain/retrieval.py for the swap point).
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class FactRecord(Base):
    """
    Cache of facts extracted per chunk. This is what makes an incremental run
    cheap: `extract_facts` only calls the LLM for chunks with no FactRecord
    yet (new documents), then reads the *whole* pile's FactRecords — cached
    plus new — to run contradiction/rule checks. Cost events are only ever
    emitted for the chunks actually re-extracted, so "an update should cost
    like an update" is a number you can pull from cost_events, not a claim.
    """
    __tablename__ = "fact_records"
    __table_args__ = (UniqueConstraint("chunk_id", "subject", name="uq_chunk_subject"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    pile_id: Mapped[str] = mapped_column(ForeignKey("piles.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"))
    subject: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    clause_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    document_filename: Mapped[str] = mapped_column(String)
    quote: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_GATE = "awaiting_gate"
    COMPLETED = "completed"
    FAILED = "failed"


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_run_idempotency_key"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    pile_id: Mapped[str] = mapped_column(ForeignKey("piles.id"))
    run_type: Mapped[str] = mapped_column(String, default="full")  # full | incremental
    trigger_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default=RunStatus.PENDING.value)
    idempotency_key: Mapped[str] = mapped_column(String, index=True)
    thread_id: Mapped[str] = mapped_column(String, default=_uuid)  # LangGraph checkpoint thread
    base_pile_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["RunStep"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    cost_events: Mapped[list["CostEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RunStep(Base):
    """One row per graph-node execution: what stage ran, what it decided, when."""
    __tablename__ = "run_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    stage_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # started | completed | failed | skipped | retried
    decision: Mapped[str | None] = mapped_column(String, nullable=True)  # proceed | retry | skip | escalate
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run: Mapped["Run"] = relationship(back_populates="steps")


class CostEvent(Base):
    __tablename__ = "cost_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    stage_name: Mapped[str] = mapped_column(String)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    usd_cost: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    run: Mapped["Run"] = relationship(back_populates="cost_events")


class FindingStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Finding(Base):
    """
    A contradiction, a rule violation, or (deliberately) a clean-pass record.
    Every finding traces to exact source locations, never a vague claim.
    """
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    pile_id: Mapped[str] = mapped_column(ForeignKey("piles.id"))
    rule_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String)  # contradiction | rule_violation | no_findings | injection_attempt
    severity: Mapped[str] = mapped_column(String, default="medium")  # low | medium | high
    description: Mapped[str] = mapped_column(Text)
    source_refs: Mapped[list] = mapped_column(JSON)  # [{document_id, clause_ref, quote}, ...]
    proposed_resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String, default=FindingStatus.PENDING.value)
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    run: Mapped["Run"] = relationship(back_populates="findings")


class DeliverableVersion(Base):
    """
    An immutable, append-only history of the pile's grounded deliverable.
    `carried_over_sections` records which parts a new version left byte-
    identical, so "an update should cost like an update" is provable, not
    just claimed (behavior: proof over assertion).
    """
    __tablename__ = "deliverable_versions"
    __table_args__ = (UniqueConstraint("pile_id", "version_number", name="uq_pile_version"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    pile_id: Mapped[str] = mapped_column(ForeignKey("piles.id"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    # Null while this is an uncommitted draft (SQL treats distinct NULLs as
    # non-colliding, so many drafts per pile coexist under the same unique
    # constraint that guards *committed* version numbers). Assigned exactly
    # once, at commit time, by app/services/concurrency.py.
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_json: Mapped[dict] = mapped_column(JSON)
    changed_sections: Mapped[list] = mapped_column(JSON, default=list)  # [{section, reason, source_document_id}]
    carried_over_sections: Mapped[list] = mapped_column(JSON, default=list)
    is_committed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class GateDecisionLog(Base):
    """Append-only audit trail: who approved/rejected what, and when."""
    __tablename__ = "gate_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"))
    decision: Mapped[str] = mapped_column(String)  # approve | reject
    actor: Mapped[str] = mapped_column(String, default="human")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
