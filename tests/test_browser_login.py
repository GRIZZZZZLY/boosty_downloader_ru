"""The part of the browser login that turns cookies into a token.

Launching a browser is not tested here; this covers the step that decides
whether the person is logged in and what gets stored.
"""

import json
import sys
import urllib.parse
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from core.browser_login import (  # noqa: E402
    _build_token,
    _cookies_of_boosty,
    find_browser,
)

# 2026-09-21 in milliseconds, which is how Boosty writes expiresAt.
EXPIRES_AT_MS = 1789000000000


def cookie(name, value, domain=".boosty.to", http_only=False):
    return {"name": name, "value": value, "domain": domain, "httpOnly": http_only}


def auth_cookie(access_token="token-123", expires_at=EXPIRES_AT_MS):
    payload = json.dumps({"accessToken": access_token, "expiresAt": expires_at})
    return cookie("auth", urllib.parse.quote(payload))


def test_cookies_of_other_sites_are_ignored():
    cookies = [auth_cookie(), cookie("_ga", "1", domain=".google.com")]
    assert [c["name"] for c in _cookies_of_boosty(cookies)] == ["auth"]


def test_no_auth_cookie_means_not_logged_in_yet():
    assert _build_token([cookie("_ga", "1")]) is None


def test_empty_auth_cookie_means_not_logged_in_yet():
    assert _build_token([cookie("auth", "")]) is None


def test_unreadable_auth_cookie_is_not_a_crash():
    assert _build_token([cookie("auth", "not-json-at-all")]) is None


def test_auth_cookie_without_a_token_is_rejected():
    payload = urllib.parse.quote(json.dumps({"expiresAt": EXPIRES_AT_MS}))
    assert _build_token([cookie("auth", payload)]) is None


def test_token_is_taken_from_the_auth_cookie():
    token = _build_token([auth_cookie()])
    assert token is not None
    assert token.authorization == "token-123"


def test_expiry_is_converted_from_milliseconds_to_seconds():
    """The console script passes expiresAt straight through, in milliseconds."""
    token = _build_token([auth_cookie()])
    assert token.expires_in == EXPIRES_AT_MS // 1000


def test_cookie_header_holds_every_boosty_cookie():
    token = _build_token([auth_cookie(), cookie("_clientId", "abc")])
    assert "_clientId=abc" in token.cookie
    assert "auth=" in token.cookie


def test_cookie_header_leaves_out_http_only_ones():
    """The console script reads document.cookie, which cannot see them."""
    cookies = [auth_cookie(), cookie("secret", "x", http_only=True)]
    assert "secret" not in _build_token(cookies).cookie


def test_cookie_header_leaves_out_other_sites():
    cookies = [auth_cookie(), cookie("_ga", "1", domain=".google.com")]
    assert "_ga" not in _build_token(cookies).cookie


def test_browser_lookup_returns_a_real_file_or_nothing():
    found = find_browser()
    assert found is None or found.is_file()
