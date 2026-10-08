#!/usr/bin/env python3
"""Check HTTP responses, not page contents. Requires Python 3.10+, stdlib only."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import math
import re
import socket
import ssl
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_URLS = 200
REDIRECTS = {301, 302, 303, 307, 308}
FALLBACK_GET = {403, 405, 501}
RESTRICTED = {401, 403, 407, 429}
URL_PATTERN = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)


class PolicyError(Exception):
    """A request was blocked before its destination was contacted."""


@dataclass(frozen=True)
class ParsedURL:
    url: str
    scheme: str
    host: str
    port: int
    target: str


@dataclass
class Result:
    url: str
    final_url: str
    state: str
    http_status: int | None
    method: str
    redirects: int
    checked_at: str
    elapsed_ms: int
    detail: str


def display_url(value: str) -> str:
    """Remove userinfo, fragments and query values from reports."""
    try:
        p = urlsplit(value)
        if not p.hostname or any(ord(c) < 32 for c in value):
            return "<URL inválida omitida>"
        host = p.hostname
        if ":" in host:
            host = f"[{host}]"
        if p.port is not None:
            host += f":{p.port}"
        hidden = urlencode([(key, "[redacted]") for key, _ in parse_qsl(
            p.query, keep_blank_values=True, max_num_fields=1000
        )])
        return urlunsplit((p.scheme, host, p.path, hidden, ""))
    except (ValueError, UnicodeError):
        return "<URL inválida omitida>"


def parse_url(value: str) -> ParsedURL:
    if not value or len(value) > 8192 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("URL vazia, extensa demais ou com espaço/caractere de controle.")
    p = urlsplit(value)
    if p.scheme not in {"http", "https"} or not p.hostname:
        raise ValueError("Informar uma URL HTTP(S) absoluta.")
    if "@" in p.netloc:
        raise PolicyError("Credenciais embutidas na URL; requisição bloqueada.")
    if any(c in p.netloc for c in "\\{}%") or any(c in p.path for c in "{}"):
        raise ValueError("Autoridade inválida ou placeholder na URL.")
    host = p.hostname.encode("idna").decode("ascii").lower()
    port = p.port if p.port is not None else (443 if p.scheme == "https" else 80)
    if not 1 <= port <= 65535:
        raise ValueError("Porta inválida.")
    for key, _ in parse_qsl(p.query, keep_blank_values=True, max_num_fields=1000):
        compact = re.sub(r"[^a-z0-9]", "", key.lower())
        if compact in {"key", "apikey", "code", "auth", "authorization", "sig"} or any(
            marker in compact for marker in
            ("token", "secret", "password", "signature", "credential", "xamz", "xgoog")
        ):
            raise PolicyError("Parâmetro possivelmente sensível; requisição bloqueada.")
    authority = f"[{host}]" if ":" in host else host
    if p.port is not None:
        authority += f":{port}"
    path = quote(p.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = quote(p.query, safe="=&%+/:?@!$'()*;,~-._")
    url = urlunsplit((p.scheme, authority, path, query, ""))
    return ParsedURL(url, p.scheme, host, port, path + ("?" + query if query else ""))


def extract_urls(text: str) -> list[str]:
    """Extract plain/Markdown URLs heuristically, preserving balanced parentheses."""
    urls = []
    for match in URL_PATTERN.finditer(text):
        value = match.group(0).rstrip(".,;:!")
        for closing, opening in ((")", "("), ("]", "[")):
            while value.endswith(closing) and value.count(closing) > value.count(opening):
                value = value[:-1].rstrip(".,;:!")
        urls.append(value)
    return urls


def unique_urls(urls: list[str]) -> list[str]:
    found = set()
    result = []
    for value in urls:
        value = value.strip()
        try:
            key = parse_url(value).url
        except (ValueError, UnicodeError, PolicyError):
            key = value
        if key not in found:
            found.add(key)
            result.append(value)
    return result


def resolve_addresses(host: str, port: int, allow_private: bool) -> list[tuple]:
    """Validate every resolved address and pin connection to the checked address."""
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise socket.gaierror("No addresses")
    result = []
    seen = set()
    for family, socktype, protocol, _, sockaddr in addresses:
        ip = ipaddress.ip_address(sockaddr[0].split("%", 1)[0])
        if not allow_private and (not ip.is_global or ip.is_multicast):
            raise PolicyError("Destino não público; requisição bloqueada.")
        key = (family, sockaddr)
        if key not in seen:
            seen.add(key)
            result.append((family, socktype, protocol, sockaddr))
    # Try IPv4 first where both families are available; never re-resolve to connect.
    return sorted(result, key=lambda item: item[0] != socket.AF_INET)[:4]


def request_once(parsed: ParsedURL, method: str, timeout: float,
                 allow_private: bool) -> tuple[int, str | None]:
    addresses = resolve_addresses(parsed.host, parsed.port, allow_private)
    last_error: OSError | None = None
    sock = None
    for family, socktype, protocol, sockaddr in addresses:
        candidate = socket.socket(family, socktype, protocol)
        candidate.settimeout(timeout)
        try:
            candidate.connect(sockaddr)
        except OSError as exc:
            last_error = exc
            candidate.close()
            continue
        sock = candidate
        break
    if sock is None:
        raise last_error or OSError("Connection unavailable")
    conn = http.client.HTTPConnection(parsed.host, parsed.port, timeout=timeout)
    try:
        if parsed.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.host)
        # Supplying the connected socket preserves Host/SNI without a second DNS lookup.
        conn.sock = sock
        headers = {"User-Agent": "claim-verifier/1.0", "Accept-Encoding": "identity",
                   "Connection": "close"}
        if method == "GET":
            headers["Range"] = "bytes=0-1023"
        conn.request(method, parsed.target, headers=headers)
        response = conn.getresponse()
        try:
            return response.status, response.getheader("Location")
        finally:
            # No body is read: a successful response does not verify its contents.
            response.close()
    finally:
        conn.close()
        sock.close()


def classify_status(status: int) -> tuple[str, str]:
    if 200 <= status < 300:
        return "reachable", "HTTP 2xx observado; conteúdo não verificado."
    if status in {404, 410}:
        return "missing", "HTTP 404/410 observado nesta requisição."
    if status in RESTRICTED:
        return "restricted", "Acesso restrito ou limitado nesta requisição."
    return "unknown", "Resposta HTTP inconclusiva para esta verificação."


def check_url(value: str, *, timeout: float = 10, max_redirects: int = 5,
              allow_private: bool = False) -> Result:
    started = time.monotonic()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    current = value
    method = "HEAD"
    jumps = 0
    status = None
    seen = set()

    def finish(state: str, detail: str) -> Result:
        return Result(display_url(value), display_url(current), state, status, method,
                      jumps, checked_at, round((time.monotonic() - started) * 1000), detail)

    try:
        while True:
            parsed = parse_url(current)
            current = parsed.url
            if current in seen:
                return finish("unknown", "Ciclo de redirecionamento.")
            seen.add(current)
            status, location = request_once(parsed, method, timeout, allow_private)
            if method == "HEAD" and status in FALLBACK_GET:
                method = "GET"
                status, location = request_once(parsed, method, timeout, allow_private)
            if status not in REDIRECTS:
                state, detail = classify_status(status)
                return finish(state, detail)
            if not location:
                return finish("unknown", "Redirecionamento sem Location.")
            if jumps >= max_redirects:
                return finish("unknown", "Limite de redirecionamentos atingido.")
            destination = parse_url(urljoin(current, location))
            if parsed.scheme == "https" and destination.scheme != "https":
                return finish("blocked", "Redirecionamento de HTTPS para HTTP bloqueado.")
            current = destination.url
            jumps += 1
    except PolicyError as exc:
        return finish("blocked", str(exc))
    except (ValueError, UnicodeError) as exc:
        # Messages come from validation, never from an untrusted response body.
        return finish("invalid", "URL inválida: " + type(exc).__name__ + ".")
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        return finish("unknown", "Falha de rede ou TLS: " + type(exc).__name__ + ".")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(
        "Conferir respostas HTTP de URLs de leitura; não verificar o conteúdo."
    ))
    parser.add_argument("urls", nargs="*", help="URLs HTTP(S) explícitas")
    parser.add_argument("--file", action="append", default=[], type=Path,
                        help="Extrair URLs de texto UTF-8 (até 5 MiB; repetível)")
    parser.add_argument("--stdin", action="store_true", help="Extrair URLs da entrada padrão")
    parser.add_argument("--json", action="store_true", help="Emitir relatório JSON")
    parser.add_argument("--timeout", type=float, default=10,
                        help="Timeout por operação de socket, em segundos (padrão: 10)")
    parser.add_argument("--max-redirects", type=int, default=5,
                        help="Máximo de redirecionamentos por URL (0 a 20; padrão: 5)")
    parser.add_argument("--allow-private", action="store_true",
                        help="Permitir destinos não públicos para diagnóstico autorizado")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout deve ser positivo e finito")
    if not 0 <= args.max_redirects <= 20:
        parser.error("--max-redirects deve estar entre 0 e 20")
    urls = list(args.urls)
    try:
        for path in args.file:
            with path.open("rb") as source:
                data = source.read(MAX_INPUT_BYTES + 1)
            if len(data) > MAX_INPUT_BYTES:
                parser.error("arquivo de entrada excede 5 MiB")
            urls.extend(extract_urls(data.decode("utf-8-sig")))
        if args.stdin:
            data = sys.stdin.read(MAX_INPUT_BYTES + 1)
            if len(data.encode("utf-8")) > MAX_INPUT_BYTES:
                parser.error("entrada padrão excede 5 MiB")
            urls.extend(extract_urls(data))
    except (OSError, UnicodeError):
        parser.error("não foi possível ler uma entrada como texto UTF-8")
    urls = unique_urls(urls)
    if not urls:
        parser.error("nenhuma URL HTTP(S) encontrada ou informada")
    if len(urls) > MAX_URLS:
        parser.error("limite de 200 URLs por execução")
    results = [check_url(url, timeout=args.timeout, max_redirects=args.max_redirects,
                         allow_private=args.allow_private) for url in urls]
    if args.json:
        print(json.dumps({"schema_version": 1, "scope": "http_response_only",
                          "results": [asdict(result) for result in results]},
                         ensure_ascii=False, indent=2))
    else:
        for result in results:
            code = str(result.http_status) if result.http_status is not None else "-"
            print(f"{result.state}\t{code}\t{result.method}\t{result.url}")
            print(f"  {result.detail}")
            if result.final_url != result.url:
                print(f"  Destino final: {result.final_url}")
    return 0 if all(result.state == "reachable" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
