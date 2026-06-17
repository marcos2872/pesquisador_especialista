# Pesquisador Especialista

Plataforma web para gerar revisões técnicas em Markdown sobre qualquer tópico de pesquisa. Combina busca em APIs acadêmicas gratuitas (Crossref, OpenAlex, arXiv) com IA (OpenAI/Azure) para produzir relatórios estruturados em 6 seções com fontes verificáveis.

## Stack

- **Backend:** Python 3.11+ (stdlib `http.server`, zero frameworks)
- **Frontend:** React 19 + TypeScript + Vite + Mantine 9
- **IA:** OpenAI-compatible API (Azure OpenAI suportado)
- **Banco:** SQLite (`~/.pesquisador/history.db`)

## Rápido

```bash
cp .env.example .env          # edite com sua OPENAI_API_KEY
make dev                      # API (8000) + UI (5173) em paralelo
```

Individualmente:

```bash
make api                      # só backend → http://127.0.0.1:8000
make ui                       # só frontend → http://localhost:5173
make install                  # instala Python + Node
make test                     # roda pytest
make lint                     # ruff + ESLint
make clean                    # remove caches
```

## API Keys

| Serviço | Variável | Para que serve | Tipo de dado retornado | Cadastro | Obrigatório |
|---|---|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | Geração do relatório via LLM (6 seções) | Texto Markdown estruturado | [platform.openai.com](https://platform.openai.com/api-keys) | Sim |
| Core.ac.uk | `CORE_API_KEY` | Artigos open access de repositórios institucionais | Metadados completos (título, autores, DOI, abstract) | [core.ac.uk/services/api](https://core.ac.uk/services/api/) | Não |
| Semantic Scholar | `SEMANTIC_SCHOLAR_API_KEY` | Artigos com metadados enriquecidos e rede de citações | Artigos com embeddings, influência, citações | [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api) | Não |
| IEEE Xplore | `IEEE_API_KEY` | Artigos de engenharia, computação e tecnologia | Artigos IEEE com metadados completos | [developer.ieee.org](https://developer.ieee.org/) | Não |
| SerpAPI | `SERPAPI_API_KEY` | Google Scholar (artigos) + Google Patents | Resultados de busca estruturados | [serpapi.com](https://serpapi.com/) | Não |
| Espacenet OPS | `EPO_OPS_CONSUMER_KEY` + `SECRET` | Patentes europeias e internacionais | Dados bibliográficos, citações, famílias | [developer.epo.org](https://developer.epo.org/) | Não |
| USPTO | `USPTO_API_KEY` | Patentes americanas | Patentes USPTO com título, inventores, classificação | [developer.uspto.gov](https://developer.uspto.gov/) | Não |
| Lens.org | `LENS_API_TOKEN` | Patentes + literatura acadêmica | Patentes com famílias, citações, jurisdições | [lens.org](https://www.lens.org/) | Não |
| WIPO Patentscope | `WIPO_API_KEY` | Patentes PCT (internacionais) | Patentes WIPO com dados bibliográficos | [patentscope.wipo.int](https://patentscope.wipo.int/) | Não |

> Sem chaves opcionais, o sistema já funciona com Crossref, OpenAlex e arXiv (artigos) — todos gratuitos sem cadastro.

## Documentação técnica

Arquivos em [docs/](docs/):

| Arquivo | Conteúdo |
|---|---|
| `api.md` | Endpoints, exemplos, códigos de erro |
| `models.md` | Dataclasses Article e Patent |
| `architecture.md` | Stack, diretórios, fluxo, providers |
| `components.md` | Componentes React, props, estado |
| `setup.md` | Setup completo, API keys com links de cadastro |

## Testes

```bash
uv run pytest
```
