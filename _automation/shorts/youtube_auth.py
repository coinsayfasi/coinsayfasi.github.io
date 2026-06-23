#!/usr/bin/env python3
"""YouTube OAuth — tek seferlik refresh token al (teknopattv kanalı için).

Desktop-app loopback akışı: localhost'ta server açar, tarayıcıda izin ekranını
açar, dönen code'u access+refresh token'a çevirir, refresh token'ı dosyaya yazar.

Env: YT_CLIENT_ID, YT_CLIENT_SECRET. Çıktı: /tmp/yt_refresh.txt
"""
from __future__ import annotations

import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests

CID = os.environ["YT_CLIENT_ID"].strip()
CSEC = os.environ["YT_CLIENT_SECRET"].strip()
PORT = 8080
REDIR = f"http://localhost:{PORT}/"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
OUT = Path("/tmp/yt_refresh.txt")

AUTH = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": CID, "redirect_uri": REDIR, "response_type": "code",
    "scope": SCOPE, "access_type": "offline", "prompt": "consent",
})


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("code", [None])[0]
        if not code:
            self.send_response(200); self.end_headers(); self.wfile.write(b"bekleniyor...")
            return
        r = requests.post("https://oauth2.googleapis.com/token",
                          data={"code": code, "client_id": CID, "client_secret": CSEC,
                                "redirect_uri": REDIR, "grant_type": "authorization_code"},
                          timeout=30)
        tok = r.json()
        rt = tok.get("refresh_token", "")
        OUT.write_text(rt)
        ok = bool(rt)
        print(f"[yt] refresh_token alindi: {ok}  {'' if ok else r.text[:300]}", flush=True)
        body = ("<h1>Baglandi! Bu sekmeyi kapatabilirsin.</h1>" if ok
                else f"<h1>HATA</h1><pre>{r.text}</pre>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)


def main():
    print("AUTH_URL: " + AUTH, flush=True)
    try:
        webbrowser.open(AUTH)
    except Exception:
        pass
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
