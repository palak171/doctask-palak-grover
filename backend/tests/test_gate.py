"""
Behavior 3: "A human holds the gate... approves what is right and rejects
what is wrong in the same review, item by item, and the system respects
every decision. Rejecting one finding does not discard the rest."
"""
from app.models import Finding
from app.services.commit import commit_run
from app.services.gate import decide_finding, list_findings
from app.services.runs import create_pile, start_run, upload_document
from tests.conftest import CONTRACT_TWO_CONTRADICTIONS


def test_approve_one_reject_other_independently(db):
    pile = create_pile(db, "Vendor Contracts")
    doc = upload_document(db, pile.id, "contract.txt", CONTRACT_TWO_CONTRADICTIONS.encode())
    run = start_run(db, pile.id, [doc.id])

    findings = list_findings(db, run.id)
    contradictions = {f.description.split("'")[1]: f for f in findings if f.kind == "contradiction"}
    assert set(contradictions) == {"payment_terms_days", "renewal_term_months"}

    payment_finding = contradictions["payment_terms_days"]
    renewal_finding = contradictions["renewal_term_months"]

    decide_finding(db, payment_finding.id, "approve", reason="Adopt the amended 45-day term.")
    decide_finding(db, renewal_finding.id, "reject", reason="Needs legal review before we touch this one.")

    db.refresh(payment_finding)
    db.refresh(renewal_finding)
    assert payment_finding.status == "approved"
    assert renewal_finding.status == "rejected"  # rejecting this one did not touch the other

    result = commit_run(db, run.id)
    assert result["version_number"] == 1

    from app.models import DeliverableVersion
    committed = db.get(DeliverableVersion, result["deliverable_version_id"])

    payment_section = committed.content_json["sections"]["payment_terms_days"]
    assert payment_section["status"] == "resolved"
    assert "45" in payment_section["resolution_applied"]

    renewal_section = committed.content_json["sections"]["renewal_term_months"]
    assert renewal_section["status"] == "contradiction_open_rejected"
    assert renewal_section["rejection_reason"] == "Needs legal review before we touch this one."


def test_pending_findings_do_not_block_commit(db):
    """You do not need to finish every part to submit — same principle for gate decisions."""
    pile = create_pile(db, "Vendor Contracts")
    doc = upload_document(db, pile.id, "contract.txt", CONTRACT_TWO_CONTRADICTIONS.encode())
    run = start_run(db, pile.id, [doc.id])

    # Decide nothing. Commit should still succeed, leaving both open.
    result = commit_run(db, run.id)

    from app.models import DeliverableVersion
    committed = db.get(DeliverableVersion, result["deliverable_version_id"])
    assert committed.content_json["sections"]["payment_terms_days"]["status"] == "contradiction"
    assert committed.content_json["sections"]["renewal_term_months"]["status"] == "contradiction"
