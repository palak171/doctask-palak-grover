"""
Behavior 5: "It never bluffs. When the sources do not support a claim, it
says so instead of inventing one." Applied to rule-checking specifically: a
rule this system cannot confidently evaluate must come back UNSUPPORTED, not
a fabricated pass.
"""
from app.domain.facts import Fact, SourceRef
from app.domain.rules import check_rule
from app.services.gate import list_findings
from app.services.runs import add_rule, create_pile, start_run, upload_document
from tests.conftest import CONTRACT_CONSISTENT, CONTRACT_TWO_CONTRADICTIONS


def _fact(subject, value, unit=None):
    return Fact(subject=subject, value=value, unit=unit,
                source=SourceRef("doc-1", "doc.txt", "Clause 1", "quote"))


def test_unrecognized_rule_subject_is_unsupported_not_a_false_pass():
    result = check_rule("r1", "The font size must be at least 12", [_fact("payment_terms_days", "30")])
    assert result.status == "unsupported"


def test_no_facts_for_subject_is_no_data_not_a_false_pass():
    result = check_rule("r1", "payment terms must not exceed 30 days", [])
    assert result.status == "no_data"


def test_recognized_rule_with_supporting_facts_evaluates_correctly():
    facts = [_fact("payment_terms_days", "45")]
    violation = check_rule("r1", "payment terms must not exceed 30 days", facts)
    assert violation.status == "violation"

    facts_ok = [_fact("payment_terms_days", "20")]
    clean = check_rule("r1", "payment terms must not exceed 30 days", facts_ok)
    assert clean.status == "pass"


def test_clean_pile_gets_an_honest_no_findings_report(db):
    pile = create_pile(db, "Vendor Contracts")
    doc = upload_document(db, pile.id, "clean.txt", CONTRACT_CONSISTENT.encode())
    run = start_run(db, pile.id, [doc.id])

    findings = list_findings(db, run.id)
    kinds = {f.kind for f in findings}
    assert "contradiction" not in kinds
    assert "no_findings" in kinds  # the honest "clean corpus" report, not silence


def test_unsupported_pile_rule_surfaces_as_a_finding_not_a_silent_pass(db):
    pile = create_pile(db, "Vendor Contracts")
    add_rule(db, pile.id, "The document must use 12pt font throughout")
    doc = upload_document(db, pile.id, "contract.txt", CONTRACT_TWO_CONTRADICTIONS.encode())
    run = start_run(db, pile.id, [doc.id])

    findings = list_findings(db, run.id)
    unsupported = [f for f in findings if f.kind == "unsupported_rule"]
    assert len(unsupported) == 1
    assert "font" in unsupported[0].description.lower() or "could not map" in unsupported[0].description.lower()
