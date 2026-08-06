# TASK.md — how to work with this repo

This is the SuperDocs Round 2 submission for the Full-Stack AI Engineer role
(Palak Grover). It covers **Task 1** (the mandatory shared agentic system)
from the engineering task document. Task 2 (the assigned "Cross-clause
contradiction detector" built on the actual SuperDocs API) lives in a
separate PR against `superdocs-builds`, not in this repository — the brief
requires them to be split that way.

## What "done" means here

The brief lists ten behaviors every submission is checked against. This repo
is organized so each one has a single, findable place it's implemented and a
single, findable test that proves it:

| # | Behavior | Implementation | Test |
|---|---|---|---|
| 1 | Visible stages, decisions can change path | `app/graph/nodes.py` (each node writes a `RunStep`) | `tests/test_resume.py` |
| 2 | Survives being stopped | `app/graph/checkpoint.py` (SqliteSaver) | `tests/test_resume.py` |
| 3 | Human holds the gate, item by item | `app/services/gate.py` | `tests/test_gate.py` |
| 4 | Machine can drive it end to end | `app/mcp_server.py` mirrors `app/api/` | `tests/test_mcp_parity.py` |
| 5 | Never bluffs | `app/domain/rules.py` (`unsupported`/`no_data` statuses) | `tests/test_no_bluffing.py` |
| 6 | Stranger can run it in minutes | `README.md` Quickstart, SQLite default | (manual — see README) |
| 7 | Proves itself without a live key | `app/llm/fake.py` default backend | entire `tests/` suite |
| 8 | Doesn't take orders from documents | `app/domain/injection.py` + `app/llm/base.py` prompt envelope | `tests/test_injection_defense.py` |
| 9 | Concurrent runs don't corrupt state | `app/services/concurrency.py` (optimistic version check) | `tests/test_concurrency.py` |
| 10 | Knows what it cost | `app/models.py:CostEvent`, `app/api/cost.py` | `tests/test_cost_reporting.py` |

## Working method

- Run tests before and after any change: `make test`.
- The fake LLM backend (`app/llm/fake.py`) is the default and what every test
  uses. Do not make a test depend on `ANTHROPIC_API_KEY` being set.
- Every ambiguous call made while building this is logged in `PROGRESS.md`
  with the reasoning, per the task brief's instruction.
