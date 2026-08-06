"""
The fact schema this system extracts and reasons over. Kept intentionally
small and contract-shaped (matches the assigned build's domain: "clause seven
contradicts clause twelve") rather than a generic open-ended schema — a
declared, narrow fact set is exactly what makes contradiction-detection
precise instead of a source of false positives (see WHAT STRONG LOOKS LIKE:
"does not flag ordinary tension as conflict").

README.md and the write-up declare this as the accepted domain/format set per
the brief's instruction: "Say in your README which formats and domains your
system accepts."
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceRef:
    document_id: str
    document_filename: str
    clause_ref: str | None
    quote: str

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "document_filename": self.document_filename,
            "clause_ref": self.clause_ref,
            "quote": self.quote,
        }


@dataclass
class Fact:
    """One grounded, cited assertion extracted from a chunk."""
    subject: str          # e.g. "payment_terms_days", "termination_notice_days", "governing_law"
    value: str            # normalized string form, e.g. "30" or "California"
    unit: str | None      # e.g. "days", "months", "usd"
    source: SourceRef
    raw_span: str = ""

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "value": self.value,
            "unit": self.unit,
            "source": self.source.to_dict(),
            "raw_span": self.raw_span,
        }


KNOWN_SUBJECTS = (
    "payment_terms_days",
    "termination_notice_days",
    "governing_law",
    "confidentiality_period_months",
    "liability_cap_usd",
    "renewal_term_months",
)
