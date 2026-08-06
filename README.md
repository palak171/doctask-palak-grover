# DocPile Agent

An agentic system that owns a pile of documents end to end: it **understands**
a pile (ingests mixed formats, extracts facts, notices contradictions), it
**examines** the pile against rules you supply (a compliance checklist, a
contract playbook), and it **stays alive** as new documents arrive, updating
its one grounded deliverable incrementally instead of starting over. A human
gates every commit, item by item.

Built for the SuperDocs Round 2 engineering task (Task 1 — the shared
agentic system every candidate is compared on). The assigned build (Task 2,
"Cross-clause contradiction detector," built on SuperDocs' own product API)
lives in a separate pull request against `superdocs-builds`, per the brief.

## Quickstart

Requires Python 3.11+. Nothing else — no Docker, no Postgres, no API key.

```bash
cd backend
pip install -e ".[dev]"
pytest -q                                   # 17 tests, all pass, no live key needed
uvicorn app.main:app --reload --port 8000   # http://localhost:8000
```

Optional review UI:

```bash
cd frontend
npm install
npm run dev                                 # http://localhost:5173
```

Optional MCP server (same operations, machine-drivable):

```bash
cd backend
python -m app.mcp_server
```

### Why SQLite by default

The brief's behavior 6 is "a stranger can run it in minutes, one documented
command." Requiring Docker/Postgres just to run the test suite or try the demo
works against that. SQLite is the default for both the app database and the
LangGraph checkpoint file; `DATABASE_URL` swaps in Postgres+pgvector (see
`docker-compose.yml`) for production-scale retrieval. This trade-off, and
every other non-obvious call made while building this, is logged in
[PROGRESS.md](PROGRESS.md).

### Why a fake LLM by default

`app/llm/fake.py` is a deterministic, zero-cost extractor and is the default
backend — not a test-only mock. Setting `ANTHROPIC_API_KEY` opts into the real
backend (`app/llm/anthropic_client.py`). This is what makes "real tests exist
and run without a live key" literally true, and it means the extraction logic
itself is auditable and reproducible rather than a black box.

## Architecture

```
Upload documents → [ingest] → [extract_facts] → [examine] → [await_gate] → (human decides) → [commit]
                       │             │               │                          │
                   chunk by      cache facts    detect contra-              apply approved
                   clause,       per chunk,     dictions, check             resolutions,
                   dedupe by     skip cached    rules, build draft          optimistic-
                   content       chunks         deliverable                 concurrency commit
                   hash                                                     against Pile.version
```

- **Orchestration**: LangGraph (`app/graph/`), checkpointed to a SQLite file
  after every node, so a killed process resumes from the last completed node
  — nothing finished is re-run, nothing unfinished is lost.
- **Domain logic** (`app/domain/`): chunking, fact extraction schema,
  cross-clause contradiction detection, rule checking, deliverable
  building/diffing, prompt-injection detection. All pure, LLM-agnostic,
  independently unit-tested.
- **Persistence** (`app/models.py`): every stage, cost event, finding, gate
  decision, and deliverable version is a row, not a log line — the whole
  system is auditable from the database alone.
- **Two identical surfaces**: `app/api/` (REST, for the React console) and
  `app/mcp_server.py` (MCP tools, for a machine/agent) both call the exact
  same `app/services/*` functions. Neither has orchestration logic of its own.

## Accepted domains and formats

Declared up front, per the brief's request: **contracts** is the first (and
currently only) domain, with a narrow fact schema —
`app/domain/facts.py:KNOWN_SUBJECTS` (payment terms, termination notice,
governing law, confidentiality period, liability cap, renewal term). Formats:
`.txt`, `.md`, `.pdf`, `.docx`, chunked by `Clause N` / `Section N` /
`Article N` headers (falling back to paragraph-splitting if none are found).
A second domain means a second fact schema and extractor — the graph,
gating, concurrency, and cost-tracking machinery don't change.

## The ten behaviors, where they live, how they're proven

| # | Behavior | Code | Test |
|---|---|---|---|
| 1 | Visible stages; decisions can change path | `app/graph/nodes.py`, `route_after_ingest` | `tests/test_ingest_routing.py` |
| 2 | Survives being stopped | `app/graph/checkpoint.py` (file-backed SqliteSaver) | `tests/test_resume.py` |
| 3 | Human holds the gate, item by item | `app/services/gate.py` | `tests/test_gate.py` |
| 4 | Machine can drive it end to end | `app/mcp_server.py` mirrors `app/api/` | `tests/test_mcp_parity.py` |
| 5 | Never bluffs | `app/domain/rules.py` (`unsupported`/`no_data`, never a guessed pass) | `tests/test_no_bluffing.py` |
| 6 | Stranger can run it in minutes | SQLite default, one `pip install`, `pytest` | this README |
| 7 | Proves itself without a live key | `app/llm/fake.py` is the default backend | entire suite (17/17 pass, no key) |
| 8 | Doesn't take orders from documents | `app/domain/injection.py` + prompt envelope in `app/llm/base.py` | `tests/test_injection_defense.py` |
| 9 | Concurrent runs don't corrupt state | `app/services/concurrency.py` (optimistic version check) | `tests/test_concurrency.py` |
| 10 | Knows what it cost | `app/models.py:CostEvent`, `app/services/cost.py` | `tests/test_cost_reporting.py` |

Run `pytest -v` to see all 17 tests, named after the exact behavior each one proves.

## What "an update costs like an update" looks like in practice

Facts are cached per chunk (`FactRecord`, keyed on `chunk_id`). A second run
against a pile with one new document only calls the extractor for that
document's chunks — `tests/test_incremental_update.py` asserts the exact
call count. Every committed `DeliverableVersion` records `changed_sections`
and `carried_over_sections`, so "the parts the new source did not affect stay
exactly as they were" is a diff you can pull from the database, not a claim.

## Known limitations (logged honestly, not hidden)

- Retrieval is exact/regex-based, not embedding-based, in the default SQLite
  path — fine for the fact schema declared above, would need real vector
  search (the Postgres+pgvector path is stubbed for this) at larger scale or
  with a less structured fact set.
- Fact extraction is a deterministic regex extractor by default. It is
  intentionally narrow and auditable rather than broadly "smart"; swapping in
  `AnthropicLLMClient` widens coverage but trades away that determinism.
- Chunking assumes `Clause N` / `Section N` / `Article N` headers; documents
  that structure clauses differently (e.g. numbered lists without a keyword)
  fall back to paragraph-level chunks with no `clause_ref`, which weakens
  citation specificity for those documents.
- The React console is a working review tool, not a polished product UI —
  scoped to what's needed to demonstrate the human gate, not visual design.

## Repository layout

```
backend/app/
  domain/       chunking, facts, contradictions, rules, deliverable, injection
  llm/          LLMClient interface, fake (default) + Anthropic backends
  graph/        LangGraph state, nodes, checkpointing, graph wiring
  services/     runs, gate, commit, concurrency, cost — used by both surfaces
  api/          FastAPI routers
  mcp_server.py MCP tools mirroring the REST API
backend/tests/  one test file per behavior
frontend/       React review console (Vite)
TASK.md         how the ten behaviors map to code, for a reviewer
PROGRESS.md     assumptions and trade-offs logged as they were made
```
