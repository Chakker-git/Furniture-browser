"""Polite HTTP client: identifies itself, obeys robots.txt and Crawl-delay,
rate-limits per host, backs off on 429/5xx. It does NOT try to defeat
bot protection (CAPTCHAs, Cloudflare/Akamai/DataDome challenges): a site that
blocks us is reported as blocked, and should be covered by a feed instead."""
from __future__ import annotations

import os
import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

DEFAULT_UA = os.environ.get(
    "FB_USER_AGENT", "FurnitureBrowserBot/0.1 (+https://example.invalid/bot; personal research)")


class Blocked(Exception):
    """robots.txt disallows the URL, or the site answered with a bot challenge."""


class PoliteClient:
    def __init__(self, delay: float = 1.5, timeout: float = 30.0, user_agent: str = DEFAULT_UA,
                 transport: httpx.BaseTransport | None = None, max_retries: int = 3,
                 respect_robots: bool = True):
        self.delay = delay
        self.user_agent = user_agent
        self.max_retries = max_retries
        self.respect_robots = respect_robots
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._delays: dict[str, float] = {}
        self.robots_status: dict[str, int] = {}
        self.client = httpx.Client(
            timeout=timeout, follow_redirects=True, transport=transport,
            headers={"User-Agent": user_agent,
                     "Accept-Language": "da-DK,da;q=0.9,de-DE;q=0.8,de;q=0.7,en;q=0.6"})
        self.sleep = time.sleep  # swapped out in tests

    def close(self):
        self.client.close()

    # -- robots ---------------------------------------------------------------
    def robots(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(host + "/robots.txt")
                self.robots_status[parts.netloc] = r.status_code
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                elif r.status_code in (401, 403, 429) or r.status_code >= 500:
                    # 401/403: the site refuses bots outright. 429/5xx: per Google's
                    # robots.txt rules, treat as "everything disallowed for now"
                    # rather than hammering a site that is already pushing back.
                    rp.disallow_all = True
                else:  # 404 etc.: no robots.txt means no restrictions
                    rp.allow_all = True
            except httpx.HTTPError:
                rp.allow_all = True
            self._robots[host] = rp
            cd = rp.crawl_delay(self.user_agent)
            if cd:
                self._delays[parts.netloc] = min(float(cd), 30.0)
        return self._robots[host]

    def sitemaps_from_robots(self, base_url: str) -> list[str]:
        rp = self.robots(base_url)
        return list(rp.site_maps() or []) if rp else []

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        rp = self.robots(url)
        return rp.can_fetch(self.user_agent, url) if rp else True

    # -- fetch ----------------------------------------------------------------
    def _throttle(self, netloc: str):
        delay = max(self.delay, self._delays.get(netloc, 0))
        wait = self._last.get(netloc, 0) + delay - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        self._last[netloc] = time.monotonic()

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        if not self.allowed(url):
            raise Blocked(f"robots.txt disallows {url}")
        netloc = urlsplit(url).netloc
        backoff = 5.0
        for attempt in range(self.max_retries + 1):
            self._throttle(netloc)
            try:
                r = self.client.get(url, params=params)
            except httpx.TransportError:
                if attempt == self.max_retries:
                    raise
                self.sleep(backoff); backoff *= 2
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                ra = r.headers.get("Retry-After", "")
                self.sleep(min(float(ra), 120) if ra.isdigit() else backoff)
                backoff *= 2
                continue
            if r.status_code == 403 and _looks_like_challenge(r):
                raise Blocked(f"bot challenge at {url}")
            return r
        return r

    def get_json(self, url: str, params: dict | None = None):
        r = self.get(url, params)
        r.raise_for_status()
        return r.json()


def _looks_like_challenge(r: httpx.Response) -> bool:
    body = r.text[:3000].lower()
    return any(s in body for s in ("captcha", "cf-chl", "challenge-platform", "datadome",
                                   "access denied", "perimeterx", "akamai"))
