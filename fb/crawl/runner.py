from __future__ import annotations

import logging
import sqlite3
import time
from urllib.parse import urlsplit
from typing import Iterable

from .. import db
from ..extract import normalize
from ..models import RawProduct
from .adapters import ADAPTERS, detect_platform
from .http import Blocked, PoliteClient

log = logging.getLogger("fb.crawl")

# Adapters that walk the full catalogue: products missing afterwards are gone.
COMPLETE_PLATFORMS = {"shopify", "woocommerce", "feed"}


def register(conn: sqlite3.Connection, r: dict, platform: str | None = None):
    conn.execute("INSERT INTO retailers(id, name, country, base_url, platform) VALUES (?,?,?,?,?) "
                 "ON CONFLICT(id) DO UPDATE SET name=excluded.name, country=excluded.country, "
                 "base_url=excluded.base_url, platform=COALESCE(excluded.platform, platform)",
                 (r["id"], r["name"], r["country"], r["base_url"], platform))


def ingest(conn: sqlite3.Connection, r: dict, raws: Iterable[RawProduct],
           platform: str = "manual", complete: bool = False) -> dict:
    """Normalize + store a stream of RawProduct, recording a crawl run."""
    register(conn, r, platform)
    started = time.time()
    run_id = conn.execute("INSERT INTO crawl_runs(retailer_id, started, status) VALUES (?,?,?)",
                          (r["id"], started, "running")).lastrowid
    conn.commit()
    n = skipped = errors = 0
    status, message = "ok", ""
    try:
        for raw in raws:
            try:
                p = normalize(raw, r["country"])
                if r.get("furniture_only") and not p.category:
                    skipped += 1
                    continue
                if not p.title or not p.url:
                    skipped += 1
                    continue
                db.upsert(conn, p)
                n += 1
                if n % 200 == 0:
                    conn.commit()
                    log.info("%s: %d products", r["id"], n)
            except Exception as e:  # one bad product must not kill the run
                errors += 1
                log.debug("normalize failed for %s: %s", raw.url, e)
    except Blocked as e:
        status, message = "blocked", str(e)
    except Exception as e:
        status, message = "error", f"{type(e).__name__}: {e}"
        log.exception("crawl of %s failed", r["id"])
    removed = 0
    if status == "ok" and complete and n:
        removed = db.deactivate_unseen(conn, r["id"], started)
    if skipped:
        message = (message + f" skipped={skipped}").strip()
    if removed:
        message = (message + f" deactivated={removed}").strip()
    conn.execute("UPDATE crawl_runs SET finished=?, status=?, products=?, errors=?, message=? "
                 "WHERE id=?", (time.time(), status, n, errors, message, run_id))
    conn.commit()
    return {"retailer": r["id"], "status": status, "products": n, "errors": errors,
            "skipped": skipped, "deactivated": removed, "message": message}


def crawl_retailer(conn: sqlite3.Connection, r: dict, client: PoliteClient | None = None) -> dict:
    own = client is None
    client = client or PoliteClient(delay=r.get("delay_seconds", 2.0))
    try:
        platform = r.get("platform", "auto")
        if platform == "auto":
            platform = "feed" if r.get("feed_url") else detect_platform(client, r)
        log.info("%s: platform=%s", r["id"], platform)
        return ingest(conn, r, ADAPTERS[platform](client, r), platform,
                      complete=platform in COMPLETE_PLATFORMS)
    finally:
        if own:
            client.close()


def probe(r: dict, client: PoliteClient | None = None) -> dict:
    """Cheap reconnaissance: robots.txt, sitemaps, detected platform. No catalogue crawl."""
    own = client is None
    client = client or PoliteClient(delay=r.get("delay_seconds", 2.0))
    try:
        rp = client.robots(r["base_url"])
        netloc = urlsplit(r["base_url"]).netloc
        robots = client.robots_status.get(netloc)
        if not client.allowed(r["base_url"]):
            why = {403: "refuses bots (403)", 401: "refuses bots (401)",
                   429: "rate-limited (429)"}.get(robots, f"robots.txt disallows ({robots})")
            return {"id": r["id"], "status": "blocked", "robots": robots, "reason": why}
        sitemaps = list(rp.site_maps() or []) if rp else []
        return {"id": r["id"], "status": "ok", "robots": robots,
                "platform": detect_platform(client, r), "sitemaps": sitemaps[:5]}
    except Exception as e:
        return {"id": r["id"], "error": f"{type(e).__name__}: {e}"}
    finally:
        if own:
            client.close()
