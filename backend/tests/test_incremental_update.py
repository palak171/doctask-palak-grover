"""
"Stays alive": new documents keep arriving, and each arrival produces a
grounded update to the deliverable, not a rewrite and not a full re-run that
happens to reproduce the same bytes. An update should cost like an update.

This test proves it two ways: (1) the second run's extraction cost only
covers the newly added document's chunks, not the whole pile again, and
(2) the diff between committed versions correctly separates what changed
from what carried over untouched.
"""
from app.models import DeliverableVersion
from app.services.commit import commit_run
from app.services.cost import cost_report
from app.services.runs import create_pile, start_run, upload_document
from tests.conftest import CONTRACT_CONSISTENT, CONTRACT_TWO_CONTRADICTIONS


def test_incremental_run_only_costs_for_new_content(db):
    pile = create_pile(db, "Vendor Contracts")
    doc_1 = upload_document(db, pile.id, "base.txt", CONTRACT_CONSISTENT.encode())
    run_1 = start_run(db, pile.id, [doc_1.id])
    commit_run(db, run_1.id)

    report_1 = cost_report(db, run_1.id)
    extract_1 = next(r for r in report_1["by_stage"] if r["stage"] == "extract_facts")
    assert extract_1["call_count"] == 3  # 3 clauses in CONTRACT_CONSISTENT

    # New document arrives. Re-running against the same pile (base_doc + new_doc)
    # must not re-extract base_doc's chunks: they're already cached.
    doc_2 = upload_document(db, pile.id, "amendment.txt", CONTRACT_TWO_CONTRADICTIONS.encode())
    run_2 = start_run(db, pile.id, [doc_1.id, doc_2.id])

    report_2 = cost_report(db, run_2.id)
    extract_2 = next(r for r in report_2["by_stage"] if r["stage"] == "extract_facts")
    assert extract_2["call_count"] == 4  # only doc_2's 4 clauses, doc_1's 3 are cached and skipped


def test_committed_diff_separates_changed_from_carried_over(db):
    pile = create_pile(db, "Vendor Contracts")
    doc_1 = upload_document(db, pile.id, "base.txt", CONTRACT_CONSISTENT.encode())
    run_1 = start_run(db, pile.id, [doc_1.id])
    result_1 = commit_run(db, run_1.id)
    v1 = db.get(DeliverableVersion, result_1["deliverable_version_id"])
    # First version: everything is new, nothing carried over yet.
    assert len(v1.changed_sections) >= 1
    assert v1.carried_over_sections == []

    doc_2 = upload_document(db, pile.id, "amendment.txt", CONTRACT_TWO_CONTRADICTIONS.encode())
    run_2 = start_run(db, pile.id, [doc_1.id, doc_2.id])
    result_2 = commit_run(db, run_2.id)
    v2 = db.get(DeliverableVersion, result_2["deliverable_version_id"])

    changed_keys = {c["section"] for c in v2.changed_sections}
    carried_keys = {c["section"] for c in v2.carried_over_sections}

    # governing_law and confidentiality_period_months come only from doc_1
    # and doc_2 never mentions them: they must carry over byte-identical.
    assert "governing_law" in carried_keys
    assert "confidentiality_period_months" in carried_keys
    # payment_terms_days and renewal_term_months are newly contradicted by doc_2.
    assert "renewal_term_months" in changed_keys
    assert changed_keys.isdisjoint(carried_keys)
