#!/usr/bin/env python3
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROMPT_TEMPLATE_PATH = BASE_DIR / "agent" / "prompt.md"


def load_prompt_template() -> str:
    if PROMPT_TEMPLATE_PATH.exists():
        return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8").strip()
    return (
        "Você é um pesquisador especialista em revisão técnica, pesquisa de anterioridade, "
        "patentes e análise de lacunas de P&D."
    )


PROMPT_TEMPLATE = load_prompt_template()


def build_user_prompt(topic: str) -> str:
    return (
        f"Tema da pesquisa: {topic}\n\n"
        "Execute a pesquisa técnica e entregue exatamente nesta estrutura:\n"
        "1. Estado da arte técnico-científico\n"
        "2. Pesquisa de anterioridade/patentes\n"
        "3. Tabela comparativa\n"
        "4. Lacunas e oportunidades\n"
        "5. Conclusão técnica\n"
        "6. Referências utilizadas (links)\n\n"
        "FORMATO OBRIGATÓRIO: responda em Markdown (GitHub Flavored Markdown).\n"
        "Use português técnico e inclua obrigatoriamente links diretos/DOI/número de patente.\n"
        "NÃO escreva avisos operacionais como 'Falha operacional', 'sem acesso MCP' ou similares.\n"
        "NÃO diga que usou ferramentas que não usou.\n"
        "Priorize fontes de 2016 até hoje; se usar referência anterior, marque como [Fundacional] "
        "e use no máximo 2.\n"
        "REGRA OBRIGATÓRIA DE CITAÇÃO: em cada parágrafo técnico, adicione ao final "
        "um marcador em LINK MARKDOWN no formato [Fonte](URL/DOI/link-da-patente).\n"
        "Na tabela comparativa, adicione uma coluna 'Fonte (link/DOI/patente)'.\n"
        "Na seção 6, liste somente as fontes realmente citadas no texto."
    )


def generate_demo_report(topic: str) -> str:
    return (
        f"# Pesquisa técnica: {topic}\n\n"
        "1. Estado da arte técnico-científico\n"
        "- Modo demonstração ativo (sem provedor de IA configurado). "
        "[Fonte](https://scholar.google.com/)\n"
        "- Estruture este bloco com panorama histórico, abordagens e limitações. "
        "[Fonte](https://www.sciencedirect.com/)\n\n"
        "2. Pesquisa de anterioridade/patentes\n"
        "- Liste documentos por jurisdição (BR/US/EP/WO), com número, ano e titular. "
        "[Fonte](https://worldwide.espacenet.com/)\n\n"
        "3. Tabela comparativa\n"
        "| Referência/Patente | Ano | Método | Principais resultados | Limitações | Fonte (link/DOI/patente) |\n"
        "|---|---:|---|---|---|---|\n"
        "| Exemplo | 2024 | Revisão | Resultado resumido | Limitação resumida | https://doi.org/xx.xxxx/xxxxx |\n\n"
        "4. Lacunas e oportunidades\n"
        "- Identifique gaps técnicos, riscos de sobreposição e linhas de P&D. "
        "[Fonte](https://patentscope.wipo.int/)\n\n"
        "5. Conclusão técnica\n"
        "- Defina maturidade tecnológica e próximos passos prioritários. "
        "[Fonte](https://link.springer.com/)\n\n"
        "6. Referências utilizadas (links)\n"
        "- https://scholar.google.com/\n"
        "- https://worldwide.espacenet.com/\n"
        "- https://patentscope.wipo.int/\n\n"
        "**Para ativar IA real:** configure `OPENAI_API_KEY` (e opcionalmente `OPENAI_MODEL`) "
        "e `OPENAI_BASE_URL` quando usar Azure."
    )


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
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
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


def call_openai(topic: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": PROMPT_TEMPLATE},
            {"role": "user", "content": build_user_prompt(topic)},
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


def generate_report(topic: str) -> str:
    if os.getenv("OPENAI_API_KEY"):
        return call_openai(topic)
    return generate_demo_report(topic)


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
