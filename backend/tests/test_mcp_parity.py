"""
Behavior 4: "A machine can drive it end to end... The gate is part of that
flow: approval is an operation your machine interface exposes." This drives
the ENTIRE flow — upload, run, inspect findings, approve one, reject
another, commit — using only the MCP tool functions (no REST calls, no
direct service-layer calls), proving the machine surface alone is sufficient.
"""
import base64

from app import mcp_server as mcp
from tests.conftest import CONTRACT_TWO_CONTRADICTIONS


def test_full_flow_driven_entirely_through_mcp_tools():
    pile = _call(mcp.create_pile, name="Vendor Contracts")
    content_b64 = base64.b64encode(CONTRACT_TWO_CONTRADICTIONS.encode()).decode()

    doc = _call(mcp.upload_document, pile_id=pile["id"], filename="contract.txt", content_base64=content_b64)
    run = _call(mcp.start_run, pile_id=pile["id"], document_ids=[doc["id"]])
    assert run["status"] == "awaiting_gate"

    findings = _call(mcp.list_run_findings, run_id=run["id"])
    contradictions = [f for f in findings if f["kind"] == "contradiction"]
    assert len(contradictions) == 2

    _call(mcp.decide_finding, finding_id=contradictions[0]["id"], decision="approve", actor="agent")
    _call(mcp.decide_finding, finding_id=contradictions[1]["id"], decision="reject", actor="agent",
          reason="needs review")

    result = _call(mcp.commit_run, run_id=run["id"])
    assert result["version_number"] == 1

    deliverable = _call(mcp.get_pile_deliverable, pile_id=pile["id"])
    assert deliverable["is_committed"] is True

    cost = _call(mcp.get_run_cost, run_id=run["id"])
    assert cost["total_tokens"] > 0

    steps = _call(mcp.get_run_steps, run_id=run["id"])
    stage_names = [s["stage_name"] for s in steps]
    assert stage_names == ["ingest", "extract_facts", "examine", "await_gate", "commit"]


def _call(tool, **kwargs):
    """FastMCP-style tool decorators sometimes wrap the function (exposing the
    original via `.fn`) and sometimes return it unchanged, depending on SDK
    version. Handle both so this test isn't coupled to that detail."""
    fn = getattr(tool, "fn", tool)
    return fn(**kwargs)
