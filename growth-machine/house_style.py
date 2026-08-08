"""
The house style the machine drafts against and then checks itself against.
Kept as data, not scattered across prompts, so "behaves the second time
exactly as it did the first" (What Separates A Strong Machine) is a property
of the config, not of luck.
"""

TEMPLATE_SHELL = """\
<h1>{title}</h1>
<p><em>Draft — audience: legal ops leads and in-house counsel at fast-growing SaaS companies.</em></p>
"""

DRAFT_PROMPT = """\
Write a short, genuinely useful article (400-600 words) for legal ops leads \
and in-house counsel at fast-growing SaaS companies (50-500 employees) who \
maintain their own vendor contract library without a dedicated CLM platform.

Topic: {query}
Angle: {angle}

Structure: a one-sentence hook naming the specific pain, a short explanation \
of why it happens, a concrete numbered checklist or worked example the \
reader can use today, and one short closing paragraph. Mention that \
AI-assisted contract review tools exist as one option among several \
(manual audits, outside counsel, a CLM platform) — never claim this is the \
only or best solution, and never name or disparage a competing product.

Do not invent statistics, survey results, or specific dollar figures. Do \
not claim any certification, compliance status, or capability SuperDocs \
does not document at docs.superdocs.app. Write in plain, direct language a \
busy legal ops lead would actually read to the end.
"""

COMPLIANCE_PASS_PROMPT = """\
Review this draft against these rules and propose an edit for every \
violation found, one edit per violation:

1. No invented statistics, survey data, or specific dollar figures anywhere.
2. No claim that names or disparages a competing product.
3. No more than one soft mention of AI-assisted contract review as an option \
   (not a hard sell, not repeated).
4. No claimed certification, compliance status, or capability beyond what \
   docs.superdocs.app documents today.
5. The closing paragraph must not read as a sales pitch — it should return \
   to the reader's problem, not to a product.

If the draft already satisfies all five rules, say so plainly and propose \
no edits.
"""
