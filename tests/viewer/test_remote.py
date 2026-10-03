"""The viewer from another PC: access token, read-only and HTTPS (#141).

Traces to: VIEW-FR-025 .. VIEW-FR-027, SWE4-UT-VIEWREMOTE.
"""

from __future__ import annotations

import http.client
import json
import shutil
import socket
import ssl
import subprocess
import threading

import pytest

from benchtools.viewer.server import (
    GUARD_HEADER, TOKEN_COOKIE, Catalogue, Hub, Launcher, ViewerServer, build_parser,
    is_loopback, new_token,
)

TOKEN = "s3cret-token"


def _serve(tmp_path, host="127.0.0.1", **options):
    hub = Hub(interval=0.05).start()
    catalogue = Catalogue([], [])
    server = ViewerServer(hub, catalogue, Launcher(catalogue, str(tmp_path / "runs")), 0, host,
                          **options)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    return server


@pytest.fixture
def guarded(tmp_path):
    server = _serve(tmp_path, token=TOKEN)
    yield server
    server.shutdown()
    server.server_close()
    server.hub.stop()


def _ask(server, method, path, headers=None, body=None, **where):
    """*where*: ``host`` to connect to (127.0.0.1), ``context`` for HTTPS."""
    host, context = where.get("host", "127.0.0.1"), where.get("context")
    if context is not None:
        connection = http.client.HTTPSConnection(host, server.port, timeout=10, context=context)
    else:
        connection = http.client.HTTPConnection(host, server.port, timeout=10)
    sent = {"Host": "viewer.example:%d" % server.port}
    sent.update(headers or {})
    connection.request(method, path, body=json.dumps(body).encode() if body is not None else None,
                       headers=sent)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response, data


class TestToken:
    def test_nothing_is_answered_without_the_token(self, guarded):
        for path in ("/", "/static/app.js", "/api/state", "/api/events"):
            response, data = _ask(guarded, "GET", path)
            assert response.status == 401, path
            assert b"access token" in data

    def test_a_bearer_token_is_accepted_whatever_the_host_name(self, guarded):
        response, _data = _ask(guarded, "GET", "/api/state",
                               {"Authorization": "Bearer " + TOKEN})
        assert response.status == 200

    def test_opening_the_printed_address_sets_the_cookie(self, guarded):
        response, _data = _ask(guarded, "GET", "/?token=" + TOKEN)
        assert response.status == 303
        cookie = response.getheader("Set-Cookie")
        assert cookie.startswith("%s=%s" % (TOKEN_COOKIE, TOKEN))
        assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
        response, data = _ask(guarded, "GET", "/", {"Cookie": "%s=%s" % (TOKEN_COOKIE, TOKEN)})
        assert response.status == 200 and b"/static/app.js" in data

    @pytest.mark.parametrize("headers", [
        {"Authorization": "Bearer wrong"},
        {"Cookie": "%s=wrong" % TOKEN_COOKIE},
        {"Cookie": "other=%s" % TOKEN},
    ])
    def test_a_wrong_token_is_refused(self, guarded, headers):
        assert _ask(guarded, "GET", "/api/state", headers)[0].status == 401

    def test_a_wrong_token_in_the_address_does_not_sign_in(self, guarded):
        assert _ask(guarded, "GET", "/?token=wrong")[0].status == 401

    def test_a_post_needs_the_token_and_still_the_guard_header(self, guarded):
        bearer = {"Authorization": "Bearer " + TOKEN}
        assert _ask(guarded, "POST", "/api/attach", {GUARD_HEADER: "1"},
                    {"event_log": "x"})[0].status == 401
        assert _ask(guarded, "POST", "/api/attach", bearer, {"event_log": "x"})[0].status == 403
        assert _ask(guarded, "POST", "/api/attach", dict(bearer, **{GUARD_HEADER: "1"}),
                    {"event_log": "x"})[0].status == 200


class TestReadOnly:
    def test_a_read_only_viewer_still_needs_the_token(self, tmp_path):
        server = _serve(tmp_path, token=TOKEN, read_only=True)
        try:
            assert _ask(server, "POST", "/api/attach", {GUARD_HEADER: "1"},
                        {"event_log": "x"})[0].status == 401
        finally:
            server.shutdown()
            server.server_close()
            server.hub.stop()

    def test_nothing_that_changes_anything_is_accepted(self, tmp_path):
        server = _serve(tmp_path, token=TOKEN, read_only=True)
        try:
            headers = {"Authorization": "Bearer " + TOKEN, GUARD_HEADER: "1"}
            for path in ("/api/attach", "/api/start", "/api/control"):
                response, data = _ask(server, "POST", path, headers, {"event_log": "x"})
                assert response.status == 403 and b"read-only" in data
            assert _ask(server, "GET", "/api/state", headers)[0].status == 200
        finally:
            server.shutdown()
            server.server_close()
            server.hub.stop()


class TestBinding:
    @pytest.mark.parametrize("host, loopback", [
        ("127.0.0.1", True), ("127.0.0.2", True), ("::1", True), ("localhost", True),
        ("0.0.0.0", False), ("192.168.1.20", False), ("bench-pc", False)])
    def test_loopback(self, host, loopback):
        assert is_loopback(host) is loopback

    def test_another_address_without_a_token_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="access token"):
            _serve(tmp_path, host="0.0.0.0")

    def test_tokens_are_long_and_fresh(self):
        assert len(new_token()) >= 40 and new_token() != new_token()

    def test_options(self):
        args = build_parser().parse_args(["--bind", "0.0.0.0", "--read-only",
                                          "--tls-cert", "c.pem", "--tls-key", "k.pem"])
        assert (args.bind, args.read_only, args.tls_cert, args.tls_key) == (
            "0.0.0.0", True, "c.pem", "k.pem")
        assert build_parser().parse_args([]).bind == "127.0.0.1"

    def test_reached_by_another_address_of_this_machine(self, tmp_path):
        try:
            address = socket.gethostbyname(socket.gethostname())
        except OSError:
            address = ""
        if not address or is_loopback(address):
            pytest.skip("this machine has no address other than loopback")
        server = _serve(tmp_path, host=address, token=TOKEN)
        try:
            response, _data = _ask(server, "GET", "/api/state",
                                   {"Authorization": "Bearer " + TOKEN}, host=address)
            assert response.status == 200
            assert _ask(server, "GET", "/api/state", host=address)[0].status == 401
        finally:
            server.shutdown()
            server.server_close()
            server.hub.stop()


def test_https_with_a_certificate(tmp_path):
    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("openssl is not available to make a test certificate")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    made = subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                           "-subj", "/CN=localhost", "-keyout", str(key), "-out", str(cert)],
                          capture_output=True, check=False)
    if made.returncode:
        pytest.skip("openssl could not make a test certificate")
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(str(cert), str(key))
    server = _serve(tmp_path, token=TOKEN, tls=tls)
    try:
        # What is under test is that the server speaks TLS, not chain validation
        # of a throwaway self-signed certificate.
        client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client.check_hostname = False
        client.verify_mode = ssl.CERT_NONE
        response, _data = _ask(server, "GET", "/?token=" + TOKEN, context=client)
        assert response.status == 303
        assert "Secure" in response.getheader("Set-Cookie")
    finally:
        server.shutdown()
        server.server_close()
        server.hub.stop()
