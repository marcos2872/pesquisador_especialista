# Plataforma de Pesquisa com IA

Aplicação web simples para gerar revisões técnicas em **Markdown** a partir de um tópico de pesquisa, incluindo seção final com links das referências usadas e visualização Markdown na interface.

## Como executar com uv (recomendado)

```bash
cd /home/marcos/Projetos/pesquisador_especialista
cp .env.example .env
uv run --env-file .env app.py
```

Abra no navegador: `http://127.0.0.1:8000`

## Alternativa sem uv

```bash
cd /home/marcos/Projetos/pesquisador_especialista
python3 app.py
```

## Configuração de IA

### Opção 1: OpenAI (API padrão)

```bash
export OPENAI_API_KEY="sua-chave"
export OPENAI_MODEL="gpt-5.4-mini"   # opcional
uv run --env-file .env app.py
```

### Opção 2: Azure OpenAI (`.../openai/v1`)

```bash
export OPENAI_BASE_URL="https://SEU-RECURSO.openai.azure.com/openai/v1"
export OPENAI_API_KEY="sua-chave-azure"
export OPENAI_MODEL="nome-do-deployment"
export OPENAI_DEBUG="1"  # opcional: mostra payload bruto em caso de erro
export OPENAI_TIMEOUT_SECONDS="240" # opcional: timeout da chamada ao modelo
uv run --env-file .env app.py
```

Sem configuração de IA, a API retorna erro informando ausência de fonte confiável.  
Para gerar pesquisa baseada em artigos/patentes com dados verificáveis, configure `OPENAI_API_KEY`.

## Configuração de busca de fontes

A plataforma busca artigos e patentes em várias APIs gratuitas para reduzir a alucinação de links. Sem nenhuma chave configurada, o sistema já funciona com **Crossref**, **OpenAlex**, **arXiv** e **Core.ac.uk** (todas gratuitas e sem cadastro). As chaves abaixo são opcionais e ampliam a cobertura.

### APIs sem cadastro (já funcionam)

| API | Uso | Documentação |
|---|---|---|
| Crossref | Artigos | https://api.crossref.org |
| OpenAlex | Artigos | https://docs.openalex.org |
| arXiv | Pré-prints de CS/ML | https://info.arxiv.org/help/api/basics.html |
| Core.ac.uk | Artigos open access | https://api.core.ac.uk |

### APIs que precisam de chave (opcional)

| API | Uso | Onde criar a chave |
|---|---|---|
| **Semantic Scholar** | Artigos com metadados ricos (recomendado; sem chave há rate limit) | https://www.semanticscholar.org/product/api |
| **Unpaywall** | Enriquecer com link de PDF gratuito (só precisa de um email) | https://unpaywall.org/products/api |
| **IEEE Xplore** | Artigos de CS, IA, eletrônica, controle | https://developer.ieee.org/ |
| **USPTO Open Data** | Patentes americanas | https://data.uspto.gov/apis/patent-data-api |
| **Espacenet OPS (EPO)** | Patentes europeias e mundiais | https://developers.epo.org/ |
| **Lens.org** | Artigos + patentes cruzados (uso acadêmico) | https://www.lens.org/lens/api |
| **WIPO Patentscope** | Patentes internacionais (PCT) | https://patentscope.wipo.int/ |
| **SerpAPI** | Google Scholar + Google Patents | https://serpapi.com |

### Por que não há scripts para Scopus / Web of Science / ScienceDirect / SpringerLink / Wiley

- **Scopus, Web of Science, ScienceDirect, SpringerLink, Wiley** — exigem credenciais institucionais (login de universidade) e/ou têm APIs **comerciais pagas** (Elsevier, Wiley, Springer Nature) sem tier gratuito viável. Não há busca automatizada possível sem essas credenciais.

A alternativa prática é usar as APIs já integradas (Crossref, OpenAlex, Unpaywall), que cobrem o mesmo conteúdo de forma gratuita e legal.

### Exemplo de `.env` completo

```bash
HOST=127.0.0.1
PORT=8000

# OpenAI/Azure OpenAI
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
OPENAI_DEBUG=0
OPENAI_TIMEOUT_SECONDS=240

# Busca de fontes (opcional, mas recomendado)
OPENALEX_USER_AGENT=mailto:seu-email@dominio.com
UNPAYWALL_EMAIL=seu-email@dominio.com
SEMANTIC_SCHOLAR_API_KEY=
IEEE_API_KEY=
USPTO_API_KEY=
EPO_OPS_CONSUMER_KEY=
EPO_OPS_CONSUMER_SECRET=
LENS_API_TOKEN=
WIPO_API_KEY=
SERPAPI_API_KEY=

# Timeout e comportamento da busca
SEARCH_TIMEOUT_SECONDS=30
ENABLE_REAL_SEARCH=1
```
