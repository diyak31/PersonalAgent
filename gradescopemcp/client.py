"""
Gradescope session client.
Uses a browser session cookie for authentication — no login flow needed.

Setup:
1. Log into gradescope.com in your browser
2. Open DevTools (F12) → Application → Cookies → https://www.gradescope.com
3. Copy the value of _gradescope_session
4. Set env var: GRADESCOPE_SESSION=<value>
"""

import os
import httpx
from bs4 import BeautifulSoup

BASE = "https://www.gradescope.com"


class GradescopeClient:
    def __init__(self):
        session_cookie = os.environ.get("GRADESCOPE_SESSION")
        if not session_cookie:
            raise RuntimeError(
                "Missing GRADESCOPE_SESSION environment variable.\n"
                "Log into gradescope.com, open DevTools → Application → Cookies, "
                "copy _gradescope_session value, and set it as GRADESCOPE_SESSION."
            )
        self._client = httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            cookies={"_gradescope_session": session_cookie},
            timeout=20,
        )

    def get(self, path: str) -> BeautifulSoup:
        r = self._client.get(f"{BASE}{path}")
        r.raise_for_status()
        # If redirected to login, session has expired
        if "/login" in str(r.url):
            raise RuntimeError(
                "Gradescope session expired. Please log in again and update GRADESCOPE_SESSION."
            )
        return BeautifulSoup(r.text, "html.parser")


_instance: GradescopeClient | None = None


def get_client() -> GradescopeClient:
    global _instance
    if _instance is None:
        _instance = GradescopeClient()
    return _instance
