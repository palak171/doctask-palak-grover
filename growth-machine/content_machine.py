"""
The growth machine: topic batch -> draft (chat) -> compliance review (HITL,
same pattern as the engineer track's contradiction detector) -> export.

Run it twice, on two independent batches, without patching anything in
between — that's the brief's own bar for "a machine that behaves the second
time exactly as it did the first."

Usage:
    python content_machine.py run 1 --auto-approve
    python content_machine.py run 2 --auto-approve
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

from house_style import COMPLIANCE_PASS_PROMPT, DRAFT_PROMPT, TEMPLATE_SHELL
from superdocs_client import JobTimeout, SuperDocsClient, SuperDocsError
from topics import ALL_BATCHES

OUTPUT_ROOT = Path(__file__).parent / "outputs"


def run_topic(client: SuperDocsClient, topic: dict, auto_approve: bool, out_dir: Path) -> dict:
    session_id = f"growth-{topic['topic']}-{uuid.uuid4().hex[:6]}"
    log: dict = {"topic": topic["topic"], "session_id": session_id, "stages": []}

    t0 = time.monotonic()
    print(f"\n=== {topic['topic']} ===")
    print("Drafting...")
    shell = TEMPLATE_SHELL.format(title=topic["query"].title())
    draft = client.chat(
        DRAFT_PROMPT.format(query=topic["query"], angle=topic["angle"]),
        session_id, document_html=shell,
    )
    draft_usage = draft.get("usage", {})
    log["stages"].append({"stage": "draft", "seconds": round(time.monotonic() - t0, 1),
                            "ops_charged": draft_usage.get("ops_charged"),
                            "monthly_remaining": draft_usage.get("monthly_remaining")})

    print("Running compliance pass (HITL)...")
    t1 = time.monotonic()
    started = client.start_edit(COMPLIANCE_PASS_PROMPT, session_id)
    job_id = started["job_id"]
    edits_approved = 0
    edits_rejected = 0

    while True:
        job = client.wait_for_job(job_id)
        if job["status"] == "failed":
            log["stages"].append({"stage": "compliance", "error": job.get("error")})
            break
        if job["status"] == "awaiting_approval":
            changes = client.pending_changes(job)
            decisions = []
            for change in changes:
                print(f"  [{change.change_id}] {change.ai_explanation}")
                approved = True if auto_approve else input("    Approve? [y/N]: ").strip().lower() == "y"
                decisions.append((change.change_id, approved, None))
                edits_approved += approved
                edits_rejected += not approved
            client.approve_changes(session_id, job_id, decisions)
            continue
        if job["status"] == "completed":
            break

    log["stages"].append({"stage": "compliance", "seconds": round(time.monotonic() - t1, 1),
                            "edits_approved": edits_approved, "edits_rejected": edits_rejected})

    print("Exporting...")
    result = client.export_document(session_id, format="html")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{topic['topic']}.html"
    out_path.write_bytes(result.content)
    log["output_file"] = str(out_path)
    log["total_seconds"] = round(time.monotonic() - t0, 1)
    print(f"Wrote {out_path} ({len(result.content)} bytes) in {log['total_seconds']}s")
    return log


def main():
    load_dotenv()
    api_key = os.environ.get("SUPERDOCS_API_KEY")
    if not api_key:
        print("Set SUPERDOCS_API_KEY (env or .env) first.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="Run one batch of topics end to end.")
    p_run.add_argument("batch", choices=["1", "2"])
    p_run.add_argument("--auto-approve", action="store_true")
    args = parser.parse_args()

    batch = ALL_BATCHES[args.batch]
    run_dir = OUTPUT_ROOT / f"batch{args.batch}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logs = []
    with SuperDocsClient(api_key) as client:
        for topic in batch:
            try:
                logs.append(run_topic(client, topic, args.auto_approve, run_dir))
            except (SuperDocsError, JobTimeout) as exc:
                print(f"FAILED on {topic['topic']}: {exc}", file=sys.stderr)
                logs.append({"topic": topic["topic"], "error": str(exc)})

    log_path = run_dir / "run_log.json"
    log_path.write_text(json.dumps(logs, indent=2))
    print(f"\nBatch {args.batch} done. Log: {log_path}")


if __name__ == "__main__":
    main()
