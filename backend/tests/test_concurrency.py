"""
Behavior 9: "Two runs at the same time stay two runs... Concurrent work does
not corrupt state." Two runs against the SAME pile both examine independently
(that part is naturally concurrency-safe: each run only reads and writes its
own FactRecords/Findings/draft). The one place two runs could actually
collide is publishing a DeliverableVersion, so that's what this test races.
"""
import threading

from app.db import SessionLocal
from app.models import DeliverableVersion, Pile
from app.services.commit import commit_run
from app.services.concurrency import ConcurrentUpdateConflict
from app.services.runs import create_pile, start_run, upload_document
from tests.conftest import CONTRACT_V1, CONTRACT_TWO_CONTRADICTIONS


def test_concurrent_commits_on_same_pile_do_not_corrupt_state(db):
    pile = create_pile(db, "Vendor Contracts")
    doc_a = upload_document(db, pile.id, "contract_a.txt", CONTRACT_V1.encode())
    doc_b = upload_document(db, pile.id, "contract_b.txt", CONTRACT_TWO_CONTRADICTIONS.encode())

    # Two independent runs, both examining the pile at base version 0.
    run_a = start_run(db, pile.id, [doc_a.id], idempotency_key="run-a")
    run_b = start_run(db, pile.id, [doc_b.id], idempotency_key="run-b")
    assert run_a.base_pile_version == 0
    assert run_b.base_pile_version == 0

    results = {}
    barrier = threading.Barrier(2)

    def commit_worker(run_id: str, key: str):
        session = SessionLocal()
        try:
            barrier.wait(timeout=5)  # maximize the chance they actually race
            try:
                results[key] = ("ok", commit_run(session, run_id))
            except ConcurrentUpdateConflict as exc:
                results[key] = ("conflict", str(exc))
        finally:
            session.close()

    t1 = threading.Thread(target=commit_worker, args=(run_a.id, "a"))
    t2 = threading.Thread(target=commit_worker, args=(run_b.id, "b"))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    outcomes = [results["a"][0], results["b"][0]]
    assert sorted(outcomes) == ["conflict", "ok"], f"expected exactly one winner, got {results}"

    committed = (
        db.query(DeliverableVersion)
        .filter(DeliverableVersion.pile_id == pile.id, DeliverableVersion.is_committed.is_(True))
        .all()
    )
    assert len(committed) == 1, "exactly one commit should have won; state must not be corrupted"
    assert committed[0].version_number == 1

    pile_after = db.get(Pile, pile.id)
    assert pile_after.version == 1, "pile version must reflect exactly one successful commit, not two"


def test_two_piles_are_fully_independent(db):
    """The other half of behavior 9: two piles hit at once never interact."""
    pile_1 = create_pile(db, "Pile One")
    pile_2 = create_pile(db, "Pile Two")
    doc_1 = upload_document(db, pile_1.id, "a.txt", CONTRACT_V1.encode())
    doc_2 = upload_document(db, pile_2.id, "b.txt", CONTRACT_TWO_CONTRADICTIONS.encode())

    run_1 = start_run(db, pile_1.id, [doc_1.id])
    run_2 = start_run(db, pile_2.id, [doc_2.id])

    r1 = commit_run(db, run_1.id)
    r2 = commit_run(db, run_2.id)

    assert r1["version_number"] == 1
    assert r2["version_number"] == 1  # independent counters, both succeed
