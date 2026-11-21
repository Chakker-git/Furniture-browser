"""CLI:  python -m fb <command>

  probe   [--retailer ID]          robots.txt / sitemap / platform detection only
  crawl   [--retailer ID] [--all]  crawl enabled retailers (or one, or --all incl. disabled)
  ingest  FILE --retailer ID [--format google|csv]   load a local product feed file
  demo                             load the synthetic demo catalogue
  serve   [--host H] [--port P]    run the web app
  stats                            products per retailer + last crawl status
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import db, registry
from .crawl import adapters, runner


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fb")
    ap.add_argument("--db", default=os.environ.get("FB_DB", "data/furniture.db"))
    ap.add_argument("--retailers", default=str(registry.DEFAULT_PATH))
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("probe", "crawl"):
        p = sub.add_parser(name)
        p.add_argument("--retailer", action="append")
        p.add_argument("--all", action="store_true", help="include enabled=false retailers")
        p.add_argument("--max-pages", type=int)
    p = sub.add_parser("ingest")
    p.add_argument("file")
    p.add_argument("--retailer", required=True)
    p.add_argument("--format", choices=["google", "csv"], default="google")
    sub.add_parser("demo")
    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    sub.add_parser("stats")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not a.verbose:  # one line per HTTP request is noise unless debugging
        logging.getLogger("httpx").setLevel(logging.WARNING)

    if a.cmd == "serve":
        import uvicorn
        os.environ["FB_DB"] = a.db
        from .api import create_app
        uvicorn.run(create_app(a.db), host=a.host, port=a.port)
        return

    conn = db.connect(a.db)
    if a.cmd == "demo":
        from . import demo
        catalogue = demo.generate()
        for r in demo.RETAILERS:
            print(json.dumps(runner.ingest(conn, r, catalogue[r["id"]], "demo")))
        return
    if a.cmd == "stats":
        print(f"{'retailer':<24} cc  {'products':>8}  status    % with: size color cat price img")
        for r in db.retailer_stats(conn):
            lr, cov = r["last_run"] or {}, r["coverage"] or {}
            pct = "  ".join(f"{int(cov.get(k) or 0):>4}" for k in
                            ("size", "color", "category", "price", "image"))
            print(f"{r['id']:<24} {r['country']}  {r['products']:>8}  "
                  f"{lr.get('status', '-'):<8}  {pct}  {lr.get('message') or ''}")
        return

    retailers = registry.load(a.retailers)
    by_id = {r["id"]: r for r in retailers}
    if a.cmd == "ingest":
        r = by_id.get(a.retailer) or sys.exit(f"unknown retailer {a.retailer}")
        content = Path(a.file).read_bytes()
        raws = (adapters.parse_csv_feed(content.decode("utf-8-sig"), r) if a.format == "csv"
                else adapters.parse_google_feed(content, r))
        print(json.dumps(runner.ingest(conn, r, raws, "feed", complete=True)))
        return

    selected = [by_id[i] for i in a.retailer] if a.retailer else \
        [r for r in retailers if a.all or r.get("enabled", True)]
    for r in selected:
        if a.max_pages:
            r["max_pages"] = a.max_pages
        if a.cmd == "probe":
            print(json.dumps(runner.probe(r)))
        else:
            print(json.dumps(runner.crawl_retailer(conn, r)))


if __name__ == "__main__":
    main()
