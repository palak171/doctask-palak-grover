"""
Builds the one grounded deliverable a run produces, and diffs it against the
pile's previous version so an incremental update can prove — not just claim —
that "the parts the new source did not affect stay exactly as they were."

content_json is organized per fact-subject "section" plus a rule-checks list.
Diffing is a plain deep-equality comparison per section: unaffected sections
serialize identically and are recorded in `carried_over_sections`; anything
that changed is recorded in `changed_sections` with the source document that
caused the change, so "what changed, when, and because of which source" is
always answerable from the DB, not from memory.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.contradictions import Contradiction, detect_contradictions
from app.domain.facts import Fact
from app.domain.rules import RuleCheckResult


def build_deliverable(facts: list[Fact], rule_results: list[RuleCheckResult]) -> dict:
    contradictions = detect_contradictions(facts)
    contradiction_subjects = {c.subject for c in contradictions}

    by_subject: dict[str, list[Fact]] = {}
    for fact in facts:
        by_subject.setdefault(fact.subject, []).append(fact)

    sections = {}
    for subject, subject_facts in sorted(by_subject.items()):
        sections[subject] = {
            "facts": [f.to_dict() for f in subject_facts],
            "status": "contradiction" if subject in contradiction_subjects else "consistent",
        }

    if not rule_results:
        rule_summary = "no rules supplied; nothing checked"
    elif all(r.status == "pass" for r in rule_results):
        rule_summary = "clean corpus: no findings"
    else:
        rule_summary = f"{sum(1 for r in rule_results if r.status == 'violation')} violation(s) found"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "rule_checks": [
            {
                "rule_id": r.rule_id, "rule_text": r.rule_text, "subject": r.subject,
                "status": r.status, "detail": r.detail,
            }
            for r in rule_results
        ],
        "rule_summary": rule_summary,
        "contradiction_count": len(contradictions),
    }


def diff_sections(previous: dict | None, current: dict, changed_document_id: str | None) -> tuple[list, list]:
    """Returns (changed_sections, carried_over_sections), each a list of dicts."""
    prev_sections = (previous or {}).get("sections", {})
    curr_sections = current.get("sections", {})

    changed = []
    carried_over = []

    all_keys = set(prev_sections) | set(curr_sections)
    for key in sorted(all_keys):
        if prev_sections.get(key) == curr_sections.get(key):
            carried_over.append({"section": key})
        else:
            reason = "new section" if key not in prev_sections else (
                "removed" if key not in curr_sections else "value changed"
            )
            changed.append({"section": key, "reason": reason, "source_document_id": changed_document_id})

    return changed, carried_over
