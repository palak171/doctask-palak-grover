from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.piles import router as piles_router
from app.api.runs import router as runs_router
from app.db import init_db

app = FastAPI(
    title="DocPile Agent",
    description="Agentic system that owns a pile of documents end to end — "
                "SuperDocs Round 2, Task 1.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(piles_router)
app.include_router(runs_router)
