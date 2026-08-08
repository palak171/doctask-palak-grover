# Growth machine — SuperDocs Round 2, Growth Task 1

A content/search machine: it picks a batch of real pain-point search
queries a specific audience types into Google, drafts a genuinely useful
article for each on SuperDocs, runs an automated compliance pass over the
draft (no invented numbers, no competitor claims, no hard sell), gets each
proposed fix approved or rejected one at a time, and exports the result —
publish-ready, never actually published by the machine itself.

## The audience, defended

**Legal ops leads and in-house counsel at Series B–D SaaS companies
(~50–500 employees) who maintain their own vendor contract library without
a dedicated CLM platform.** Specific enough to be wrong: it excludes
enterprises (who already have CLM budgets and legal headcount) and it
excludes pre-seed startups (who don't have vendor contract volume worth
auditing yet). Ten example companies this audience sits inside, all public
knowledge, none contacted: Deel, Remote.com, Flexport, Faire, Ramp, Brex,
Instacart, SoFi, Carta, Vanta.

## Why a content/search machine, not outbound

This audience researches solutions before buying — they Google their pain
point, they don't respond to cold outreach from a tool they've never heard
of. That channel choice also does something structural: **a search machine
never contacts anyone**, human or company, real or fictional. It sidesteps
this round's hardest, clearest rule (never contact a real person or
company) entirely, rather than tip-toeing around it with invented personas.
Nothing here is sent to any inbox, DM, or feed. What gets published, if
anything, is a human decision made after this round — the machine only
gets content to the export step.

## How the machine works

```
topic batch → draft (chat, template shell) → compliance pass (chat/async, HITL) → export (html)
```

1. **Draft.** `superdocs_client.chat()` sends a template shell plus a
   topic-specific brief (`house_style.DRAFT_PROMPT`) — one SuperDocs
   operation per topic.
2. **Compliance pass.** `start_edit()` (⁠`approval_mode: ask_every_time`)
   asks SuperDocs to check the draft against five house-style rules
   (`house_style.COMPLIANCE_PASS_PROMPT`: no invented stats, no competitor
   claims, at most one soft product mention, no unearned certification
   claims, no sales-pitch closing) and propose one edit per violation.
   Every proposed edit is approved or rejected **individually** — the
   exact same item-by-item Review pattern as the engineer track's
   contradiction detector, reused here on purpose.
3. **Export.** Clean HTML, written to `outputs/batch{n}/{topic}.html`.

## Run it — twice, on fresh batches, without patching in between

```bash
pip install -e ".[dev]"
cp .env.example .env   # fill in SUPERDOCS_API_KEY

python content_machine.py run 1 --auto-approve
python content_machine.py run 2 --auto-approve
```

`topics.py` defines two disjoint batches (`tests/test_content_machine.py`
asserts they don't overlap). Each run writes `outputs/batch{n}/run_log.json`
recording, per topic: draft operation cost, compliance-pass timing, how
many edits were approved vs. rejected, and the output file — this is the
"numbers that show what each stage costs" the brief's own bar asks for.

## The one real produced piece

`outputs/featured/contract-contradiction-checklist.html` — the strongest
result from batch 1, picked by hand after both runs, polished for
publication. It doubles as a natural showcase of the engineer track's
Cross-clause contradiction detector, without ever naming this round or
SuperDocs as more than "one option among several."

## Tests

```bash
pytest -v
```

2 tests, mocked API, no live key, no operations spent — same approach as
the engineer track. They prove the pipeline's control flow (draft never
triggers HITL, the compliance pass's mixed approve/reject payload is
correct, export writes to the right place); they cannot and do not judge
SuperDocs' own drafting quality — that's what the two `outputs/batch*/`
directories and the demo video are for.

## What separates a strong machine, addressed directly

- **Audience specific enough to be wrong, defended anyway:** above.
- **Behaves the second time exactly as it did the first:** batch 2 is a
  disjoint topic set run through the identical, unmodified pipeline — see
  `run_log.json` in both batch folders for the evidence, not just the claim.
- **Numbers on cost and loss per stage:** `run_log.json`'s per-stage
  `ops_charged` and `seconds` fields.
- **Claims never outrun the product:** the compliance pass's rule 4 exists
  specifically to catch this mechanically, not just rely on the drafting
  prompt getting it right once.

## See also

- [`measurement.md`](measurement.md) — the required one-page, honest
  measurement write-up: what would prove this works, where it leaks, what
  breaks at 10x volume, where a human must stay in the loop.
- [`../use-cases-growth.md`](../use-cases-growth.md) — Task 3's use-case
  map, extended with the "how a first conversation would start" column the
  growth track's version of Task 3 asks for.
