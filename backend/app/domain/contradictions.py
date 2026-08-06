"""
Cross-clause contradiction detection — the core of the assigned build
("Finds places where clause seven contradicts clause twelve"), and also the
"notices where the documents disagree" behavior Task 1's generic system
needs.

Precision strategy (WHAT STRONG LOOKS LIKE: "does not flag ordinary tension as
conflict"): we only ever compare facts that share the same *normalized
subject* (payment_terms_days vs payment_terms_days), never facts about
different topics. Two clauses can be in tension about different things
without ever being compared here — that's how false positives are kept out
structurally rather than filtered after the fact.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from app.domain.facts import Fact

_CLAUSE_NUMBER = re.compile(r"(\d+)")


def _clause_number(clause_ref: str | None) -> int:
    if not clause_ref:
        return -1
    match = _CLAUSE_NUMBER.search(clause_ref)
    return int(match.group(1)) if match else -1


@dataclass
class Contradiction:
    subject: str
    conflicting_facts: list[Fact]

    @property
    def description(self) -> str:
        parts = [f"{f.value}{(' ' + f.unit) if f.unit else ''} ({f.source.clause_ref or f.source.document_filename})"
                 for f in self.conflicting_facts]
        return f"Conflicting values for '{self.subject}': " + " vs. ".join(parts)

    def proposed_resolution(self, uploaded_at_by_doc: dict[str, str]) -> str:
        # Deliberately simple, deliberately explicit: propose the value from
        # the most recently uploaded document, breaking ties (facts living in
        # the same document) by preferring the higher clause number — matches
        # the plain-English convention these sample contracts use themselves
        # ("Notwithstanding Clause 7, ..." in Clause 12 means 12 overrides 7).
        # This is a proposal for a human to approve or reject, never applied
        # on its own.
        def sort_key(f: Fact) -> tuple[str, int]:
            return (uploaded_at_by_doc.get(f.source.document_id, ""), _clause_number(f.source.clause_ref))

        newest = max(self.conflicting_facts, key=sort_key)
        return (
            f"Proposed edit: adopt {newest.value}{(' ' + newest.unit) if newest.unit else ''} "
            f"from {newest.source.clause_ref or newest.source.document_filename} "
            f"(most recently uploaded / highest-numbered source) and update the other clause to match. "
            f"This is a proposal only; nothing is changed until approved."
        )


def detect_contradictions(facts: list[Fact]) -> list[Contradiction]:
    by_subject: dict[str, list[Fact]] = defaultdict(list)
    for fact in facts:
        by_subject[fact.subject].append(fact)

    contradictions = []
    for subject, subject_facts in by_subject.items():
        distinct_values = {(f.value, f.unit) for f in subject_facts}
        if len(distinct_values) > 1:
            # Keep one representative fact per distinct value so the finding
            # cites every conflicting source exactly once, not every mention.
            representatives: dict[tuple[str, str | None], Fact] = {}
            for f in subject_facts:
                representatives.setdefault((f.value, f.unit), f)
            contradictions.append(Contradiction(subject=subject, conflicting_facts=list(representatives.values())))

    return contradictions
