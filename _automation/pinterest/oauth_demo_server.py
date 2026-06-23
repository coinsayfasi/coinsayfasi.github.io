#!/usr/bin/env python3
"""Browser-only Pinterest Standard-access demo — everything happens in ONE browser
window (no terminal, no window juggling), so the screen recording is deterministic.

Flow shown in the recording:
  1) OAuth: open the auth URL → Pinterest consent → "Give access".
  2) Browser is redirected to http://localhost:8085/callback?code=...  (our local
     server). The server then, server-side (app secret stays private):
       - exchanges the code for a Sandbox access token,
       - creates a board + a Pin (POST /v5/pins),
       - reads the Pin back (GET /v5/pins/{id}),
     and renders an HTML page that shows each API request/response + the created Pin.
  3) That page auto-redirects to https://www.pinterest.com/pin/{id}/ so the recording
     ends on the newly-created Pin live on the Pinterest platform.

Run:  PINTEREST_APP_SECRET=xxxxx python3 oauth_demo_server.py
Then open the printed auth URL in the browser (or it opens automatically).

⚠️ The redirect URI  http://localhost:8085/callback  must be registered in the
   Pinterest app (1581587) → Configure → Redirect URIs.
"""
from __future__ import annotations

import base64
import html
import os
import sys
import urllib.parse
import warnings
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

warnings.filterwarnings("ignore")
import requests

from pin_image import build_pin_image

APP_ID = os.environ.get("PINTEREST_APP_ID", "1581587").strip()
SECRET = os.environ.get("PINTEREST_APP_SECRET", "").strip()
PORT = int(os.environ.get("PINTEREST_DEMO_PORT", "8085"))
REDIRECT = f"http://localhost:{PORT}/callback"
SCOPES = "boards:read,boards:write,pins:read,pins:write"
SBX = "https://api-sandbox.pinterest.com/v5"
BOARD = "Tabserve Travel & Rental Tips"


def auth_url() -> str:
    q = urllib.parse.urlencode({
        "client_id": APP_ID, "redirect_uri": REDIRECT,
        "response_type": "code", "scope": SCOPES, "state": "tabserve",
    })
    return f"https://www.pinterest.com/oauth/?{q}"


def _page(body: str, refresh: str = "") -> bytes:
    return (f"""<!doctype html><html><head><meta charset="utf-8">
<title>Pinterest API Integration Demo — Tabserve</title>{refresh}
<style>
 body{{font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;background:#0f1320;
   color:#e8edf6;margin:0;padding:40px;display:flex;justify-content:center}}
 .wrap{{max-width:880px;width:100%}}
 h1{{color:#fff}} h2{{color:#e60023;margin-top:28px}}
 .step{{background:#171c2e;border:1px solid #283049;border-radius:12px;
   padding:18px 22px;margin:14px 0}}
 .ok{{color:#34d399;font-weight:700}}
 code,pre{{background:#0b0f1a;color:#9ad;border-radius:8px;padding:2px 6px;
   font:13px/1.5 SFMono-Regular,Menlo,monospace;word-break:break-all}}
 pre{{padding:12px 14px;overflow-x:auto;white-space:pre-wrap}}
 img.pin{{width:220px;border-radius:14px;float:right;margin:0 0 12px 24px}}
 a.btn{{display:inline-block;background:#e60023;color:#fff;text-decoration:none;
   padding:12px 22px;border-radius:24px;font-weight:700;margin-top:8px}}
</style></head><body><div class="wrap">{body}</div></body></html>""").encode()


def render_start() -> bytes:
    return _page(f"""
 <h1>Pinterest API Integration Demo</h1>
 <p>This app (ID <code>{APP_ID}</code>) connects to the Pinterest v5 API to create
    Pins on the user's behalf. Click below to start the OAuth flow.</p>
 <div class="step">Requested scopes: <code>{SCOPES}</code><br>
   Redirect URI: <code>{REDIRECT}</code></div>
 <a class="btn" href="{auth_url()}">Connect Pinterest &amp; create a Pin</a>""")


def do_demo(code: str) -> bytes:
    basic = base64.b64encode(f"{APP_ID}:{SECRET}".encode()).decode()
    # 1) token exchange (Sandbox)
    tr = requests.post(f"{SBX}/oauth/token",
                       headers={"Authorization": f"Basic {basic}",
                                "Content-Type": "application/x-www-form-urlencoded"},
                       data={"grant_type": "authorization_code", "code": code,
                             "redirect_uri": REDIRECT}, timeout=30)
    tr.raise_for_status()
    tok = tr.json()
    token = tok["access_token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    # 2) ensure board
    boards = s.get(f"{SBX}/boards", params={"page_size": 100}, timeout=20).json().get("items", [])
    board_id = next((b["id"] for b in boards if b.get("name", "").lower() == BOARD.lower()), None)
    if not board_id:
        board_id = s.post(f"{SBX}/boards", json={"name": BOARD, "privacy": "PUBLIC"},
                          timeout=20).json()["id"]
    # 3) create pin
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"OneBag API demo — {stamp}"
    img = build_pin_image("Travel lighter, stress less", "onebag", "One bag. Every trip.")
    payload = {"board_id": board_id, "title": title,
               "description": "Carry-on packing tips with OneBag. #travel #onebag #packinglight",
               "link": "https://coinsayfasi.github.io/go/onebag/",
               "alt_text": "OneBag packing tips",
               "media_source": {"source_type": "image_base64", "content_type": "image/png",
                                 "data": base64.b64encode(img).decode("ascii")}}
    pr = s.post(f"{SBX}/pins", json=payload, timeout=60)
    pr.raise_for_status()
    pin_id = pr.json()["id"]
    # 4) read back
    pin = s.get(f"{SBX}/pins/{pin_id}", timeout=20).json()
    img_uri = "data:image/png;base64," + base64.b64encode(img).decode("ascii")
    pin_url = f"https://www.pinterest.com/pin/{pin_id}/"
    body = f"""
 <h1>Pinterest API Integration — live result</h1>
 <img class="pin" src="{img_uri}" alt="created pin">
 <h2>1 · OAuth complete</h2>
 <div class="step">Authorization <code>code</code> received at our redirect URI and
   exchanged for an access token.<br>Granted scopes:
   <code>{html.escape(tok.get('scope',''))}</code></div>
 <h2>2 · Token exchange — API call</h2>
 <div class="step"><pre>POST {SBX}/oauth/token
Authorization: Basic base64(app_id:app_secret)
grant_type=authorization_code &amp; code=… &amp; redirect_uri={REDIRECT}

→ 200 OK  access_token: {html.escape(token[:14])}…</pre></div>
 <h2>3 · Create Pin — API call</h2>
 <div class="step"><pre>POST {SBX}/pins   (board "{BOARD}")
title: {html.escape(title)}

→ 201 Created  <span class="ok">Pin id: {pin_id}</span></pre></div>
 <h2>4 · Read the Pin back — API call</h2>
 <div class="step"><pre>GET {SBX}/pins/{pin_id}
→ id: {pin.get('id')}
   title: {html.escape(str(pin.get('title')))}
   board_id: {pin.get('board_id')}
   link: {pin.get('link')}
   created_at: {pin.get('created_at')}</pre></div>
 <p class="ok">✓ Pin created via the Pinterest API. Opening it live on Pinterest…</p>
 <a class="btn" href="{pin_url}">View this Pin on Pinterest →</a>"""
    # auto-redirect to the live pin after a few seconds
    refresh = f'<meta http-equiv="refresh" content="10;url={pin_url}">'
    print(f"[demo] pin created: {pin_id}  ({title})", flush=True)
    return _page(body, refresh)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            qs = urllib.parse.parse_qs(parsed.query)
            code = qs.get("code", [""])[0]
            try:
                out = do_demo(code) if code else _page("<h1>Missing code.</h1>")
            except Exception as e:  # noqa: BLE001
                out = _page(f"<h1>Demo error</h1><pre>{html.escape(str(e))}</pre>")
                print(f"[demo] ERROR: {e}", flush=True)
            self._send(out)
        elif parsed.path in ("/", "/start"):
            self._send(render_start())
        else:
            self._send(_page("<h1>Not found.</h1>"))

    def _send(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    if not SECRET:
        sys.exit("HATA: PINTEREST_APP_SECRET env gerekli.")
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Yerel sunucu çalışıyor: http://localhost:{PORT}/")
    print(f"Redirect URI (Pinterest app'e ekli OLMALI): {REDIRECT}")
    print(f"\nBaşlamak için tarayıcıda aç:\n  http://localhost:{PORT}/\n")
    try:
        webbrowser.open(f"http://localhost:{PORT}/")
    except Exception:  # noqa: BLE001
        pass
    srv.serve_forever()


if __name__ == "__main__":
    main()
