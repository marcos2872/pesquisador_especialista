# Refatoração da Estrutura do Projeto

## Visão Geral

Esta refatoração separa as responsabilidades do `app.py` (que antes tinha ~540 linhas) em módulos especializados, seguindo o princípio de **responsabilidade única**.

## Nova Estrutura

```
pesquisador_especialista/
├── app.py                    # Servidor HTTP apenas (20 linhas)
├── main.py                   # Ponto de entrada
├── config.py                 # Configurações (.env)
├── services/
│   ├── __init__.py
│   ├── ai_service.py         # Integração OpenAI/Azure
│   ├── source_service.py     # Validação de URLs/fontes
│   ├── report_service.py     # Sanitização de links
│   ├── research_service.py   # Orquestração da pesquisa
│   └── source_collector.py   # Coleta de fontes reais
├── handlers/
│   ├── __init__.py
│   └── research_handler.py   # Handler HTTP
├── models/
│   ├── __init__.py
│   ├── article.py            # Dataclass Article
│   └── patent.py             # Dataclass Patent
├── utils/
│   ├── http_client.py        # Cliente HTTP com retry inteligente
│   ├── fetcher.py            # Download e extração de textos
│   └── search/               # Providers de busca (academic, patents, ieee, serpapi, wipo)
├── agent/
│   ├── systemprompt.md
│   └── userprompt.md
└── static/
    └── index.html
```

## Separação de Responsabilidades

### `config.py`
- Carrega variáveis de ambiente
- Define paths de arquivos
- Fornece configurações padronizadas para todos os módulos

### `services/ai_service.py`
- `call_openai()`: Chamada à API OpenAI/Azure
- `extract_openai_text()`: Parse de diferentes formatos de resposta

### `services/source_service.py`
- `_is_search_or_home_url()`: Identifica URLs de busca/homepage
- `_looks_like_primary_source()`: Identifica fontes primárias
- `validate_report_sources()`: Valida links no relatório
- `count_unique_sources()`: Conta fontes únicas

### `services/report_service.py`
- `sanitize_report_links()`: Remove links inválidos, adiciona seção de referências

### `services/research_service.py`
- `generate_report()`: Orquestra coleta de fontes → IA → validação → sanitização

### `handlers/research_handler.py`
- `ResearchHandler`: Classe que herda de `BaseHTTPRequestHandler`
- Gerencia rotas `GET /`, `GET /index.html`, `POST /api/research`

### `app.py`
- Apenas inicializa o servidor HTTP com o handler

## Benefícios

1. **Testabilidade**: Cada serviço pode ser testado isoladamente
2. **Manutenção**: Mudanças localizadas em um único arquivo
3. **Escalabilidade**: Fácil adicionar novos serviços (ex: novas APIs de busca)
4. **Clareza**: Cada arquivo tem uma única responsabilidade bem definida
5. **Reusabilidade**: Serviços podem ser usados em outros contextos (CLI, testes, etc.)

## Migração

A lógica foi movida intacta para os novos arquivos. As funções mantêm os mesmos nomes e assinaturas quando possível, facilitando transição.

## Próximos Passos Sugeridos

1. ~~Mover modelos de dados para `models/` (Pydantic ou dataclasses)~~ ✅ Concluído
2. ~~Centralizar HTTP client com retry, rate limiting e paralelização~~ ✅ Concluído
3. Criar testes unitários por serviço
4. Adicionar logging centralizado
5. Considerar injeção de dependência para facilitar mocks
6. Documentar APIs de cada serviço com docstrings completas
