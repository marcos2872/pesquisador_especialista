#!/usr/bin/env python3
import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from utils.fetcher import validate_url_relevance
from utils.search.academic import search_articles
from utils.search.patents import search_patents
from utils.search.prompt_enrichment import build_sources_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("pesquisador")


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROMPT_TEMPLATE_PATH = BASE_DIR / "agent" / "systemprompt.md"
USER_PROMPT_PATH = BASE_DIR / "agent" / "userprompt.md"


def load_prompt_template() -> str:
    if PROMPT_TEMPLATE_PATH.exists():
        return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8").strip()
    return (
        "Você é um pesquisador especialista em revisão técnica, pesquisa de anterioridade, "
        "patentes e análise de lacunas de P&D."
    )


PROMPT_TEMPLATE = load_prompt_template()
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
SEARCH_QUERY_KEYS = {"q", "query", "search", "keyword", "keywords", "term"}
MIN_UNIQUE_SOURCES = 3


def load_user_prompt_template() -> str:
    if USER_PROMPT_PATH.exists():
        return USER_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "Tema da pesquisa: {topic}"


USER_PROMPT_TEMPLATE = load_user_prompt_template()


def build_user_prompt(topic: str, sources_context: str = "") -> str:
    base = USER_PROMPT_TEMPLATE.replace("{topic}", topic)
    if sources_context:
        return f"{base}\n\n--- CONTEXTO DE FONTES VERIFICADAS ---\n{sources_context}\n---\nUse SOMENTE as fontes do contexto acima para embasar o relatório. Não adicione fontes externas.\n"
    return base


def extract_openai_text(data: dict) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = data.get("output")
    if isinstance(output, list):
        chunks = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text" and isinstance(
                    part.get("text"), str
                ):
                    text = part["text"].strip()
                    if text:
                        chunks.append(text)
        if chunks:
            return "\n\n".join(chunks)

    # Fallback para payloads estilo chat completions.
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            chunks = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text = part["text"].strip()
                    if text:
                        chunks.append(text)
            if chunks:
                return "\n\n".join(chunks)

    return ""


def _is_search_or_home_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path or "/"
    normalized_path = path.rstrip("/")
    lower_path = normalized_path.lower()
    lower_host = parsed.netloc.lower()
    query_keys = {key.lower() for key in parse_qs(parsed.query).keys()}

    if normalized_path in ("",):
        return True
    if any(
        token in lower_path for token in ("/search", "/scholar", "/results", "/query")
    ):
        return True
    if lower_host == "scholar.google.com":
        return True
    if query_keys & SEARCH_QUERY_KEYS and not any(
        token in lower_path
        for token in ("/article", "/doi", "/patent", "/document", "/pdf")
    ):
        return True
    return False


def _looks_like_primary_source(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "doi.org/" in url.lower():
        return True
    if any(
        token in path
        for token in (
            "/article",
            "/doi",
            "/abs",
            "/full",
            "/pdf",
            "/patent",
            "/document",
        )
    ):
        return True
    if host in {
        "patents.google.com",
        "worldwide.espacenet.com",
        "patentscope.wipo.int",
    } and path.strip("/"):
        return True
    return False


def validate_report_sources(report: str) -> None:
    urls = MARKDOWN_LINK_PATTERN.findall(report)
    if not urls:
        raise RuntimeError(
            "A resposta não trouxe links de fontes. Exija links diretos de artigos/patentes citados."
        )

    if not any(_looks_like_primary_source(url) for url in urls):
        raise RuntimeError(
            "A resposta não trouxe links diretos de artigo/documento/patente. "
            "Inclua DOI ou URL do documento final."
        )


def _count_unique_sources(report: str) -> int:
    urls = MARKDOWN_LINK_PATTERN.findall(report)
    return len({url.lower() for url in urls})


def sanitize_report_links(report: str, topic: str) -> tuple[str, list[str]]:
    """
    Verifica URLs do relatório contra o tema e remove/substui links quebrados
    ou irrelevantes por '[fonte não verificada]'.

    Retorna o relatório sanitizado e a lista de URLs removidos com motivo.
    """
    # Remove marcações de "sem validação externa" que o modelo possa ter usado.
    report = re.sub(r"\[sem validação externa\]", "", report, flags=re.IGNORECASE)

    urls = list(dict.fromkeys(MARKDOWN_LINK_PATTERN.findall(report)))
    if not urls:
        return report, []

    valid_urls: set[str] = set()
    removed: list[str] = []

    for url in urls:
        if _is_search_or_home_url(url):
            removed.append(f"{url} (link de busca/homepage)")
            continue

        is_valid, reason = validate_url_relevance(url, topic, timeout=15)
        if is_valid:
            valid_urls.add(url)
        else:
            removed.append(f"{url} ({reason})")

    if not removed:
        return report, []

    # Substitui ocorrências de links inválidos no corpo do texto.
    # Preserva o texto do link, mas substitui a URL por '[fonte não verificada]'.
    sanitized = report
    for url in urls:
        if url not in valid_urls:
            sanitized = re.sub(
                rf"\[([^\]]+)\]\(\s*{re.escape(url)}\s*\)",
                r"[\1] [fonte não verificada]",
                sanitized,
            )

    # Remove a seção 6 de referências existente no final do texto.
    # "$" ancora no fim da string; DOTALL permite .* cobrir múltiplas linhas.
    reference_header_pattern = re.compile(
        r"\n##\s+6\.\s+Referências.*$", re.IGNORECASE | re.DOTALL
    )
    sanitized = reference_header_pattern.sub("", sanitized)
    sanitized = sanitized.rstrip()

    if valid_urls:
        sanitized += "\n\n## 6. Referências utilizadas (links verificados)\n\n"
        sanitized += "\n".join(f"- {url}" for url in sorted(valid_urls))
    else:
        sanitized += (
            "\n\n## 6. Referências utilizadas\n\n"
            "_Nenhuma das fontes citadas pôde ser verificada automaticamente. "
            "Recomenda-se busca manual em bases confiáveis._"
        )

    return sanitized, removed


def call_openai(topic: str, sources_context: str = "", retry: bool = False) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")

    if retry:
        user_content = build_retry_prompt(topic)
    else:
        user_content = build_user_prompt(topic, sources_context=sources_context)
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": PROMPT_TEMPLATE},
            {"role": "user", "content": user_content},
        ],
    }
    is_azure = ".openai.azure.com" in base_url
    headers = {"Content-Type": "application/json"}
    if is_azure:
        headers["api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    req = Request(
        f"{base_url}/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    request_timeout = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "240"))
    try:
        with urlopen(req, timeout=request_timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as err:
        body = err.read().decode("utf-8", errors="ignore")
        if err.code == 404:
            raise RuntimeError(
                f"Modelo '{model}' não encontrado no endpoint '{base_url}'. "
                "Verifique OPENAI_MODEL e OPENAI_BASE_URL."
            ) from err
        raise RuntimeError(f"Falha OpenAI ({err.code}): {body}") from err
    except URLError as err:
        raise RuntimeError(f"Falha de conexão OpenAI: {err.reason}") from err

    text = extract_openai_text(data)
    if text:
        return text

    if os.getenv("OPENAI_DEBUG") == "1":
        raw = json.dumps(data, ensure_ascii=False)[:2500]
        raise RuntimeError(
            "Resposta da OpenAI sem texto utilizável. "
            f"Chaves: {list(data.keys())}. Raw (truncado): {raw}"
        )
    raise RuntimeError(
        "Resposta da OpenAI sem texto utilizável. "
        "Defina OPENAI_DEBUG=1 para ver o payload retornado."
    )


def build_retry_prompt(topic: str) -> str:
    return (
        f"Tema da pesquisa: {topic}\n\n"
        "A tentativa anterior falhou porque os links fornecidos não puderam ser "
        "verificados como fontes reais e relevantes ao tema.\n\n"
        "Execute a pesquisa novamente, mas desta vez:\n"
        "- Cite APENAS fontes que você conhece com certeza e consegue referenciar com precisão.\n"
        "- NÃO invente DOIs, números de patente, títulos, autores ou URLs.\n"
        "- NÃO use links de homepages de bases de dados (ex.: https://worldwide.espacenet.com sem número de patente).\n"
        "- Use SOMENTE links diretos: https://doi.org/10.xxxx/xxxxx ou https://patents.google.com/patent/NUMERO/en.\n"
        "- Prefira DOIs de artigos consolidados e patentes de jurisdições principais (US/EP/WO) que você saiba que existem.\n"
        "- Se não souber uma fonte específica, reduza o escopo do parágrafo ou omita a afirmação.\n"
        "- Entregue exatamente a mesma estrutura de 6 seções.\n"
        "- Use obrigatoriamente links diretos no formato [Fonte](URL/DOI/patente).\n"
        "- Seção 6 deve listar somente as fontes realmente citadas no texto."
    )


def _collect_real_sources(topic: str) -> tuple[str, dict[str, list[str]]]:
    """
    Coleta fontes reais via APIs gratuitas, baixa textos e extrai snippets.

    Returns:
        (sources_context, snippets_map): contexto formatado e mapa url->snippets.
    """
    if os.getenv("ENABLE_REAL_SEARCH", "1") == "0":
        return "", {}

    from utils.fetcher import download_source_texts, generate_query_variants

    # Expande o tópico em múltiplas queries (EN + PT + variantes)
    queries = generate_query_variants(topic)
    logger.info("Buscando com %d queries: %s", len(queries), queries[:3])

    all_articles: list = []
    all_patents: list = []

    for query in queries[:3]:  # Limita a 3 queries para não sobrecarregar APIs
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_art = executor.submit(
                search_articles, query, max_results=5, timeout=15
            )
            future_pat = executor.submit(
                search_patents, query, max_results=3, timeout=15
            )

            try:
                all_articles.extend(future_art.result())
            except Exception as exc:
                logger.warning("Falha na busca de artigos para '%s': %s", query, exc)

            try:
                all_patents.extend(future_pat.result())
            except Exception as exc:
                logger.warning("Falha na busca de patentes para '%s': %s", query, exc)

    if not all_articles and not all_patents:
        logger.info("Nenhuma fonte real encontrada para o tópico '%s'", topic)
        return "", {}

    # Baixa PDFs e extrai snippets das fontes encontradas
    sources_for_download: list[dict] = []
    for a in all_articles:
        entry = {
            "title": a.title,
            "url": a.url,
            "pdf_url": getattr(a, "pdf_url", None),
            "doi": getattr(a, "doi", None),
        }
        sources_for_download.append(entry)
    for p in all_patents:
        entry = {
            "title": p.title,
            "url": p.url,
            "pdf_url": None,
            "doi": None,
        }
        sources_for_download.append(entry)

    logger.info(
        "Baixando PDFs e extraindo snippets de %d fontes...", len(sources_for_download)
    )
    enriched = download_source_texts(
        sources_for_download, topic, timeout=20, max_workers=3
    )

    # Constrói o mapa de snippets: url -> lista de trechos
    snippets_map: dict[str, list[str]] = {}
    for src in enriched:
        url = src.get("url") or ""
        if url and src.get("snippets"):
            snippets_map[url] = src["snippets"]

    total_snippets = sum(len(v) for v in snippets_map.values())
    logger.info(
        "%d fontes encontradas, %d trechos extraídos para citação literal",
        len(enriched),
        total_snippets,
    )

    context = (
        build_sources_context(all_articles, all_patents, snippets_map=snippets_map)
        or ""
    )
    return context, snippets_map


def generate_report(topic: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "Pesquisa confiável indisponível sem `OPENAI_API_KEY`. "
            "Configure um provedor para gerar resposta baseada em fontes verificáveis."
        )

    from utils.fetcher import validate_quoted_citations

    sources_context, snippets_map = _collect_real_sources(topic)

    def _try_generate(retry: bool = False) -> tuple[str, list[str], list[str]]:
        report = call_openai(topic, sources_context=sources_context, retry=retry)
        validate_report_sources(report)
        sanitized, removed = sanitize_report_links(report, topic)
        # Valida citações literais ("...") contra snippets extraídos
        citation_warnings: list[str] = []
        if snippets_map:
            sanitized, citation_warnings = validate_quoted_citations(
                sanitized, snippets_map
            )
        return sanitized, removed, citation_warnings

    sanitized_report, removed, citation_warnings = _try_generate(retry=False)

    if _count_unique_sources(sanitized_report) < MIN_UNIQUE_SOURCES:
        sanitized_report, removed, citation_warnings = _try_generate(retry=True)

    if _count_unique_sources(sanitized_report) < MIN_UNIQUE_SOURCES:
        raise RuntimeError(
            "A resposta trouxe poucas fontes que puderam ser verificadas como reais e relevantes. "
            f"Use pelo menos {MIN_UNIQUE_SOURCES} fontes distintas e confiáveis, "
            "ou integre uma ferramenta de busca real (ex.: Crossref, SerpAPI) para obter referências verificadas."
        )

    # Monta avisos acumulados
    warnings: list[str] = []
    if removed:
        warnings.append(
            "> **Aviso de validação de fontes:** alguns links gerados pelo modelo "
            "não foram confirmados como válidos ou relevantes ao tema e foram "
            "substituídos por `[fonte não verificada]`. "
            "Recomenda-se revisão manual das referências."
        )
    if citation_warnings:
        warnings.append(
            "> **Aviso de citações literais:** alguns trechos entre aspas não foram "
            "encontrados nos textos das fontes e foram marcados como "
            "`[citação não verificada na fonte]`. "
            "Recomenda-se verificar manualmente."
        )

    if warnings:
        sanitized_report = "\n\n".join(warnings) + "\n\n" + sanitized_report

    return sanitized_report


class Handler(BaseHTTPRequestHandler):
    def _write_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _serve_index(self) -> None:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "index.html não encontrado.")
            return
        content = index_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(content)
        self.close_connection = True

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._serve_index()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")

    def do_POST(self) -> None:
        if self.path != "/api/research":
            self.send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            self._write_json({"error": "JSON inválido."}, status=HTTPStatus.BAD_REQUEST)
            return

        topic = str(data.get("topic", "")).strip()
        if not topic:
            self._write_json(
                {"error": "Informe um tópico de pesquisa."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            report = generate_report(topic)
        except RuntimeError as err:
            self._write_json(
                {"error": str(err)},
                status=HTTPStatus.BAD_GATEWAY,
            )
            return

        self._write_json({"topic": topic, "report": report})


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Servidor ativo em http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
