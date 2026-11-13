#!/usr/bin/env python3
"""CS-806 Airable compatibility service; standard-library-only Python 3.11+.

Mihomo routes the configured Airable hostname through this HTTP CONNECT proxy.
The radio accepts the local TLS certificate inside that tunnel. The server's
own upstream traffic must bypass this proxy in Mihomo to avoid a routing loop.
"""

import argparse
import hashlib
import gzip
import http.client
import http.server
import json
import logging
import math
import os
from pathlib import Path
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request

LOG = logging.getLogger("cs806")
POPULAR = "/airable/radios/popular"
LOCAL = "/local/cs806/"
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailer", "transfer-encoding", "upgrade", "content-length"}


class Favorites:
    def __init__(self, path, host):
        self.path = Path(path)
        self.base = "https://" + host

    def stations(self):
        # Read on each request: Germany's five-minute sync owns this file.
        rows = json.loads(self.path.read_text())
        result = {}
        for row in rows:
            if row.get("category") not in ("Favoriten", "Favorites"):
                continue
            url = row["url"]
            parts = urllib.parse.urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname or parts.username:
                raise ValueError("invalid configured stream URL")
            # Stable across list reordering and renaming, unlike index-based IDs.
            key = "99" + str(int(hashlib.sha256(url.encode()).hexdigest()[:14], 16) % 10**14).zfill(14)
            result[key] = row
        return result

    def station(self, key, row, full=False):
        station = {
            "id": ["airable", "radio", key], "title": row["name"],
            "url": self.base + LOCAL + "station/" + key,
            "description": row.get("desc", ""),
            "slogan": "",
            "images": [],
            # The CS-806 retains prior station fields when they are omitted.
            # Our shared list has no verified geographic/language metadata.
            "place": {"id": ["airable", "place", "0"], "title": "", "url": self.base + POPULAR},
            "language": {"id": ["airable", "language", "0"], "title": "", "url": self.base + POPULAR},
        }
        if row.get("logo", "").startswith(("http://", "https://")):
            station["images"] = [{"url": row["logo"], "width": 150, "height": 150}]
        if full:
            # AsiaFM's extensionless endpoint supplies AAC; SRG includes /aac/.
            codec = row.get("codec") or ("AAC" if "/aac/" in row["url"] or
                row["url"].lower().endswith(".aac") or
                row["url"] == "http://yyt.asiafm.net:8000/asiafm" else "MP3")
            station["streams"] = [{
                "id": ["airable", "radio.stream", key], "title": codec,
                "url": self.base + LOCAL + "play/" + key,
                "codec": {"name": codec, "bitrate": row.get("bitrate", 128)}, "icy": not bool(row.get("nometa")),
            }]
        return station

    def directory(self, query):
        rows = sorted(self.stations().items(), key=lambda item: item[1]["name"].casefold())
        # Airable's page links use p, with collection.limit/offset in responses.
        params = urllib.parse.parse_qs(query)
        limit = min(100, max(1, int(params.get("limit", [20])[0])))
        offset = max(0, int(params.get("offset", [0])[0]))
        if "p" in params:
            offset = max(0, int(params["p"][0]) - 1) * limit
        pages = max(1, math.ceil(len(rows) / limit))
        url = self.base + POPULAR
        return {
            "id": ["airable.radios", "listing", "popular"], "title": "Our favorites", "url": url,
            "content": {
                "entries": [self.station(k, r) for k, r in rows[offset:offset + limit]],
                "pagination": {
                    "range": {"url": url + f"?limit={limit}&p=:value:", "replace": ":value:"},
                    "pages": {"url": url + f"?limit={limit}&p=:value:", "replace": ":value:",
                              "current": offset // limit + 1, "values": list(range(1, pages + 1))},
                },
                "collection": {"size": len(rows), "limit": limit, "offset": offset},
            },
        }


class QuietHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *unused):
        # BaseHTTPRequestHandler error messages can contain request credentials.
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(30)


class RadioHandler(QuietHandler):
    def send_body(self, status, body, content_type="application/json", headers=()):
        self.send_response(status)
        for key, value in headers:
            if key.lower() not in HOP_HEADERS | {"server", "date", "content-type"}:
                self.send_header(key, value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def send_json(self, data, status=200):
        self.send_body(status, json.dumps(data, ensure_ascii=True).encode(),
                       headers=[("Cache-Control", "no-store")])

    def do_GET(self):
        self.handle_radio()

    def do_POST(self):
        self.handle_radio()

    def handle_radio(self):
        path = urllib.parse.urlsplit(self.path)
        if path.scheme or path.netloc or not path.path.startswith("/"):
            self.send_error(400)
            return
        try:
            favorites = self.server.favorites
            if self.command == "GET" and path.path == POPULAR:
                answer = favorites.directory(path.query)
                LOG.info("favorites: %s entries", len(answer["content"]["entries"]))
                self.send_json(answer)
                return
            if path.path.startswith(LOCAL):
                match = re.fullmatch(re.escape(LOCAL) + r"(station|play|stream)/(99[0-9]{14})", path.path)
                if self.command != "GET" or not match:
                    self.send_error(404)
                    return
                action, key = match.groups()
                row = favorites.stations().get(key)
                if row is None:
                    self.send_json({"id": ["airable", "error"], "message": "Station removed"}, 404)
                    return
                if action == "stream":
                    self.stream(row)
                    return
                station = favorites.station(key, row, full=True)
                if action == "station":
                    self.send_json(station)
                else:
                    url = (favorites.base + LOCAL + "stream/" + key
                           if row.get("proxy") or row.get("nometa") else row["url"])
                    self.send_json({"id": ["airable", "redirect", key], "url": url, "content": station})
                    LOG.info("play: %s", row["name"])
                return
            self.forward()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            LOG.warning("request failed: %s", type(exc).__name__)
            if not getattr(self, "response_started", False):
                self.send_json({"id": ["airable", "error"], "message": "Service unavailable"}, 502)

    def forward(self):
        if self.headers.get("Transfer-Encoding"):
            self.send_error(400)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 <= length <= 65536:
            self.send_error(413)
            return
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
        headers["Host"] = self.server.upstream
        headers["Connection"] = "close"
        # Path, query, method and Authorization stay intact: requests are signed.
        conn = http.client.HTTPSConnection(self.server.upstream, timeout=20)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            res = conn.getresponse()
            data = res.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError("directory response too large")
            if getattr(self.server, "capture_dir", None):
                try:
                    decoded = gzip.decompress(data) if res.getheader("Content-Encoding") == "gzip" else data
                    # Diagnostic only: never capture Authorization or other request
                    # headers. Responses may carry signed URLs; keep them in /run.
                    record = {"path": self.path.split("?")[0], "status": res.status,
                              "body": json.loads(decoded)}
                    dest = self.server.capture_dir / f"{time.time_ns()}.json"
                    with open(dest, "x", opener=lambda p, f: os.open(p, f, 0o600)) as out:
                        json.dump(record, out)
                except (OSError, ValueError) as exc:
                    LOG.warning("diagnostic capture skipped: %s", type(exc).__name__)
            self.send_body(res.status, data, res.getheader("Content-Type", "application/json"), res.getheaders())
            LOG.info("upstream %s: %s", self.command, res.status)
        finally:
            conn.close()

    def stream(self, row):
        # Only admin-configured stream URLs are fetched; never accept a URL parameter
        # or forward the radio's Airable credentials to a broadcaster.
        headers = {"User-Agent": self.headers.get("User-Agent", "cachip 1.0"), "Accept-Encoding": "identity"}
        if not row.get("nometa") and self.headers.get("Icy-MetaData") == "1":
            headers["Icy-MetaData"] = "1"
        request = urllib.request.Request(row["url"], headers=headers)
        with urllib.request.urlopen(request, timeout=20) as res:
            self.send_response(res.status)
            self.send_header("Content-Type", res.headers.get("Content-Type", "audio/mpeg"))
            for name in ("icy-name", "icy-br", "icy-genre", "icy-metaint"):
                if name in res.headers and not (name == "icy-metaint" and row.get("nometa")):
                    self.send_header(name, res.headers[name])
            self.send_header("Connection", "close")
            self.end_headers()
            self.response_started = True
            self.close_connection = True
            while data := res.read(16384):
                self.wfile.write(data)


class ConnectHandler(QuietHandler):
    def do_CONNECT(self):
        if self.client_address[0] not in self.server.allowed_clients:
            self.send_error(403)
            return
        if self.path != self.server.upstream + ":443":
            self.send_error(403)
            return
        self.send_response(200, "Connection established")
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        try:
            with self.server.tls.wrap_socket(self.connection, server_side=True) as tls:
                RadioHandler(tls, self.client_address, self.server)
        except (OSError, TimeoutError):
            LOG.warning("TLS tunnel closed")

    def do_GET(self):
        if self.path == "/health" and self.client_address[0] in self.server.allowed_clients:
            try:
                self.server.favorites.stations()
                body, status = b"ok\n", 200
            except (OSError, ValueError, KeyError):
                body, status = b"favorites unavailable\n", 503
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True
        else:
            self.send_error(403)


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, *, upstream, data, context, clients):
        super().__init__(address, handler)
        self.upstream = upstream
        self.favorites = Favorites(data, upstream)
        self.tls = context
        self.allowed_clients = clients


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="10.18.0.13")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--upstream", default="5788230443.airable.io")
    parser.add_argument("--data", required=True)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--allow-client", action="append", default=["127.0.0.1", "10.18.0.2", "10.18.0.13"])
    parser.add_argument("--direct-tls-port", type=int, help="optional temporary DNAT test listener")
    parser.add_argument("--capture-dir", help="temporary upstream JSON diagnostics under /run")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.cert, args.key)
    options = dict(upstream=args.upstream, data=args.data, context=context, clients=args.allow_client)
    server = Server((args.bind, args.port), ConnectHandler, **options)
    if args.capture_dir:
        capture = Path(args.capture_dir).resolve()
        if not capture.is_relative_to(Path("/run")):
            parser.error("capture directory must be under /run")
        capture.mkdir(mode=0o700, parents=True, exist_ok=True)
        if capture.stat().st_mode & 0o077:
            parser.error("capture directory must have mode 0700")
        server.capture_dir = capture
    if args.direct_tls_port:
        direct = Server((args.bind, args.direct_tls_port), RadioHandler, **options)
        direct.socket = context.wrap_socket(direct.socket, server_side=True)
        threading.Thread(target=direct.serve_forever, daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
