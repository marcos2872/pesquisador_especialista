# AGENTS.md — pesquisador-especialista

## Stack

- **Backend**: Python 3.11+ stdlib `http.server` (no Flask/FastAPI). Entry: `app.py` (delegates to `server.app.main`).
- **Frontend**: React 19 + TypeScript + Vite + Mantine 9. Entry: `ui/src/main.tsx`.
- **AI**: OpenAI-compatible API (Azure OpenAI supported via `OPENAI_BASE_URL`).
- **DB**: SQLite at `~/.pesquisador/history.db`.
- **Package mgmt**: `uv` (Python), `npm` (ui).

## Commands

```bash
# Backend dev
cp .env.example .env  # then edit OPENAI_API_KEY
uv run app.py          # starts on http://127.0.0.1:8000

# Frontend dev (separate terminal)
cd ui && npm install && npm run dev           # http://localhost:5173, proxies /api → :8000

# Frontend build
cd ui && npm run build                        # output → ui/dist/ (served by backend in prod)

# Tests
uv run pytest                                 # tests in server/tests/

# Lint
ruff check                                     # Python
cd ui && npm run lint                          # TypeScript/React
```

## Architecture

```
app.py → server/app.py → ResearchHandler
  GET  /, /index.html           → serves ui/dist/index.html
  GET  /api/history             → list_researches()
  GET  /api/history/{id}        → get_research(id)
  POST /api/research            → generate_report(topic) → save_research(...)
  DELETE /api/history/{id}      → delete_research(id)
```

- `server/services/research_service.py` orchestrates: collect real sources → call OpenAI → validate → sanitize.
- Source collection uses free APIs (Crossref, OpenAlex, arXiv, Core.ac.uk); no keys required.
- `ENABLE_REAL_SEARCH=1` (default) enables real source fetching; `0` skips it.

## Key constraints

- **No `OPENAI_API_KEY`** → endpoint returns 502.
- **No web framework** — `BaseHTTPRequestHandler` with manual routing, JSON serialization, content-type headers.
- Production build of frontend is expected at `ui/dist/` — `STATIC_DIR` in `server/config.py`.
- `.env` is auto-loaded by `server/app.py` (via `python-dotenv`).
- Tests live in `server/tests/` (`testpaths` in `pyproject.toml`). `conftest.py` adds project root to `sys.path`.

## Testing quirks

- Heavily uses `unittest.mock.patch` for external calls (OpenAI, search APIs, HTTP fetches).
- `SEARCH_QUERY_DELAY_SECONDS=0` in env to speed up tests.
- Integration tests (`test_app_integration.py`) mock `server.services.source_collector` and `server.utils.fetcher`.

## Constantes de coleta (limites)

| Constante | Arquivo | Valor | Efeito |
|---|---|---|---|
| `MAX_QUERY_VARIANTS` | `source_collector.py` | 5 | Até 5 queries geradas por tópico |
| `ARTICLES_PER_QUERY` | `source_collector.py` | 8 | Artigos buscados por query (antes da dedup) |
| `PATENTS_PER_QUERY` | `source_collector.py` | 6 | Patentes buscadas por query (antes da dedup) |
| `DEFAULT_MAX_RESULTS` | `academic.py` | 10 | Artigos finais retornados por `search_articles()` |
| `PROVIDER_MULTIPLIER` | `academic.py` | 2 | Provider busca `max_results × 2` |
| `DEFAULT_MAX_RESULTS` | `patents.py` | 5 | Patentes finais retornadas por `search_patents()` |
| `PROVIDER_MULTIPLIER` | `patents.py` | 2 | Provider busca `max_results × 2` |
| `SOURCES_MAX_ARTICLES` | env / `prompt_enrichment.py` | 50 | Teto de artigos no prompt (nunca atingido) |
| `SOURCES_MAX_PATENTS` | env / `prompt_enrichment.py` | 30 | Teto de patentes no prompt (nunca atingido) |

## Project conventions

- Python: no type stubs in prod code (stdlib only), `ruff` for lint.
- Frontend: TypeScript strict mode (`noUnusedLocals`, `noUnusedParameters`), `verbatimModuleSyntax`.
- Prompt templates in `server/prompts/` (system + user). AI output must follow a rigid 6-section Markdown structure.
- All links in AI reports must be direct (DOIs, patent URLs), never homepage/search-page URLs.
