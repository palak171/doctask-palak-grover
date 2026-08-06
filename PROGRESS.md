# PROGRESS.md — assumptions and calls made while building

Dated entries, most recent last. Per the task brief: "When something in this
brief is ambiguous, do not wait for us. Make a reasonable call, write it and
the reasoning in your README, and keep building."

## 2026-08-06

- **Domain scope**: implemented for contracts first (matches the assigned
  build). The fact schema (`app/domain/facts.py:KNOWN_SUBJECTS`) is narrow and
  declared on purpose — payment terms, termination notice, governing law,
  confidentiality period, liability cap, renewal term. A second domain (e.g.
  vendor invoices) would mean a second fact schema + extractor, not a rewrite
  of the graph. Logged here because the brief explicitly asks which
  formats/domains the system accepts.

- **Storage**: SQLite by default, Postgres+pgvector supported via
  `DATABASE_URL` for production retrieval at scale. Reasoning: the brief's
  behavior 6 ("stranger can run it in minutes, one documented command")
  weighs against requiring Docker/Postgres just to run the test suite or the
  demo. The trade-off is real — SQLite's cosine-similarity fallback for
  retrieval is pure Python and won't scale to a large pile — and it's a
  documented, not hidden, choice.

- **LangGraph checkpointer**: SqliteSaver (file-backed), not the in-memory
  saver, specifically so "kill the process, start it again" is a real test
  against a real file, not a claim.

- **Concurrency mechanism**: optimistic version counter on `Pile.version`
  rather than `SELECT ... FOR UPDATE`, because SQLite doesn't give real row
  locks and the guarantee needs to hold identically on both backends. See
  `app/models.py` docstring and `app/services/concurrency.py`.

- **Contradiction detection precision**: only compares facts sharing the
  exact same normalized subject key. This is what keeps "ordinary tension"
  between unrelated clauses from ever being compared, rather than trying to
  filter false positives after generating them.

- **Fake LLM backend is the default**, not a test-only mock. Presence of
  `ANTHROPIC_API_KEY` opts into the real backend. Reasoning: matches "tests
  run without a live key" and "should not cost you real money" directly,
  and keeps the extraction logic itself auditable/deterministic for the
  write-up's demo.
