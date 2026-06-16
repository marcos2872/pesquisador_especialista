# Estrutura Modular do Projeto

## Visão Geral

O projeto foi refatorado para seguir o princípio de **responsabilidade única**, separando as ~540 linhas do `app.py` original em módulos especializados.

## Organização dos Arquivos

### Raiz do Projeto

| Arquivo | Responsabilidade | Linhas |
|---------|-----------------|--------|
| `app.py` | Inicialização do servidor HTTP | 18 |
| `main.py` | Ponto de entrada | 14 |
| `config.py` | Configurações de ambiente | 44 |
| `STRUCTURE.md` | Documentação desta estrutura | - |
| `REFACTORING.md` | Documentação da refatoração | - |

### `services/` - Camada de Negócio

| Arquivo | Responsabilidade |
|---------|-----------------|
| `ai_service.py` | Integração com OpenAI/Azure API |
| `source_service.py` | Validação de URLs e fontes primárias |
| `report_service.py` | Sanitização de links e formatação |
| `research_service.py` | Orquestração do fluxo de pesquisa |

### `handlers/` - Camada de Apresentação

| Arquivo | Responsabilidade |
|---------|-----------------|
| `research_handler.py` | Rotas HTTP (`GET /`, `POST /api/research`) |

### `agent/` - Prompts

| Arquivo | Responsabilidade |
|---------|-----------------|
| `systemprompt.md` | Prompt de sistema (persona do pesquisador) |
| `userprompt.md` | Template do prompt do usuário |

### `models/` - Modelos de Dados

| Arquivo | Responsabilidade |
|---------|-----------------|
| `article.py` | Dataclass `Article` (artigos acadêmicos) |
| `patent.py` | Dataclass `Patent` (patentes) |
| `__init__.py` | Exporta `Article` e `Patent` |

### `utils/` - Utilitários

| Arquivo | Responsabilidade |
|---------|-----------------|
| `http_client.py` | Cliente HTTP com retry (429/5xx), rate limiting, logging |
| `fetcher.py` | Download de PDFs/HTML, extração de snippets, validação de URLs |
| `search/academic.py` | Busca paralela em 7 APIs de artigos (Crossref, OpenAlex, arXiv, Core, Semantic Scholar, IEEE, SerpAPI) |
| `search/patents.py` | Busca paralela em 6 APIs de patentes (EPO, USPTO, Lens, WIPO, SerpAPI, PatentsView) |
| `search/ieee.py` | Provider IEEE Xplore |
| `search/serpapi.py` | Providers Google Scholar / Google Patents |
| `search/wipo.py` | Provider WIPO Patentscope |
| `search/prompt_enrichment.py` | Formatação de contexto para prompt do LLM |

### `static/` - Frontend

| Arquivo | Responsabilidade |
|---------|-----------------|
| `index.html` | Interface do usuário |

## Fluxo de Execução

```
Usuario → GET / → handlers/research_handler.py → _serve_index()
                     ↓
            POST /api/research → handlers/research_handler.py → do_POST()
                     ↓
            services/research_service.py → generate_report()
                     ↓
    ┌────────────┬───────────────┬──────────────┐
    ↓            ↓               ↓              ↓
ai_service   source_service  report_service  (internamente)
(call_openai) (validate)    (sanitize)
```

## Principais Mudanças

### Antes

- `app.py`: 540 linhas, mistura HTTP, IA, validação, sanitização
- Dificuldade de teste
- Difícil de manter

### Depois

- `app.py`: 18 linhas, apenas servidor
- Serviços especializados por responsabilidade
- Fácil testar cada componente isoladamente
- Fácil adicionar novas funcionalidades

## Como Executar

```bash
# Opção 1: Via app.py (recomendado)
uv run --env-file .env app.py

# Opção 2: Via main.py
uv run python3 main.py
```

## Como Testar Novos Serviços

### Exemplo: Testar `ai_service.py`

```python
# tests/test_ai_service.py
from services.ai_service import extract_openai_text

def test_extract_openai_text():
    data = {"output_text": "Hello world"}
    assert extract_openai_text(data) == "Hello world"
```

### Exemplo: Testar `source_service.py`

```python
from services.source_service import _is_search_or_home_url

def test_is_search_or_home_url():
    assert _is_search_or_home_url("https://scholar.google.com")
    assert not _is_search_or_home_url("https://doi.org/10.xxxx/xxxxx")
```

## Próximos Passos Sugeridos

1. ~~**Mover modelos de dados** → `models/article.py` + `models/patent.py`~~ ✅ Concluído
2. ~~**Centralizar HTTP client** → `utils/http_client.py` com retry 429/5xx, paralelização~~ ✅ Concluído
3. **Adicionar logging** → `logging.conf` + `logger = logging.getLogger(__name__)`
4. **Injeção de dependência** → Facilitar mocks em testes
5. **Testes unitários** → Cobertura por serviço
6. **CI/CD** → GitHub Actions para validar commits

## Padrões de Design Utilizados

- **Single Responsibility Principle (SRP)**: Cada arquivo tem uma única razão para mudar
- **Dependency Inversion**: Serviços recebem dependências via parâmetros
- **Separation of Concerns**: Camadas distintas (HTTP, Negócio, Dados)

## Compatibilidade

A lógica foi preservada intacta. Funções mantêm mesmos nomes e assinaturas. Não há quebra de compatibilidade.
