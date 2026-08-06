"""Behavior 10: "It knows what it cost. A run can report what it spent and where the time went, stage by stage." """
from app.services.cost import cost_report
from app.services.runs import create_pile, start_run, upload_document
from tests.conftest import CONTRACT_V1


def test_cost_report_has_per_stage_breakdown(db):
    pile = create_pile(db, "Vendor Contracts")
    doc = upload_document(db, pile.id, "contract.txt", CONTRACT_V1.encode())
    run = start_run(db, pile.id, [doc.id])

    report = cost_report(db, run.id)

    assert report["run_id"] == run.id
    stages = {row["stage"] for row in report["by_stage"]}
    assert "extract_facts" in stages

    extract_row = next(r for r in report["by_stage"] if r["stage"] == "extract_facts")
    assert extract_row["tokens_in"] > 0
    assert extract_row["call_count"] == 3  # one call per clause chunk in CONTRACT_V1

    assert report["total_tokens"] == sum(r["tokens_in"] + r["tokens_out"] for r in report["by_stage"])
    assert report["total_usd_cost"] >= 0.0
