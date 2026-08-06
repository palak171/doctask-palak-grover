"""
Deterministic, zero-cost, zero-key "extraction model". This is what tests and
the default local run use — it is not a toy stand-in bolted on for CI; it is
the documented default backend (see README "Why a fake LLM by default").

It recognizes the same fact schema a real model would be prompted for
(app/llm/base.py:build_grounded_prompt lists it), via regex over normalized
text. Swapping in AnthropicLLMClient does not change any caller: both
implement LLMClient.extract_facts and return the same Fact shape.
"""
from __future__ import annotations

import re

from app.domain.facts import Fact, SourceRef
from app.llm.base import ExtractionResult, LLMClient

_PATTERNS: list[tuple[str, re.Pattern, str | None]] = [
    ("payment_terms_days", re.compile(r"payment[^.]*?(\d+)\s*day", re.I), "days"),
    ("termination_notice_days", re.compile(r"terminat[^.]*?(\d+)\s*day[^.]*?notice", re.I), "days"),
    ("termination_notice_days", re.compile(r"(\d+)\s*days?[^.]*?notice[^.]*?terminat", re.I), "days"),
    ("governing_law", re.compile(r"govern(?:ed|ing)?\s+by\s+the\s+laws\s+of\s+([A-Za-z][A-Za-z ,]{2,40})", re.I), None),
    ("confidentiality_period_months", re.compile(r"confidential[^.]*?(\d+)\s*year", re.I), "years"),
    ("confidentiality_period_months", re.compile(r"confidential[^.]*?(\d+)\s*month", re.I), "months"),
    ("liability_cap_usd", re.compile(r"liabilit\w*[^.]*?\$\s*([\d][\d,]*)", re.I), "usd"),
    ("renewal_term_months", re.compile(r"renew\w*[^.]*?(\d+)\s*year", re.I), "years"),
    ("renewal_term_months", re.compile(r"renew\w*[^.]*?(\d+)\s*month", re.I), "months"),
]


def _normalize(subject: str, raw_value: str, unit: str | None) -> tuple[str, str | None]:
    value = raw_value.strip().rstrip(".,;: ")
    if subject == "confidentiality_period_months" and unit == "years":
        value = str(int(value) * 12)
        unit = "months"
    elif subject == "renewal_term_months" and unit == "years":
        value = str(int(value) * 12)
        unit = "months"
    elif subject == "liability_cap_usd":
        value = value.replace(",", "")
        unit = "usd"
    elif subject == "governing_law":
        value = " ".join(value.split())
        unit = None
    return value, unit


class FakeLLMClient(LLMClient):
    def extract_facts(self, document_id: str, document_filename: str, clause_ref: str | None,
                       text: str) -> ExtractionResult:
        facts: list[Fact] = []
        seen_subjects: set[str] = set()

        for subject, pattern, unit in _PATTERNS:
            if subject in seen_subjects:
                continue
            match = pattern.search(text)
            if not match:
                continue
            raw_value = match.group(1)
            value, normalized_unit = _normalize(subject, raw_value, unit)
            facts.append(
                Fact(
                    subject=subject,
                    value=value,
                    unit=normalized_unit,
                    source=SourceRef(
                        document_id=document_id,
                        document_filename=document_filename,
                        clause_ref=clause_ref,
                        quote=match.group(0).strip(),
                    ),
                    raw_span=match.group(0).strip(),
                )
            )
            seen_subjects.add(subject)

        # Deterministic, tiny, and free — but non-zero, so cost reporting has
        # something real to sum even when running the fake backend.
        tokens_in = max(1, len(text) // 4)
        tokens_out = max(1, len(facts) * 12)
        return ExtractionResult(
            facts=facts, tokens_in=tokens_in, tokens_out=tokens_out, usd_cost=0.0, duration_ms=0
        )
