"""
Central config. Defaults are chosen so a stranger can clone this repo and run
it — tests and the demo path — with zero external services: SQLite for
storage, a SQLite-backed checkpoint file for graph resumability, and a fake
deterministic "LLM" for extraction so nothing costs money or needs a key.

Postgres + pgvector is supported for production-scale retrieval (set
DATABASE_URL to a postgresql+psycopg:// URL); see README "Why SQLite by
default" for the trade-off this encodes.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DOCPILE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'docpile.db'}")
CHECKPOINT_DB_PATH = os.environ.get("DOCPILE_CHECKPOINT_DB", str(DATA_DIR / "checkpoints.sqlite"))

WATCH_ROOT = Path(os.environ.get("DOCPILE_WATCH_ROOT", DATA_DIR / "watched"))
WATCH_ROOT.mkdir(parents=True, exist_ok=True)

# Presence of a real key opts into a real LLM backend; absence keeps the fake
# deterministic extractor, which is what tests and CI always use.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
LLM_BACKEND = os.environ.get("DOCPILE_LLM_BACKEND", "anthropic" if ANTHROPIC_API_KEY else "fake")

# Operation budget, mirroring the "budget your operations" note in the task
# brief: a small-sample mode and a stopping rule.
MAX_CHUNKS_PER_RUN = int(os.environ.get("DOCPILE_MAX_CHUNKS_PER_RUN", "500"))
MAX_LLM_CALLS_PER_RUN = int(os.environ.get("DOCPILE_MAX_LLM_CALLS_PER_RUN", "200"))
