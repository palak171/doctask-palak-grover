from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.graph.checkpoint import get_checkpointer
from app.graph.nodes import (
    await_gate_node, examine_node, extract_facts_node, ingest_failed_node,
    ingest_node, route_after_ingest,
)
from app.graph.state import GraphState

_compiled = None


def build_graph(checkpointer=None):
    graph = StateGraph(GraphState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("ingest_failed", ingest_failed_node)
    graph.add_node("extract_facts", extract_facts_node)
    graph.add_node("examine", examine_node)
    graph.add_node("await_gate", await_gate_node)

    graph.set_entry_point("ingest")
    graph.add_conditional_edges("ingest", route_after_ingest, {
        "extract_facts": "extract_facts",
        "ingest_failed": "ingest_failed",
    })
    graph.add_edge("ingest_failed", END)
    graph.add_edge("extract_facts", "examine")
    graph.add_edge("examine", "await_gate")
    graph.add_edge("await_gate", END)

    return graph.compile(checkpointer=checkpointer or get_checkpointer())


def get_compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def reset_compiled_graph_for_tests(checkpointer):
    global _compiled
    _compiled = build_graph(checkpointer=checkpointer)
    return _compiled
