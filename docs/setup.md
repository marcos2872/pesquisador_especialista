# Guia de Setup

## Pré-requisitos

- Python 3.11+
- Node.js 20+
- [make](https://www.gnu.org/software/make/) (Linux: nativo; Windows: via Git Bash/WSL/chocolatey)
- [uv](https://github.com/astral-sh/uv) (gerenciador de pacotes Python)
- npm (gerenciador de pacotes Node)

## Setup inicial

```bash
git clone <repo>
cd pesquisador_especialista
cp .env.example .env    # edite com suas chaves
make install            # instala Python + Node
```

## Comandos disponíveis

| Comando | Descrição |
|---|---|
| `make dev` | API (8000) + UI (5173) em paralelo |
| `make api` | Só o backend (`uv run app.py`) |
| `make ui` | Só o frontend dev |
| `make install` | Instala dependências Python + Node |
| `make test` | Roda pytest |
| `make lint` | Roda ruff + ESLint |
| `make clean` | Remove caches e build artifacts |

## Backend (manual)

```bash
uv run app.py
# → http://127.0.0.1:8000
```

## Frontend dev (manual)

```bash
cd ui && npm install && npm run dev
# → http://localhost:5173 (proxy /api → 127.0.0.1:8000)
```

## Frontend produção

```bash
cd ui && npm run build
# Build em ui/dist/ — servido pelo backend em /
```

## Testes

```bash
make test
# ou: uv run pytest
```

## Lint

```bash
make lint
# ou: ruff check . && cd ui && npm run lint
```

## API Keys

### Obrigatória

| Serviço | Variável | Cadastro | Preço |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | Pago por uso |

### Opcionais — Artigos

| Serviço | Variável | Cadastro | Preço |
|---|---|---|---|
| Core.ac.uk | `CORE_API_KEY` | [core.ac.uk/services/api](https://core.ac.uk/services/api/) | Gratuito |
| Semantic Scholar | `SEMANTIC_SCHOLAR_API_KEY` | [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api) | Gratuito |
| IEEE Xplore | `IEEE_API_KEY` | [developer.ieee.org](https://developer.ieee.org/) | Gratuito |
| SerpAPI (Google Scholar) | `SERPAPI_API_KEY` | [serpapi.com](https://serpapi.com/) | Trial gratuito, depois pago |
| Unpaywall | `UNPAYWALL_EMAIL` | [unpaywall.org/products/api](https://unpaywall.org/products/api) | Gratuito (só email) |

### Opcionais — Patentes

| Serviço | Variável | Cadastro | Preço |
|---|---|---|---|
| Espacenet OPS | `EPO_OPS_CONSUMER_KEY` + `SECRET` | [developer.epo.org](https://developer.epo.org/) | Gratuito |
| USPTO | `USPTO_API_KEY` | [developer.uspto.gov](https://developer.uspto.gov/) | Gratuito |
| Lens.org | `LENS_API_TOKEN` | [lens.org](https://www.lens.org/) | Gratuito (cadastro acadêmico) |
| WIPO Patentscope | `WIPO_API_KEY` | [patentscope.wipo.int](https://patentscope.wipo.int/) | Gratuito |
| SerpAPI (Google Patents) | `SERPAPI_API_KEY` | [serpapi.com](https://serpapi.com/) | Trial gratuito, depois pago |

> **Sem nenhuma chave opcional**, o sistema já busca artigos em Crossref, OpenAlex e arXiv (todos gratuitos, sem cadastro). Para patentes sem chave, apenas o PatentsView é usado (descontinuado, pode falhar).

## Variáveis de ambiente

| Variável | Padrão | Obrigatória | Descrição |
|---|---|---|---|
| `OPENAI_API_KEY` | — | Sim | Chave da API OpenAI |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Não | Endpoint (use Azure se necessário) |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Não | Modelo ou deployment name |
| `OPENAI_TIMEOUT_SECONDS` | `240` | Não | Timeout da chamada OpenAI |
| `ENABLE_REAL_SEARCH` | `1` | Não | `0` desativa busca real (usa só IA) |
| `SEARCH_TIMEOUT_SECONDS` | `30` | Não | Timeout das APIs de busca |
| `SEARCH_QUERY_DELAY_SECONDS` | `1.0` | Não | Delay entre queries |
| `CORE_API_KEY` | — | Não | Core.ac.uk |
| `SEMANTIC_SCHOLAR_API_KEY` | — | Não | Semantic Scholar |
| `IEEE_API_KEY` | — | Não | IEEE Xplore |
| `SERPAPI_API_KEY` | — | Não | SerpAPI (Google Scholar + Patents) |
| `EPO_OPS_CONSUMER_KEY` | — | Não | Espacenet OPS |
| `EPO_OPS_CONSUMER_SECRET` | — | Não | Espacenet OPS |
| `USPTO_API_KEY` | — | Não | USPTO |
| `LENS_API_TOKEN` | — | Não | Lens.org |
| `WIPO_API_KEY` | — | Não | WIPO Patentscope |
