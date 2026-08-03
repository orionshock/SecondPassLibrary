from __future__ import annotations

import json
import socket
from threading import Thread
import time
from urllib.request import Request, urlopen

from django.test import SimpleTestCase
import uvicorn


class UvicornProxyBoundaryTests(SimpleTestCase):
    def test_disabled_proxy_headers_preserve_direct_peer_address(self):
        async def peer_probe(scope, receive, send):
            body = json.dumps({"client": scope["client"][0]}).encode("ascii")
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body})

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("127.0.0.1", 0))
        server_socket.listen(5)
        port = server_socket.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                peer_probe,
                proxy_headers=False,
                lifespan="off",
                log_level="critical",
            )
        )
        thread = Thread(
            target=server.run,
            kwargs={"sockets": [server_socket]},
            daemon=True,
        )
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)

        try:
            request = Request(
                f"http://127.0.0.1:{port}/",
                headers={"X-Forwarded-For": "198.51.100.20"},
            )
            with urlopen(request, timeout=5) as response:  # noqa: S310
                payload = json.load(response)
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            server_socket.close()

        self.assertFalse(thread.is_alive())
        self.assertEqual(payload["client"], "127.0.0.1")
