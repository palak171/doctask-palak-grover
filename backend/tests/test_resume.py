"""
Behavior 2: "Kill the process in the middle of a run and start it again. It
continues from where it left off, and no finished work is lost."

We simulate the crash by making extraction raise on the first document it
touches (as if the process died there), letting that propagate all the way
out of start_run (exactly like a real crash would), then calling resume_run
after clearing the fault. The ingest stage must not run twice.
"""
import pytest

from app.llm.fake import FakeLLMClient
from app.models import Document, Run, RunStatus, RunStep
from app.services.runs import create_pile, resume_run, start_run, upload_document
from tests.conftest import CONTRACT_V1


def test_resume_after_simulated_crash(db, monkeypatch):
    pile = create_pile(db, "Vendor Contracts")
    doc = upload_document(db, pile.id, "contract_v1.txt", CONTRACT_V1.encode())

    call_count = {"n": 0}
    real_extract = FakeLLMClient.extract_facts

    def flaky_extract(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated crash mid-extraction")
        return real_extract(self, *args, **kwargs)

    monkeypatch.setattr(FakeLLMClient, "extract_facts", flaky_extract)

    with pytest.raises(RuntimeError, match="simulated crash"):
        start_run(db, pile.id, [doc.id])

    run = db.query(Run).filter(Run.pile_id == pile.id).one()
    assert run.status == RunStatus.RUNNING.value  # never reached awaiting_gate

    steps = db.query(RunStep).filter(RunStep.run_id == run.id).all()
    stage_status = {s.stage_name: s.status for s in steps}
    assert stage_status["ingest"] == "completed"
    assert stage_status["extract_facts"] == "failed"
    assert "examine" not in stage_status  # never got there

    ingested_doc = db.get(Document, doc.id)
    assert ingested_doc.status == "ingested"  # ingest's work was not lost

    # The fault is gone now — simulate "process restarted, retry".
    resumed = resume_run(db, run.id)

    assert resumed.status == RunStatus.AWAITING_GATE.value

    steps_after = db.query(RunStep).filter(RunStep.run_id == run.id, RunStep.stage_name == "ingest").all()
    assert len(steps_after) == 1, "ingest must not be re-run after resume"

    all_stages = {
        s.stage_name for s in db.query(RunStep).filter(RunStep.run_id == run.id).all()
    }
    assert {"ingest", "extract_facts", "examine", "await_gate"} <= all_stages
