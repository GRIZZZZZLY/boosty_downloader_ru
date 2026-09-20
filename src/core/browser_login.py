"""Log in by opening a browser window instead of pasting a script.

A Chromium browser started with `--remote-debugging-port` speaks the DevTools
protocol, which can read the cookies of the profile it is running. So the app
opens boosty.to in a browser the machine already has, waits for the person to
log in as they normally would, and takes the `auth` cookie out of that window.

Nothing is installed and nothing is bundled: the browser is the one already on
the machine, and the protocol runs over the aiohttp the app already depends on.
The browser is started with a throwaway profile, so it never touches the
person's own browser data, and the profile is deleted afterwards.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

import aiohttp

from core.defs.common import AuthToken
from core.logger import setup_logger

__all__ = ["BrowserLoginError", "find_browser", "login_through_browser"]

logger = setup_logger()

BOOSTY_URL = "https://boosty.to"
AUTH_COOKIE = "auth"

# How long to wait for the person to finish logging in.
LOGIN_TIMEOUT_SECONDS = 600
POLL_SECONDS = 2
# The browser writes its port into this file once the protocol is listening.
PORT_FILE = "DevToolsActivePort"
BROWSER_START_TIMEOUT_SECONDS = 30


class BrowserLoginError(Exception):
    """Something went wrong that the person can act on."""


def _candidate_browsers() -> list[Path]:
    """Chromium browsers in their usual places, Edge first.

    Edge ships with Windows, so it is the one that is always there.
    """
    roots = [
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("PROGRAMFILES"),
        os.environ.get("LOCALAPPDATA"),
    ]
    relative = [
        Path("Microsoft/Edge/Application/msedge.exe"),
        Path("Google/Chrome/Application/chrome.exe"),
        Path("Chromium/Application/chrome.exe"),
    ]
    candidates = [Path(root) / tail for root in roots if root for tail in relative]
    # Linux and macOS, for running from source.
    candidates += [
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/microsoft-edge"),
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    return candidates


def find_browser() -> Optional[Path]:
    """The first Chromium browser found on this machine."""
    for candidate in _candidate_browsers():
        if candidate.is_file():
            return candidate
    return None


async def _read_debugger_url(profile_dir: Path, process) -> str:
    """Wait for the browser to publish the port it is listening on."""
    port_file = profile_dir / PORT_FILE
    deadline = asyncio.get_running_loop().time() + BROWSER_START_TIMEOUT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        if process.poll() is not None:
            raise BrowserLoginError("The browser closed before it was ready")
        if port_file.exists():
            content = port_file.read_text(encoding="utf-8").splitlines()
            if len(content) >= 2 and content[0].strip():
                return f"ws://127.0.0.1:{content[0].strip()}{content[1].strip()}"
        await asyncio.sleep(0.2)
    raise BrowserLoginError("The browser did not start in time")


def _cookies_of_boosty(cookies: list[dict]) -> list[dict]:
    return [c for c in cookies if "boosty.to" in (c.get("domain") or "")]


def _build_token(cookies: list[dict]) -> Optional[AuthToken]:
    """Turn the browser's cookies into the token the app stores.

    Mirrors what the console script produces: the header is built from the
    cookies a page can see, which is the set already known to work, so
    HttpOnly ones are left out.
    """
    boosty = _cookies_of_boosty(cookies)
    auth = next((c for c in boosty if c.get("name") == AUTH_COOKIE), None)
    if not auth or not auth.get("value"):
        return None
    try:
        payload = json.loads(urllib.parse.unquote(auth["value"]))
    except ValueError as e:
        logger.error("The auth cookie is not readable", exc_info=e)
        return None
    access_token = payload.get("accessToken")
    expires_at = payload.get("expiresAt")
    if not access_token or not expires_at:
        return None

    full_cookie = "; ".join(
        f"{c['name']}={c['value']}" for c in boosty if not c.get("httpOnly")
    )
    return AuthToken(
        authorization=access_token,
        cookie=full_cookie,
        expires_in=int(int(expires_at) / 1000),
    )


async def _wait_for_login(
    debugger_url: str,
    session: aiohttp.ClientSession,
    on_status: Optional[Callable[[str], None]],
) -> AuthToken:
    """Ask the browser for its cookies until the person has logged in."""
    async with session.ws_connect(debugger_url, max_msg_size=0) as socket:
        deadline = asyncio.get_running_loop().time() + LOGIN_TIMEOUT_SECONDS
        message_id = 0
        while asyncio.get_running_loop().time() < deadline:
            message_id += 1
            await socket.send_json({"id": message_id, "method": "Storage.getCookies"})
            while True:
                answer = json.loads(await socket.receive_str())
                if answer.get("id") == message_id:
                    break
            cookies = answer.get("result", {}).get("cookies", [])
            token = _build_token(cookies)
            if token:
                return token
            if on_status:
                on_status("waiting")
            await asyncio.sleep(POLL_SECONDS)
    raise BrowserLoginError("Timed out waiting for the login")


async def login_through_browser(
    on_status: Optional[Callable[[str], None]] = None,
) -> AuthToken:
    """Open a browser, wait for the login, and return the token."""
    browser = find_browser()
    if not browser:
        raise BrowserLoginError("No Chromium browser found on this computer")

    profile_dir = Path(tempfile.mkdtemp(prefix="boosty-login-"))
    logger.info(f"Starting {browser.name} with a throwaway profile")
    process = subprocess.Popen(
        [
            str(browser),
            f"--user-data-dir={profile_dir}",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            BOOSTY_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        debugger_url = await _read_debugger_url(profile_dir, process)
        async with aiohttp.ClientSession() as session:
            return await _wait_for_login(debugger_url, session, on_status)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile_dir, ignore_errors=True)
