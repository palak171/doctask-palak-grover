# Measurement — one honest page

**What would prove this machine works.** Three numbers, in order of how
early they'd tell me something: (1) search impressions and average
position for the exact query each piece targets, measured via Search
Console once published — this tells me whether the piece is findable at
all, independent of whether anyone acts on it; (2) organic click-through
from those impressions to the page — tells me whether the headline and
snippet actually earn the click; (3) scroll depth / time-on-page past the
checklist section — a legal ops reader who bails before the checklist
never got the value the piece promised, regardless of how they arrived.
Signups or trial starts attributed to the piece would be the eventual
business number, but it's three steps downstream of what this machine
directly controls, so I would not use it to judge the machine itself —
only to judge the whole funnel it feeds into.

**I did not run this against real traffic.** Publishing anything the
machine produces is explicitly not this machine's job (nothing it makes is
sent anywhere while this round runs), so every number above is what I
would measure once a human decides to publish, not something I can report
today. What I can report today, honestly: two batches, six topics, `run_log.json`
in each `outputs/batch*/` folder recording real operation counts and
wall-clock time per stage against the live SuperDocs API. That is the
extent of what actually happened; treat the search-funnel numbers above as
the measurement plan, not a result.

**Where it leaks, on the funnel I can already see without traffic data.**
Between "topic chosen" and "piece exported," the leak I watched for
directly was the compliance pass silently doing nothing — a pass that
always reports zero violations is indistinguishable from a pass that isn't
actually checking. Both batches' `run_log.json` show at least one edit
proposed and decided per topic, which is the minimum evidence the check is
live rather than decorative. Downstream of export, the leak I can't
measure without publishing is the gap between "technically correct" and
"a busy legal ops lead reads past paragraph two" — SEO-technical quality
and reader quality are not the same thing, and this machine only checks
the first.

**What breaks first at 10x volume (60 topics instead of 6).** The topic
list itself: `topics.py` is a curated, hand-picked batch, and finding 60
genuinely distinct, non-overlapping pain-point queries by hand does not
scale the way the pipeline that drafts them does. The compliance rules
would also start missing violations specific to topics the five hand-written
rules didn't anticipate — five rules were sized for six topics I could
personally read end to end, not sixty I couldn't. Both are the same
failure shape: the automated part of the pipeline scales cleanly, the
part that still depends on my own judgment does not.

**Where a human must stay in the loop, non-negotiably.** Every compliance
edit, already (this machine never auto-applies a fix, same as the
engineer track's contradiction detector). Beyond that: the actual decision
to publish anything, since that's the one step this round explicitly
reserves for a human and for after the round; and periodically re-reading
the five compliance rules themselves against a sample of output, since a
rule that was right for batch 1's topics can go stale against a topic
batch 1 never anticipated, and nothing in this pipeline would notice that
on its own.
