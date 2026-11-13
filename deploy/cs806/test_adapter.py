import http.client
import json
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import adapter


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.cert, cls.key = cls.root / "cert.pem", cls.root / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", str(cls.key), "-out", str(cls.cert), "-days", "1",
                        "-subj", "/CN=radio.test"], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.data = self.root / "stations.json"
        self.rows = [
            {"name": "Zulu", "url": "http://audio.test/z.mp3", "category": "Favoriten"},
            {"name": "Alpha", "url": "https://audio.test/a.aac", "category": "Favorites", "proxy": True},
            {"name": "Hidden", "url": "http://audio.test/h.mp3", "category": "Other"},
        ]
        self.save()
        self.favorites = adapter.Favorites(self.data, "radio.test")

    def save(self):
        self.data.write_text(json.dumps(self.rows))

    def test_protocol_filter_sort_and_pagination(self):
        first = self.favorites.directory("limit=1")
        self.assertEqual(first["id"], ["airable.radios", "listing", "popular"])
        # Captured CS-806 responses have three-part IDs. Two-part IDs make
        # app 0.43.3.ru leave Internet Radio for its main menu.
        for entry in first["content"]["entries"]:
            self.assertEqual(entry["id"][:2], ["airable", "radio"])
            self.assertRegex(entry["id"][2], r"^\d{16}$")
        self.assertEqual(first["content"]["entries"][0]["title"], "Alpha")
        self.assertEqual(first["content"]["collection"], {"size": 2, "limit": 1, "offset": 0})
        self.assertEqual(first["content"]["pagination"]["pages"]["values"], [1, 2])
        self.assertEqual(self.favorites.directory("limit=1&p=2")["content"]["entries"][0]["title"], "Zulu")

    def test_reload_and_stable_saved_station_links(self):
        before = self.favorites.stations()
        self.rows.reverse()
        self.rows[2]["name"] = "Renamed"
        self.save()
        self.assertEqual(set(before), set(self.favorites.stations()))
        self.assertIn("Renamed", [r["name"] for r in self.favorites.stations().values()])
        self.rows = []
        self.save()
        self.assertEqual(self.favorites.directory("")["content"]["entries"], [])

    def start_server(self, handler=adapter.ConnectHandler):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(self.cert, self.key)
        server = adapter.Server(("127.0.0.1", 0), handler, upstream="radio.test", data=self.data,
                                context=ctx, clients=["127.0.0.1"])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def tunnel(self, server, path):
        conn = http.client.HTTPSConnection("127.0.0.1", server.server_port,
                                          context=ssl._create_unverified_context(), timeout=3)
        conn.set_tunnel("radio.test", 443)
        conn.request("GET", path)
        res = conn.getresponse()
        status, body = res.status, res.read()
        conn.close()
        return status, json.loads(body)

    def test_real_connect_tls_list_detail_play_and_deleted_preset(self):
        server = self.start_server()
        status, listing = self.tunnel(server, adapter.POPULAR)
        self.assertEqual(status, 200)
        entry = listing["content"]["entries"][0]
        path = entry["url"].removeprefix("https://radio.test")
        _, detail = self.tunnel(server, path)
        self.assertEqual(detail["place"]["title"], "")
        self.assertEqual(detail["language"]["title"], "")
        self.assertEqual(detail["slogan"], "")
        self.assertEqual(detail["streams"][0]["codec"]["name"], "AAC")
        _, play = self.tunnel(server, detail["streams"][0]["url"].removeprefix("https://radio.test"))
        self.assertEqual(play["id"], ["airable", "redirect", entry["id"][2]])
        self.assertEqual(len(detail["streams"][0]["id"]), 3)
        self.assertIn("/local/cs806/stream/", play["url"])
        self.rows = []
        self.save()
        self.assertEqual(self.tunnel(server, path)[0], 404)

    def test_connect_rejects_other_destinations(self):
        server = self.start_server()
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        conn.request("CONNECT", "unrelated.test:443")
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()

    def test_preserves_signed_upstream_requests(self):
        server = self.start_server(adapter.RadioHandler)
        with patch.object(adapter.http.client, "HTTPSConnection") as upstream:
            response = upstream.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"upstream":true}'
            response.getheaders.return_value = [("Content-Type", "application/json")]
            response.getheader.return_value = "application/json"
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request("GET", "/airable/radios/search?q=hello%20world", headers={"Authorization": "Basic test-only"})
            res = conn.getresponse()
            self.assertEqual(json.loads(res.read()), {"upstream": True})
            args, kwargs = upstream.return_value.request.call_args
            self.assertEqual(args, ("GET", "/airable/radios/search?q=hello%20world"))
            self.assertEqual(kwargs["headers"]["Authorization"], "Basic test-only")
            conn.close()

    def test_nometa_stream_does_not_forward_credentials(self):
        seen = {}
        class Broadcaster(adapter.QuietHandler):
            def do_GET(self):
                seen.update(dict(self.headers))
                self.send_response(200)
                self.send_header("Content-Type", "audio/aac")
                self.send_header("Content-Length", "4")
                self.end_headers()
                self.wfile.write(b"test")
        audio = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Broadcaster)
        threading.Thread(target=audio.serve_forever, daemon=True).start()
        self.addCleanup(audio.server_close)
        self.addCleanup(audio.shutdown)
        self.rows[0].update(url=f"http://127.0.0.1:{audio.server_port}/audio", nometa=True, proxy=True)
        self.save()
        key = next(k for k,r in self.favorites.stations().items() if r["name"] == "Zulu")
        server = self.start_server(adapter.RadioHandler)
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        conn.request("GET", adapter.LOCAL+"stream/"+key, headers={"Authorization": "Basic test-only", "Icy-MetaData": "1"})
        res = conn.getresponse()
        self.assertEqual(res.read(), b"test")
        self.assertNotIn("Authorization", seen)
        self.assertNotIn("Icy-MetaData", seen)
        conn.close()


if __name__ == "__main__":
    unittest.main()
