"""Minimal Pinterest API v5 client — list/ensure boards and create image pins.

Auth: a Bearer access token (PINTEREST_ACCESS_TOKEN). Board creation needs the
`boards:write` scope; pin creation needs `pins:write`. Images are uploaded inline
as base64, so nothing needs to be hosted publicly.
"""
from __future__ import annotations

import base64
from typing import Optional

import requests

API = "https://api.pinterest.com/v5"


def refresh_access_token(app_id: str, app_secret: str, refresh_token: str) -> str:
    """Exchange a long-lived refresh token for a fresh access token.

    Lets the cron run forever without re-pasting a token every 30 days: store
    PINTEREST_REFRESH_TOKEN + PINTEREST_APP_ID + PINTEREST_APP_SECRET as secrets.
    """
    basic = base64.b64encode(f"{app_id}:{app_secret}".encode()).decode()
    r = requests.post(
        f"{API}/oauth/token",
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"refresh_access_token {r.status_code}: {r.text[:300]}")
    return r.json()["access_token"]


class PinterestClient:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}"})

    def list_boards(self) -> list[dict]:
        boards, bookmark = [], None
        while True:
            params = {"page_size": 100}
            if bookmark:
                params["bookmark"] = bookmark
            r = self.s.get(f"{API}/boards", params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            boards.extend(data.get("items", []))
            bookmark = data.get("bookmark")
            if not bookmark:
                return boards

    def ensure_board(self, name: str, description: str = "") -> str:
        """Return board id for `name`, creating a PUBLIC board if missing."""
        for b in self.list_boards():
            if b.get("name", "").strip().lower() == name.strip().lower():
                return b["id"]
        r = self.s.post(
            f"{API}/boards",
            json={"name": name, "description": description[:500], "privacy": "PUBLIC"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()["id"]

    def create_pin(self, board_id: str, title: str, description: str, link: str,
                   image_png: bytes, alt_text: str = "") -> Optional[str]:
        payload = {
            "board_id": board_id,
            "title": title[:100],
            "description": description[:800],
            "link": link,
            "alt_text": (alt_text or title)[:500],
            "media_source": {
                "source_type": "image_base64",
                "content_type": "image/png",
                "data": base64.b64encode(image_png).decode("ascii"),
            },
        }
        r = self.s.post(f"{API}/pins", json=payload, timeout=40)
        if r.status_code >= 400:
            raise RuntimeError(f"create_pin {r.status_code}: {r.text[:300]}")
        return r.json().get("id")
