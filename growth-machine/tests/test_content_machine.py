"""
Mocked end-to-end test of the pipeline: draft -> compliance HITL -> export.
No live key, no network call — same approach as the engineer track's
contradiction-detector tests. Proves our orchestration; SuperDocs' own
drafting quality is judged from the actual exported outputs, not a test.
"""
import json

import httpx
import respx

from content_machine import run_topic
from superdocs_client import SuperDocsClient
from topics import ALL_BATCHES

API = "https://api.superdocs.app/v1"


def test_both_batches_are_independent_and_non_empty():
    assert len(ALL_BATCHES["1"]) >= 1
    assert len(ALL_BATCHES["2"]) >= 1
    topics_1 = {t["topic"] for t in ALL_BATCHES["1"]}
    topics_2 = {t["topic"] for t in ALL_BATCHES["2"]}
    assert topics_1.isdisjoint(topics_2)  # batch 2 is genuinely fresh, not a repeat


@respx.mock
def test_run_topic_drafts_reviews_and_exports(tmp_path):
    topic = ALL_BATCHES["1"][0]

    chat_route = respx.post(f"{API}/chat").mock(
        return_value=httpx.Response(200, json={
            "response": "Drafted.",
            "document_changes": {"updated_html": "<h1>Draft</h1><p>...</p>"},
            "usage": {"ops_charged": 1, "monthly_remaining": 499},
        })
    )
    respx.post(f"{API}/chat/async").mock(return_value=httpx.Response(200, json={"job_id": "job-1"}))

    awaiting = httpx.Response(200, json={
        "status": "awaiting_approval",
        "metadata": {"pending_changes": [
            {"change_id": "ch_1", "chunk_id": "c1", "operation": "edit",
             "old_html": "<p>$50,000 saved</p>", "new_html": "<p>time saved</p>",
             "ai_explanation": "Removed an invented dollar figure (rule 1)."},
        ]},
    })
    completed = httpx.Response(200, json={"status": "completed", "result": {"response": "1 edit applied."}})
    respx.get(f"{API}/jobs/job-1").mock(side_effect=[awaiting, completed])
    approve_route = respx.route(method="POST", url__regex=rf"{API}/chat/growth-{topic['topic']}-[0-9a-f]+/approve").mock(
        return_value=httpx.Response(200, json={}),
    )
    respx.post(f"{API}/documents/export").mock(
        return_value=httpx.Response(
            200, content=b"<html>final</html>",
            headers={"content-disposition": f'attachment; filename="{topic["topic"]}.html"'},
        )
    )

    with SuperDocsClient("sk_test") as client:
        log = run_topic(client, topic, auto_approve=True, out_dir=tmp_path)

    assert "approval_mode" not in json.loads(chat_route.calls.last.request.content)  # draft never HITL
    assert log["stages"][1]["edits_approved"] == 1
    assert log["stages"][1]["edits_rejected"] == 0
    assert approve_route.called
    output_file = tmp_path / f"{topic['topic']}.html"
    assert output_file.read_bytes() == b"<html>final</html>"
    assert log["output_file"] == str(output_file)
