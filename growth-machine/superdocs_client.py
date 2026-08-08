"""
Thin SuperDocs REST client for the growth machine. Deliberately the same
shape as the client in the engineer track's cross-clause-contradiction-
detector submission (upload/chat/approve/export) — this folder is
self-contained on purpose (per the brief: "a repository is just a folder
with history, and it does not need to contain" a shared package), so the
client is duplicated rather than imported across projects, with the same
polling-not-SSE reasoning documented there.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

BASE_URL = "https://api.superdocs.app/v1"


class SuperDocsError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"SuperDocs API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class JobTimeout(Exception):
    pass


@dataclass
class ProposedChange:
    change_id: str
    chunk_id: str
    operation: str
    old_html: str
    new_html: str
    ai_explanation: str

    @classmethod
    def from_dict(cls, d: dict) -> "ProposedChange":
        return cls(
            change_id=d["change_id"], chunk_id=d.get("chunk_id", ""),
            operation=d.get("operation", ""), old_html=d.get("old_html", ""),
            new_html=d.get("new_html", ""), ai_explanation=d.get("ai_explanation", ""),
        )


@dataclass
class ExportResult:
    content: bytes
    filename: str


class SuperDocsClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: float = 90.0):
        self._client = httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _raise_for_status(self, response: httpx.Response):
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise SuperDocsError(response.status_code, str(detail))

    def chat(self, message: str, session_id: str, document_html: str | None = None,
              model_tier: str | None = None, thinking_depth: str | None = None) -> dict:
        """POST /v1/chat — used here to draft content from a template shell."""
        payload: dict = {"message": message, "session_id": session_id}
        if document_html is not None:
            payload["document_html"] = document_html
        if model_tier:
            payload["model_tier"] = model_tier
        if thinking_depth:
            payload["thinking_depth"] = thinking_depth
        response = self._client.post("/chat", json=payload)
        self._raise_for_status(response)
        return response.json()

    def start_edit(self, message: str, session_id: str) -> dict:
        """POST /v1/chat/async with approval_mode='ask_every_time' — the style/compliance review pass."""
        response = self._client.post("/chat/async", json={
            "message": message, "session_id": session_id, "approval_mode": "ask_every_time",
        })
        self._raise_for_status(response)
        return response.json()

    def get_job(self, job_id: str) -> dict:
        response = self._client.get(f"/jobs/{job_id}")
        self._raise_for_status(response)
        return response.json()

    def wait_for_job(self, job_id: str, poll_interval: float = 2.0, timeout: float = 600.0) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            job = self.get_job(job_id)
            if job["status"] in ("completed", "failed", "awaiting_approval", "cancelled"):
                return job
            if time.monotonic() > deadline:
                raise JobTimeout(f"job {job_id} still '{job['status']}' after {timeout}s")
            time.sleep(poll_interval)

    def pending_changes(self, job: dict) -> list[ProposedChange]:
        return [ProposedChange.from_dict(c) for c in job.get("metadata", {}).get("pending_changes", [])]

    def approve_changes(self, session_id: str, job_id: str,
                          decisions: list[tuple[str, bool, str | None]]) -> dict:
        changes = []
        for change_id, approved, feedback in decisions:
            entry = {"change_id": change_id, "approved": approved}
            if feedback:
                entry["feedback"] = feedback
            changes.append(entry)
        response = self._client.post(f"/chat/{session_id}/approve",
                                       json={"job_id": job_id, "approved": True, "changes": changes})
        self._raise_for_status(response)
        return response.json()

    def export_document(self, session_id: str, format: str = "html") -> ExportResult:
        response = self._client.post("/documents/export", json={"session_id": session_id, "format": format})
        self._raise_for_status(response)
        filename = "export"
        disposition = response.headers.get("content-disposition", "")
        if "filename=" in disposition:
            filename = disposition.split("filename=")[-1].strip('"; ')
        return ExportResult(content=response.content, filename=filename)
