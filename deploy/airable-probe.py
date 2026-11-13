#!/usr/bin/env python3
"""Temporary TLS pass-through HTTP probe for an owned Airable radio.

Run on the radio server with its existing TLS certificate. Captures contain
device credentials: keep the output in a mode-0700 directory under /run.
Only the explicitly supplied upstream host is contacted; redirects are returned
to the radio. No request credentials are written to stdout or the journal.
"""

import argparse
import http.client
import http.server
import json
import os
from pathlib import Path
import ssl
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", required=True)
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    output = Path(args.output).resolve()
    if not output.is_relative_to(Path("/run")):
        parser.error("captures must be kept under /run")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if output.stat().st_mode & 0o077:
        parser.error("capture directory must have mode 0700")

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_GET(self):
            if not self.path.startswith("/") or self.path.startswith("//"):
                self.send_error(400)
                return
            headers = dict(self.headers)
            headers["Host"] = args.upstream
            headers["Accept-Encoding"] = "identity"
            headers["Connection"] = "close"
            conn = http.client.HTTPSConnection(args.upstream, timeout=20)
            try:
                conn.request("GET", self.path, headers=headers)
                response = conn.getresponse()
                body = response.read(4 * 1024 * 1024 + 1)
                if len(body) > 4 * 1024 * 1024:
                    raise ValueError("response exceeds directory capture limit")
                record = {
                    "path": self.path,
                    "request_headers": headers,
                    "status": response.status,
                    "response_headers": dict(response.getheaders()),
                    "body": body.decode("utf-8", errors="replace"),
                }
                (output / f"{time.time_ns()}.json").write_text(json.dumps(record))
                self.send_response(response.status)
                for name, value in response.getheaders():
                    if name.lower() not in {"connection", "transfer-encoding", "content-length"}:
                        self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                print(f"{self.path.split('?')[0]}: {response.status}, {len(body)} bytes", flush=True)
            except Exception as exc:
                print(f"probe failed: {type(exc).__name__}", flush=True)
                self.send_error(502)
            finally:
                conn.close()

    server = http.server.ThreadingHTTPServer((args.bind, args.port), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.cert, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
