# API — Referência de Endpoints

## Base URL

```
http://{HOST}:{PORT}
```

Padrão: `http://127.0.0.1:8000`

## Endpoints

### Servir frontend

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/` | Página principal (React SPA) |
| `GET` | `/index.html` | Página principal |
| `GET` | `/assets/*` | Assets estáticos (JS, CSS, imagens, fontes) |

### Histórico de pesquisas

| Método | Caminho | Corpo | Resposta | Erros |
|---|---|---|---|---|
| `GET` | `/api/history` | — | `200` `{ researches: [{ id, topic, created_at }] }` | `500` |
| `GET` | `/api/history/{id}` | — | `200` `{ id, topic, report, created_at }` | `400`, `404` |
| `DELETE` | `/api/history/{id}` | — | `200` `{ deleted: true }` | `400`, `404` |

### Geração de relatório

| Método | Caminho | Corpo | Resposta | Erros |
|---|---|---|---|---|
| `POST` | `/api/research` | `{ topic: string }` | `200` `{ topic, report }` | `400`, `502` |

#### Exemplo de requisição

```bash
curl -X POST http://127.0.0.1:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "nanocompósitos polímero/grafeno para aplicação automotiva"}'
```

#### Exemplo de resposta (200)

```json
{
  "topic": "nanocompósitos polímero/grafeno para aplicação automotiva",
  "report": "## 1. Estado da arte técnico-científico\n\n..."
}
```

#### Códigos de erro

| Status | Significado |
|---|---|
| `400` | JSON inválido ou tópico vazio |
| `502` | Falha na OpenAI (sem chave, timeout, modelo não encontrado) ou erro no pipeline de geração |

## Detalhes dos handlers

- **Arquivo:** `server/handlers/research_handler.py`
- **Classe:** `ResearchHandler` (herda de `BaseHTTPRequestHandler`)
- **Framework:** Nenhum — roteamento manual em `do_GET`, `do_POST`, `do_DELETE`
