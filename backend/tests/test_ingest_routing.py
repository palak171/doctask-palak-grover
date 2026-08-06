"""
Behavior 1: "...some of those decisions must be able to change the path: a
retry, a skip, an escalation to a person." This test exercises the one real
branch in the graph: if every document in a run fails to ingest, the run
routes straight to a terminal failure instead of wasting an extraction pass
on nothing.
"""
from app.models import Run, RunStatus, RunStep
from app.services.runs import create_pile, start_run, upload_document


def test_all_documents_failing_ingest_routes_to_terminal_failure(db):
    pile = create_pile(db, "Vendor Contracts")
    # Empty text: chunk_document() returns [] for it, which ingest_node treats as a failure.
    doc = upload_document(db, pile.id, "empty.txt", b"   \n\n   ")

    start_run(db, pile.id, [doc.id])

    run = db.query(Run).filter(Run.pile_id == pile.id).one()
    assert run.status == RunStatus.FAILED.value
    assert "failed to ingest" in run.error

    stages = {s.stage_name for s in db.query(RunStep).filter(RunStep.run_id == run.id).all()}
    assert stages == {"ingest", "ingest_failed"}  # extract_facts/examine never ran — the path changed
