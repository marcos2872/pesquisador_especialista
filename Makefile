SHELL := /bin/bash
.PHONY: dev api ui install test lint clean

dev:  ## Sobe API (8000) + UI (5173) em paralelo
	@trap 'kill 0' EXIT; \
	$(MAKE) api & \
	$(MAKE) ui; \
	wait

api:  ## Sobe apenas o backend (http://127.0.0.1:8000)
	@uv run app.py

ui:   ## Sobe apenas o frontend dev (http://localhost:5173)
	@cd ui && npm run dev

install:  ## Instala dependências Python + Node
	uv sync
	cd ui && npm install

test:  ## Roda testes
	uv run pytest

lint:  ## Roda lint Python + TypeScript
	@ruff check . || true
	cd ui && npm run lint

clean:  ## Remove caches e build artifacts
	rm -rf ui/dist ui/node_modules
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
