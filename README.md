# Plataforma de Pesquisa com IA

Aplicação web simples para gerar revisões técnicas em **Markdown** a partir de um tópico de pesquisa, incluindo seção final com links das referências usadas e visualização Markdown na interface.

## Como executar com uv (recomendado)

```bash
cd /home/marcos/Projects/pesquisador_especialista
cp .env.example .env
uv run --env-file .env app.py
```

Abra no navegador: `http://127.0.0.1:8000`

## Alternativa sem uv

```bash
cd /home/marcos/Projects/pesquisador_especialista
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

Sem configuração de IA, a plataforma roda em **modo demonstração** com estrutura de resposta pronta.
