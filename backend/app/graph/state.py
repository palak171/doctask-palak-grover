from __future__ import annotations

from typing import TypedDict


class GraphState(TypedDict, total=False):
    run_id: str
    pile_id: str
    document_ids: list[str]        # documents this run is responsible for ingesting/extracting
    ingested_document_ids: list[str]
    failed_document_ids: list[str]
    contradiction_count: int
    injection_hit_count: int
    rule_violation_count: int
    deliverable_version_id: str    # draft DeliverableVersion.id, pending gate + commit
    status: str                    # mirrors Run.status for convenience in API responses
    error: str | None
