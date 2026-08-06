.PHONY: install test run mcp frontend

install:
	cd backend && pip install -e ".[dev]"

test:
	cd backend && pytest -q

run:
	cd backend && uvicorn app.main:app --reload --port 8000

mcp:
	cd backend && python -m app.mcp_server

frontend:
	cd frontend && npm install && npm run dev
