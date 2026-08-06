"""
Behavior 2: "It survives being stopped." LangGraph's SqliteSaver persists a
checkpoint to a real file after every node completes. Killing the process
mid-run and invoking the graph again with the same `thread_id` (== Run.id)
resumes from the last completed node — nothing finished is redone, nothing
finished is lost.

File-backed (not the in-memory saver) on purpose: an in-memory saver would
make "kill -9 and restart" indistinguishable from "never happened", which is
exactly the case this behavior is supposed to prove.
"""
from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import CHECKPOINT_DB_PATH

_conn: sqlite3.Connection | None = None
_saver: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    global _conn, _saver
    if _saver is None:
        _conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
        _saver = SqliteSaver(_conn)
    return _saver


def reset_checkpointer_for_tests(path: str):
    """Used by tests that need an isolated checkpoint file per test."""
    global _conn, _saver
    if _conn is not None:
        _conn.close()
    _conn = sqlite3.connect(path, check_same_thread=False)
    _saver = SqliteSaver(_conn)
    return _saver
