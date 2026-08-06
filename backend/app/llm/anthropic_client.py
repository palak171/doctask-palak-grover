"""
Real backend, used only when ANTHROPIC_API_KEY is set (see app/config.py).
Not imported by default, not in the base dependency set, and never touched by
tests — the fake backend is what tests and CI always exercise, per the
brief's "real tests exist and run without a live key."

Every call routes through build_grounded_prompt, so document text can only
ever reach the model as fenced <document_data> — never as free-standing
instructions.
"""
from __future__ import annotations

import json
import os

from app.domain.facts import Fact, SourceRef
from app.llm.base import ExtractionResult, LLMClient, build_grounded_prompt, timed

_MODEL = os.environ.get("DOCPILE_ANTHROPIC_MODEL", "claude-sonnet-5")
_INPUT_USD_PER_MTOK = 3.0
_OUTPUT_USD_PER_MTOK = 15.0


class AnthropicLLMClient(LLMClient):
    def __init__(self):
        import anthropic  # local import: optional dependency, only needed here

        self._client = anthropic.Anthropic()
        self._anthropic = anthropic

    @timed
    def extract_facts(self, document_id: str, document_filename: str, clause_ref: str | None,
                       text: str) -> ExtractionResult:
        prompt = build_grounded_prompt(clause_ref, text)
        response = self._client.messages.create(
            model=_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(block.text for block in response.content if block.type == "text")
        facts = _parse_facts(raw, document_id, document_filename, clause_ref)

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        usd_cost = (tokens_in / 1_000_000) * _INPUT_USD_PER_MTOK + (tokens_out / 1_000_000) * _OUTPUT_USD_PER_MTOK
        return ExtractionResult(facts=facts, tokens_in=tokens_in, tokens_out=tokens_out,
                                 usd_cost=usd_cost, duration_ms=0)


def _parse_facts(raw: str, document_id: str, document_filename: str, clause_ref: str | None) -> list[Fact]:
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        items = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return []

    facts = []
    for item in items:
        try:
            facts.append(
                Fact(
                    subject=item["subject"],
                    value=str(item["value"]),
                    unit=item.get("unit"),
                    source=SourceRef(
                        document_id=document_id,
                        document_filename=document_filename,
                        clause_ref=clause_ref,
                        quote=item.get("quote", ""),
                    ),
                    raw_span=item.get("quote", ""),
                )
            )
        except (KeyError, TypeError):
            continue
    return facts
