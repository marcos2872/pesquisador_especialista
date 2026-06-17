"""
Módulos de busca externa de fontes reais (artigos e patentes).

Cada sub-módulo implementa um provedor de busca específico:
  - academic: APIs acadêmicas (Crossref, OpenAlex, arXiv, Core, Semantic Scholar)
  - ieee: IEEE Xplore (requer API key)
  - patents: APIs de patentes (EPO, USPTO, Lens, WIPO, PatentsView)
  - serpapi: Google Scholar via SerpAPI (requer API key)
  - serpapi_patents: Google Patents via SerpAPI
  - serpapi_scholar: Citações e autor via SerpAPI
  - wipo: WIPO Patentscope (requer API key)
  - prompt_enrichment: Formata fontes em contexto para o prompt da IA

Os provedores consultam APIs gratuitas sempre que possível.
Chaves de API são opcionais — quando ausentes, o provedor retorna
lista vazia sem erro.
"""
