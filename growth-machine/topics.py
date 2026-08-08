"""
The audience and the two topic batches the machine runs on.

Audience (specific enough to be wrong, per the brief's own bar): legal ops
leads and in-house counsel at Series B-D SaaS companies (roughly 50-500
employees) who personally maintain a vendor/contract library in shared
drives or a basic CLM tool, and who research solutions before buying rather
than respond to cold outreach — which is why this machine is a content/
search machine, not an outbound one. This also structurally avoids the
round's hardest rule (never contact a real person or company): a search
machine never contacts anyone, it waits to be found.

Ten named example companies this audience sits inside of (public
knowledge only, never contacted, matching Task 3's own list): Deel,
Remote.com, Flexport, Faire, Ramp, Brex, Instacart, SoFi, Carta, Vanta.

Topics are real search queries this audience plausibly types into Google,
researched by pattern-matching against publicly known legal-ops pain
points (contract renewal management, redlining, clause consistency) — not
scraped from any individual's real search history.
"""

BATCH_1 = [
    {
        "topic": "contract-contradiction-checklist",
        "query": "contract clause contradiction checklist",
        "angle": "A practical, numbered checklist for spotting clauses in the same "
                 "contract that quietly contradict each other before renewal season.",
    },
    {
        "topic": "renewal-notice-period-conflicts",
        "query": "renewal notice period conflicts in SaaS vendor contracts",
        "angle": "Why renewal and termination notice periods are the single most "
                 "common place two clauses in the same contract disagree, with a "
                 "worked example.",
    },
    {
        "topic": "legal-ops-contract-audit-before-renewal",
        "query": "vendor contract audit before renewal season legal ops",
        "angle": "A pre-renewal audit workflow a two-person legal ops team can "
                 "actually run without a dedicated CLM platform.",
    },
]

BATCH_2 = [
    {
        "topic": "ai-redlining-tools-in-house-counsel",
        "query": "AI redlining tools for in-house counsel",
        "angle": "What in-house counsel should actually evaluate in an AI redlining "
                 "tool, beyond the demo, including how it handles unresolved conflicts.",
    },
    {
        "topic": "clause-library-drift-audit",
        "query": "clause library drift audit legal ops",
        "angle": "How a clause library quietly drifts from what contracts actually say, "
                 "and a light audit workflow to catch it quarterly.",
    },
    {
        "topic": "human-in-the-loop-contract-review-ai",
        "query": "human in the loop AI contract review",
        "angle": "Why a human-approval gate on every AI-proposed contract edit is a "
                 "requirement, not a nice-to-have, and what a workable gate looks like.",
    },
]

ALL_BATCHES = {"1": BATCH_1, "2": BATCH_2}
