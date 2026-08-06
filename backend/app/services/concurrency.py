"""
Behavior 9: "Two runs at the same time stay two runs, whether they are two
piles or the same pile hit twice. Concurrent work does not corrupt state."

The mechanism: `Pile.version` is an integer every writer must present when it
tries to publish a new DeliverableVersion. The publish is a single UPDATE with
`WHERE id = :pile_id AND version = :expected_version`. Exactly one concurrent
writer's UPDATE can match that WHERE clause and affect a row — every other
racer's UPDATE affects zero rows, which SQLAlchemy reports via `rowcount`, and
that's how a loser detects the conflict deterministically instead of via a
race on read-then-write.

This is the same optimistic-concurrency pattern regardless of backend (SQLite
or Postgres), which is why it's used here instead of `SELECT ... FOR UPDATE`
— SQLite doesn't give real row locks, and the guarantee needs to hold on both.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import DeliverableVersion, Pile


class ConcurrentUpdateConflict(Exception):
    """Raised when the pile's version moved between when a run started and when it tried to commit."""


@dataclass
class CommitResult:
    version_number: int
    deliverable_version_id: str


def commit_deliverable(
    session: Session,
    pile_id: str,
    run_id: str,
    expected_version: int,
    draft_id: str,
    content_json: dict,
    changed_sections: list,
    carried_over_sections: list,
) -> CommitResult:
    new_version_number = expected_version + 1

    result = session.execute(
        update(Pile)
        .where(Pile.id == pile_id, Pile.version == expected_version)
        .values(version=new_version_number)
    )

    if result.rowcount == 0:
        session.rollback()
        raise ConcurrentUpdateConflict(
            f"Pile {pile_id} is no longer at version {expected_version}; "
            "another run committed first. Re-read the latest deliverable and retry."
        )

    # Update the draft in place rather than inserting a second row: one
    # DeliverableVersion row per run, which starts as a draft and becomes
    # the committed record — never a growing pile of duplicate snapshots.
    deliverable = session.get(DeliverableVersion, draft_id)
    deliverable.version_number = new_version_number
    deliverable.content_json = content_json
    deliverable.changed_sections = changed_sections
    deliverable.carried_over_sections = carried_over_sections
    deliverable.is_committed = True
    session.add(deliverable)
    session.commit()
    session.refresh(deliverable)

    return CommitResult(version_number=new_version_number, deliverable_version_id=deliverable.id)
