"""
"It examines": checks the pile's facts against user-supplied rules (a
compliance checklist, a contract playbook, a style guide) and produces
findings, each pointing to the exact place it came from.

Behavior 5 ("it never bluffs") governs this file's design more than any
other: a rule this parser cannot confidently map to a known fact subject is
reported as UNSUPPORTED, never silently skipped and never guessed at. An
unsupported rule is itself an honest finding ("we cannot evaluate this yet"),
not a false pass.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.facts import Fact

_SUBJECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "payment_terms_days": ("payment",),
    "termination_notice_days": ("termination", "notice"),
    "governing_law": ("governing law", "govern"),
    "confidentiality_period_months": ("confidential",),
    "liability_cap_usd": ("liability",),
    "renewal_term_months": ("renew",),
}

_MAX_RULE = re.compile(r"must not exceed\s+\$?([\d,]+)", re.I)
_MIN_RULE = re.compile(r"must be at least\s+\$?([\d,]+)", re.I)
_EXACT_RULE = re.compile(r"must be\s+([\w][\w .,]{1,40})", re.I)


@dataclass
class RuleCheckResult:
    rule_id: str
    rule_text: str
    subject: str | None
    status: str  # "pass" | "violation" | "unsupported" | "no_data"
    detail: str
    violating_facts: list[Fact]


def _match_subject(rule_text: str) -> str | None:
    lowered = rule_text.lower()
    for subject, keywords in _SUBJECT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return subject
    return None


def check_rule(rule_id: str, rule_text: str, facts: list[Fact]) -> RuleCheckResult:
    subject = _match_subject(rule_text)
    if subject is None:
        return RuleCheckResult(rule_id, rule_text, None, "unsupported",
                                "Could not map this rule to a known fact type; needs human review.", [])

    relevant = [f for f in facts if f.subject == subject]
    if not relevant:
        return RuleCheckResult(rule_id, rule_text, subject, "no_data",
                                f"No extracted facts for '{subject}' in this pile yet.", [])

    max_match = _MAX_RULE.search(rule_text)
    min_match = _MIN_RULE.search(rule_text)
    exact_match = _EXACT_RULE.search(rule_text) if not (max_match or min_match) else None

    violating: list[Fact] = []
    if max_match:
        threshold = float(max_match.group(1).replace(",", ""))
        violating = [f for f in relevant if _safe_float(f.value) is not None and _safe_float(f.value) > threshold]
    elif min_match:
        threshold = float(min_match.group(1).replace(",", ""))
        violating = [f for f in relevant if _safe_float(f.value) is not None and _safe_float(f.value) < threshold]
    elif exact_match:
        expected = exact_match.group(1).strip().rstrip(".,;: ").lower()
        violating = [f for f in relevant if f.value.strip().lower() != expected]
    else:
        return RuleCheckResult(rule_id, rule_text, subject, "unsupported",
                                "Recognized the subject but not the rule's comparison shape "
                                "(expected 'must not exceed', 'must be at least', or 'must be').", [])

    if violating:
        cites = "; ".join(f"{f.value}{(' ' + f.unit) if f.unit else ''} ({f.source.clause_ref or f.source.document_filename})"
                           for f in violating)
        return RuleCheckResult(rule_id, rule_text, subject, "violation", f"Violated by: {cites}", violating)

    return RuleCheckResult(rule_id, rule_text, subject, "pass",
                            "All extracted facts for this subject satisfy the rule.", [])


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None
