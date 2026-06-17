"""
Camada de serviços da plataforma.

Contém a lógica de negócio orquestrada por research_service.py:
  - ai_service: comunicação com OpenAI/Azure
  - db: persistência SQLite do histórico
  - report_service: sanitização e validação de links no relatório gerado
  - research_service: orquestrador principal (coleta → IA → sanitização)
  - source_collector: busca de fontes reais em APIs acadêmicas
  - source_service: validação e contagem de fontes
"""
