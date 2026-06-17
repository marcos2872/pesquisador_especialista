# Plataforma de Pesquisa com IA — SENAI-SP Distrito Tecnológico

Aplicação web para gerar revisões técnicas em **Markdown** a partir de um tópico de pesquisa, incluindo seção de referências com links verificáveis e visualização renderizada na interface.

## Arquitetura

```
pesquisador_especialista/
├── server/          # Backend Python (API HTTP)
│   ├── app.py       # Entry point do servidor
│   ├── config.py    # Configurações e templates de prompt
│   ├── handlers/    # HTTP handlers (rotas API)
│   ├── services/    # Lógica de negócio (IA, fontes, banco)
│   ├── models/      # Dataclasses (Article, Patent)
│   ├── utils/       # Fetcher, HTTP client, módulos de busca
│   └── prompts/     # systemprompt.md, userprompt.md
├── ui/              # Frontend React + Vite
│   ├── src/         # Componentes React + CSS
│   ├── public/      # Assets estáticos (SVG, PNG)
│   ├── dist/        # Build de produção (gerado)
│   └── vite.config.ts
└── tests/           # 104 testes pytest
```

## Como executar

### 1. Backend (API)

```bash
cp .env.example .env
uv run --env-file .env python app.py
# Ou diretamente:
python app.py
```

O servidor inicia em `http://127.0.0.1:8000`.

### 2. Frontend (desenvolvimento)

```bash
cd ui
npm install
npm run dev
```

O dev server inicia em `http://localhost:5173` com proxy `/api/*` para `127.0.0.1:8000`.

### 3. Build de produção (UI)

```bash
cd ui
npm run build    # output em ui/dist/
```

O backend em produção serve os arquivos de `ui/dist/`.

## Configuração de IA

### Opção 1: OpenAI (API padrão)

```bash
export OPENAI_API_KEY="sua-chave"
export OPENAI_MODEL="gpt-5.4-mini"   # opcional
uv run --env-file .env python app.py
```

### Opção 2: Azure OpenAI (`.../openai/v1`)

```bash
export OPENAI_BASE_URL="https://SEU-RECURSO.openai.azure.com/openai/v1"
export OPENAI_API_KEY="sua-chave-azure"
export OPENAI_MODEL="nome-do-deployment"
export OPENAI_DEBUG="1"  # opcional
export OPENAI_TIMEOUT_SECONDS="240"
```

Sem `OPENAI_API_KEY`, a API retorna erro 502.

## Configuração de busca de fontes

Sem nenhuma chave, o sistema já funciona com **Crossref**, **OpenAlex**, **arXiv** e **Core.ac.uk**.

| API | Uso | Cadastro |
|-----|-----|----------|
| Crossref | Artigos | Gratuito |
| OpenAlex | Artigos | Gratuito |
| arXiv | Pré-prints CS/ML | Gratuito |
| Core.ac.uk | Artigos open access | Gratuito |
| Semantic Scholar | Metadados ricos | Opcional |
| Unpaywall | Link de PDF gratuito | Opcional |
| IEEE Xplore | Artigos de engenharia | Opcional |
| USPTO / EPO / Lens / WIPO | Patentes | Opcional |
| SerpAPI | Google Scholar + Patents | Opcional |

## Executar testes

```bash
uv run pytest
```
