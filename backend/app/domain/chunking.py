"""
Splits raw document text into clause-referenced chunks. Contracts are the
first domain (per the assigned build: "clause seven contradicts clause
twelve"), so we recognize "Clause N", "Section N", and "Article N" headers.
Text with no such headers still gets chunked (paragraph-based), just without
a clause_ref — the rest of the pipeline treats that as "cite the paragraph"
rather than failing closed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_CLAUSE_HEADER = re.compile(
    r"^\s*(Clause|Section|Article)\s+(\d+)\b[.:]?\s*(.*)$",
    re.IGNORECASE,
)


@dataclass
class TextChunk:
    ordinal: int
    clause_ref: str | None
    text: str


def chunk_document(text: str) -> list[TextChunk]:
    lines = text.splitlines()
    chunks: list[TextChunk] = []
    current_ref: str | None = None
    current_lines: list[str] = []
    ordinal = 0

    def flush():
        nonlocal ordinal, current_lines
        body = "\n".join(current_lines).strip()
        if body:
            chunks.append(TextChunk(ordinal=ordinal, clause_ref=current_ref, text=body))
            ordinal += 1
        current_lines = []

    for line in lines:
        match = _CLAUSE_HEADER.match(line)
        if match:
            flush()
            kind, number, rest = match.groups()
            current_ref = f"{kind.title()} {number}"
            current_lines = [rest] if rest else []
        else:
            if line.strip() == "" and not current_lines:
                continue
            current_lines.append(line)
    flush()

    if not chunks and text.strip():
        # No headers at all: fall back to paragraph splitting so nothing is silently dropped.
        for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
            chunks.append(TextChunk(ordinal=len(chunks), clause_ref=None, text=para))

    return chunks
