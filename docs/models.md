# Modelos de Dados

## Article

**Arquivo:** `server/models/article.py`

Dataclass que representa um artigo acadêmico encontrado nas APIs de busca.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `title` | `str` | Sim | Título do artigo |
| `authors` | `list[str]` | Não | Lista de autores |
| `year` | `int \| None` | Não | Ano de publicação |
| `venue` | `str \| None` | Não | Periódico ou conferência |
| `doi` | `str \| None` | Não | DOI (sem prefixo `https://doi.org/`) |
| `url` | `str \| None` | Não | Landing page do artigo |
| `abstract` | `str \| None` | Não | Resumo |
| `pdf_url` | `str \| None` | Não | Link direto para PDF (via Unpaywall, arXiv) |
| `source_api` | `str` | Sim (default `"unknown"`) | Provider que retornou o registro |

**Validação:** `is_valid()` retorna `True` se tem título **e** ao menos um identificador (DOI ou URL).

**Citação:** `short_citation()` formata como `Autores (ano) — Título — Link`.

## Patent

**Arquivo:** `server/models/patent.py`

Dataclass que representa um documento de patente.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `title` | `str` | Sim | Título da patente |
| `number` | `str` | Sim | Número de publicação (ex.: `US12345678A1`) |
| `url` | `str` | Sim | Link direto para a patente |
| `year` | `int \| None` | Não | Ano de publicação |
| `inventors` | `list[str]` | Não | Lista de inventores |
| `assignee` | `str \| None` | Não | Titular/depositante |
| `abstract` | `str \| None` | Não | Resumo |
| `jurisdiction` | `str` | Sim (default `"US"`) | Código do escritório (US, EP, WO, BR) |
| `source_api` | `str` | Sim (default `"unknown"`) | Provider que retornou o registro |

**Validação:** `is_valid()` retorna `True` se tem título, número **e** URL.
