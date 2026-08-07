# DocPile Agent — Task 1 write-up

**What I built:** an agentic system that owns a pile of related documents end
to end — ingests mixed formats, extracts facts, detects where documents
contradict each other, checks the pile against rules a user supplies, and
keeps one grounded, cited deliverable up to date as new documents arrive.
Nothing commits without a human approving or rejecting each finding
individually. It's driven identically by a REST API and an MCP server, so
either a person through the included React console or an autonomous agent
can run the whole loop.

**For whom:** teams that maintain many documents that are supposed to agree
with each other and currently check that by hand — the concrete instance
here is contract review (the domain I declared and built against), but the
graph, the human gate, the concurrency handling, and the cost tracking don't
know or care that the documents are contracts; a second domain is a second
fact schema, not a rewrite.

**Results, measured, not claimed:**
- All 10 required behaviors have a named test, and all 17 tests pass with
  zero API key, zero cost, zero external services — `pytest -q` from a clean
  clone. That's the "stranger can run it in minutes" claim, verified rather
  than asserted.
- Incremental cost is a number, not a promise:
  `test_incremental_run_only_costs_for_new_content` proves a second run
  against a pile with one new 4-clause document makes exactly 4 new
  extraction calls, not 7 — the original document's facts are cached and
  never re-billed.
- Concurrency safety is proven under an actual race:
  `test_concurrent_commits_on_same_pile_do_not_corrupt_state` starts two
  threads committing to the same pile simultaneously and asserts exactly one
  wins, the pile's version counter reflects exactly one commit, and no
  duplicate or corrupted deliverable exists afterward.
- The human gate is proven to be genuinely item-by-item: a test approves one
  contradiction and rejects a second in the same run and asserts the
  committed deliverable reflects each decision independently — the rejected
  one stays open and labeled as such, the approved one is resolved.

**What I did to get there:** LangGraph gives visible, checkpointed stages for
free, which is most of behavior 1 and 2 solved by choosing the right
orchestration primitive rather than hand-rolling a state machine. The harder
design work was making resumability actually safe rather than merely
possible: every node wraps its database writes in one transaction that
either fully commits or fully rolls back, so a crash mid-node leaves nothing
partial for LangGraph to skip past incorrectly on resume. Concurrency safety
came from the same instinct — an optimistic version counter with a
single-UPDATE compare-and-swap works identically on SQLite and Postgres,
where a row lock would not.

**Trade-offs, held honestly:** fact extraction is a deterministic regex
extractor by default, not a general-purpose LLM call — auditable and
free, but narrow to a declared fact schema (payment terms, termination
notice, governing law, confidentiality period, liability cap, renewal term).
A real Anthropic-backed extractor is wired in behind the same interface and
switches on via an environment variable, but every test exercises the fake
one, which is a deliberate scope choice, not an oversight. Retrieval is
exact-match, not embedding-based, in the default SQLite path — correct for
this fact schema, and would need real vector search at larger scale or with
a less structured domain; the Postgres+pgvector path exists for exactly that
transition and isn't the default because requiring Docker to run a test
suite contradicts the brief's own "minutes, one command" bar. Chunking
assumes `Clause N`/`Section N`/`Article N` headers; documents that structure
clauses differently fall back to paragraph-level chunks with weaker
citations rather than failing, which I think is the right failure mode for
an system that's supposed to never bluff.
