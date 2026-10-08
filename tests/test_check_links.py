"""Contract tests using a disposable loopback HTTP server and isolated failures."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_links.py"
spec = importlib.util.spec_from_file_location("claim_verifier_check_links", SCRIPT)
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_HEAD(self):
        self.respond()

    def do_GET(self):
        self.respond()

    def respond(self):
        self.server.received.append((self.command, self.path, dict(self.headers)))
        path = urlsplit(self.path).path
        location = None
        if path == "/slow":
            self.server.release.wait(timeout=1)
        if path in {"/ok", "/slow", "/soft-404", "/login"}:
            status = 200
        elif path == "/only-get":
            status = 405 if self.command == "HEAD" else 200
        elif path == "/head-blocked":
            status = 403 if self.command == "HEAD" else 200
        elif path == "/head-not-implemented":
            status = 501 if self.command == "HEAD" else 204
        elif path == "/redirect":
            status, location = 302, "/ok#part"
        elif path == "/sensitive-redirect":
            status, location = 302, "/ok?access_token=fixture-secret"
        elif path == "/loop":
            status, location = 301, "/loop"
        elif path == "/no-location":
            status = 302
        else:
            status = {"/gone": 410, "/restricted": 403, "/unauthorized": 401,
                      "/limited": 429, "/proxy-auth": 407, "/server-error": 503}.get(path, 404)
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()


class LinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.received = []
        cls.server.release = threading.Event()
        cls.server.release.set()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.release.set()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.server.received.clear()

    def check(self, path, **options):
        return checker.check_url(self.base + path, allow_private=True, **options)

    def run_main(self, args, stdin=""):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                patch.object(sys, "stdin", io.StringIO(stdin)):
            try:
                code = checker.main(args)
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_head_success(self):
        result = self.check("/ok")
        self.assertEqual((result.state, result.http_status, result.method), ("reachable", 200, "HEAD"))
        self.assertEqual(len(self.server.received), 1)

    def test_get_fallback(self):
        for path, expected in (("/only-get", 200), ("/head-blocked", 200),
                               ("/head-not-implemented", 204)):
            with self.subTest(path=path):
                self.server.received.clear()
                result = self.check(path)
                self.assertEqual((result.state, result.http_status, result.method),
                                 ("reachable", expected, "GET"))
                self.assertEqual([hit[0] for hit in self.server.received], ["HEAD", "GET"])
                self.assertEqual(self.server.received[-1][2]["Range"], "bytes=0-1023")

    def test_restricted_is_not_missing(self):
        for path, expected in (("/restricted", 403), ("/unauthorized", 401),
                               ("/limited", 429), ("/proxy-auth", 407)):
            with self.subTest(path=path):
                result = self.check(path)
                self.assertEqual((result.state, result.http_status), ("restricted", expected))

    def test_missing_responses(self):
        for path, expected in (("/missing", 404), ("/gone", 410)):
            with self.subTest(path=path):
                result = self.check(path)
                self.assertEqual((result.state, result.http_status), ("missing", expected))

    def test_server_error_is_unknown(self):
        result = self.check("/server-error")
        self.assertEqual((result.state, result.http_status), ("unknown", 503))

    def test_success_does_not_verify_semantics(self):
        for path in ("/soft-404", "/login"):
            with self.subTest(path=path):
                result = self.check(path)
                self.assertEqual(result.state, "reachable")
                self.assertIn("conteúdo não verificado", result.detail)

    def test_redirect_and_fragment(self):
        result = self.check("/redirect")
        self.assertEqual((result.state, result.redirects, result.final_url),
                         ("reachable", 1, self.base + "/ok"))
        self.assertEqual([hit[1] for hit in self.server.received], ["/redirect", "/ok"])

    def test_redirect_cycle(self):
        result = self.check("/loop")
        self.assertEqual(result.state, "unknown")
        self.assertIn("Ciclo", result.detail)
        self.assertEqual(len(self.server.received), 1)

    def test_redirect_limit_zero(self):
        result = self.check("/redirect", max_redirects=0)
        self.assertEqual(result.state, "unknown")
        self.assertEqual(len(self.server.received), 1)

    def test_redirect_without_location(self):
        result = self.check("/no-location")
        self.assertEqual(result.state, "unknown")
        self.assertIn("sem Location", result.detail)

    def test_private_destination_blocked_without_contact(self):
        result = checker.check_url(self.base + "/ok")
        self.assertEqual(result.state, "blocked")
        self.assertEqual(self.server.received, [])

    def test_ipv6_loopback_blocked(self):
        result = checker.check_url("http://[::1]/")
        self.assertEqual(result.state, "blocked")

    def test_redirect_to_private_address_blocked(self):
        original = checker.request_once

        def transport(parsed, method, timeout, allow_private):
            if parsed.host == "public.example":
                return 302, self.base + "/ok"
            return original(parsed, method, timeout, allow_private)

        with patch.object(checker, "request_once", side_effect=transport):
            result = checker.check_url("http://public.example/")
        self.assertEqual(result.state, "blocked")
        self.assertEqual(self.server.received, [])

    def test_mixed_public_private_dns_blocked(self):
        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80)),
                     (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        with patch.object(checker.socket, "getaddrinfo", return_value=addresses), \
                patch.object(checker.socket, "socket") as connect:
            result = checker.check_url("http://mixed.example/")
        self.assertEqual(result.state, "blocked")
        connect.assert_not_called()

    def test_dns_pinned_once_and_host_preserved(self):
        addresses = socket.getaddrinfo("127.0.0.1", self.server.server_port,
                                       type=socket.SOCK_STREAM)
        with patch.object(checker.socket, "getaddrinfo", return_value=addresses) as resolver:
            result = checker.check_url(f"http://fixture.example:{self.server.server_port}/ok",
                                       allow_private=True)
        self.assertEqual(result.state, "reachable")
        self.assertEqual(resolver.call_count, 1)
        self.assertEqual(self.server.received[0][2]["Host"],
                         f"fixture.example:{self.server.server_port}")

    def test_dns_failure_is_unknown(self):
        with patch.object(checker.socket, "getaddrinfo", side_effect=socket.gaierror("fixture")):
            result = checker.check_url("https://fixture.example/")
        self.assertEqual(result.state, "unknown")

    def test_embedded_credentials_blocked_and_redacted(self):
        url = self.base.replace("//", "//user:fixture-password@") + "/ok"
        result = checker.check_url(url, allow_private=True)
        self.assertEqual(result.state, "blocked")
        self.assertNotIn("fixture-password", str(result))
        self.assertEqual(self.server.received, [])

    def test_sensitive_parameters_blocked_and_redacted(self):
        for key in ("token", "api_key", "X-Amz-Signature", "code", "password"):
            with self.subTest(key=key):
                result = self.check("/ok?" + key + "=fixture-secret")
                self.assertEqual(result.state, "blocked")
                self.assertNotIn("fixture-secret", str(result))
        self.assertEqual(self.server.received, [])

    def test_sensitive_redirect_not_followed(self):
        result = self.check("/sensitive-redirect")
        self.assertEqual(result.state, "blocked")
        self.assertEqual(len(self.server.received), 1)
        self.assertNotIn("fixture-secret", str(result))

    def test_invalid_urls_do_not_contact_server(self):
        for url in ("ftp://example.com/x", "example.com", "http://[invalid",
                    self.base + "/{placeholder}", self.base + "/space here",
                    self.base + "/ok\r\nInjected: bad", "http://example.com:99999/"):
            with self.subTest(url=url):
                result = checker.check_url(url, allow_private=True)
                self.assertEqual(result.state, "invalid")
        self.assertEqual(self.server.received, [])

    def test_query_values_redacted_in_json(self):
        code, output, _ = self.run_main([self.base + "/ok?q=fixture-private-query",
                                         "--allow-private", "--json"])
        self.assertEqual(code, 0)
        self.assertNotIn("fixture-private-query", output)
        self.assertEqual(json.loads(output)["scope"], "http_response_only")

    def test_actual_socket_timeout_is_unknown(self):
        self.server.release.clear()
        try:
            result = self.check("/slow", timeout=0.05)
        finally:
            self.server.release.set()
        self.assertEqual(result.state, "unknown")
        self.assertIn("Timeout", result.detail)

    def test_tls_failure_no_http_retry(self):
        with patch.object(checker.ssl, "create_default_context") as context:
            context.return_value.wrap_socket.side_effect = ssl.SSLError("fixture TLS error")
            result = checker.check_url(self.base.replace("http:", "https:") + "/ok",
                                       allow_private=True)
        self.assertEqual(result.state, "unknown")
        self.assertIn("SSLError", result.detail)
        context.assert_called_once_with()
        self.assertEqual(self.server.received, [])

    def test_https_downgrade_blocked(self):
        with patch.object(checker, "request_once", return_value=(302, "http://public.example/")) as transport:
            result = checker.check_url("https://public.example/")
        self.assertEqual(result.state, "blocked")
        self.assertEqual(transport.call_count, 1)

    def test_no_ambient_credentials_or_proxy(self):
        with patch.dict("os.environ", {"HTTP_PROXY": "http://unreachable.invalid:1",
                                       "HTTPS_PROXY": "http://unreachable.invalid:1"}):
            result = self.check("/ok")
        self.assertEqual(result.state, "reachable")
        headers = self.server.received[0][2]
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("Cookie", headers)

    def test_file_extraction_deduplication_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reply.md"
            path.write_text(f"[Guia]({self.base}/ok#first).\n<{self.base}/ok#second>\n", encoding="utf-8")
            code, output, _ = self.run_main(["--file", str(path), "--allow-private", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(output)["results"]), 1)
        self.assertEqual(self.server.received[0][1], "/ok")

    def test_cli_missing_returns_one(self):
        code, output, _ = self.run_main([self.base + "/missing", "--allow-private"])
        self.assertEqual(code, 1)
        self.assertIn("missing", output)

    def test_empty_input_returns_two(self):
        code, output, error = self.run_main(["--stdin"], "sem links")
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("nenhuma URL", error)

    def test_unreadable_utf8_input_returns_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "binary.txt"
            path.write_bytes(b"\xff\x00")
            code, _, _ = self.run_main(["--file", str(path)])
        self.assertEqual(code, 2)

    def test_stdin_extraction(self):
        code, output, _ = self.run_main(["--stdin", "--json", "--allow-private"],
                                        f"Confira <{self.base}/ok>.")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["results"][0]["state"], "reachable")

    def test_balanced_parentheses_extraction(self):
        text = "[Guia](https://example.com/Guide_(test)). <https://example.com/next>"
        self.assertEqual(checker.extract_urls(text),
                         ["https://example.com/Guide_(test)", "https://example.com/next"])

    def test_invalid_limits_return_two(self):
        for args in (["--timeout", "0"], ["--timeout", "nan"], ["--timeout", "inf"],
                     ["--max-redirects", "-1"], ["--max-redirects", "21"]):
            with self.subTest(args=args):
                code, _, _ = self.run_main(args)
                self.assertEqual(code, 2)

    def test_excess_urls_rejected_without_network(self):
        urls = [f"https://fixture.example/{i}" for i in range(201)]
        with patch.object(checker, "request_once") as transport:
            code, _, _ = self.run_main(urls)
        self.assertEqual(code, 2)
        transport.assert_not_called()

    def test_help_as_executable(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--json", result.stdout)


if __name__ == "__main__":
    unittest.main()
