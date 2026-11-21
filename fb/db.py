"""Storage + search on SQLite FTS5.

Why SQLite: zero-ops, handles a few million rows on one box, and the whole
search layer is behind `search()` so it can move to Meilisearch/OpenSearch
when facet counts over millions of rows get slow.

Cross-lingual trick: at index time every product gets synthetic concept
tokens (e.g. 'zzcatsofa', 'zzcolgrey') derived from the EN/DA/DE lexicon.
At query time words are mapped to the same tokens, so "grey sofa",
"grå sofa" and "Sofa grau" all hit the same rows.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from .currency import from_eur
from .lexicon import CATEGORY_IMPLIES, CATEGORY_PARENTS, MATCHERS, concept_token
from .models import Product
from .textnorm import fold, tokenize

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY,
  retailer_id TEXT NOT NULL, country TEXT NOT NULL, external_id TEXT NOT NULL,
  group_key TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
  brand TEXT, category TEXT, attributes TEXT, colors TEXT, color_raw TEXT, materials TEXT,
  width_cm REAL, depth_cm REAL, height_cm REAL, diameter_cm REAL, seats REAL,
  price REAL, currency TEXT, price_eur REAL, image_url TEXT, gtin TEXT, sku TEXT,
  in_stock INTEGER, first_seen REAL, last_seen REAL, active INTEGER DEFAULT 1,
  UNIQUE(retailer_id, external_id)
);
CREATE INDEX IF NOT EXISTS ix_p_cat ON products(category);
CREATE INDEX IF NOT EXISTS ix_p_price ON products(price_eur);
CREATE INDEX IF NOT EXISTS ix_p_gtin ON products(gtin);
CREATE INDEX IF NOT EXISTS ix_p_group ON products(retailer_id, group_key);
CREATE TABLE IF NOT EXISTS product_colors (product_id INTEGER, color TEXT,
  PRIMARY KEY(product_id, color));
CREATE INDEX IF NOT EXISTS ix_pc_color ON product_colors(color);
CREATE TABLE IF NOT EXISTS product_materials (product_id INTEGER, material TEXT,
  PRIMARY KEY(product_id, material));
CREATE TABLE IF NOT EXISTS price_history (product_id INTEGER, ts REAL, price REAL,
  currency TEXT);
CREATE TABLE IF NOT EXISTS retailers (id TEXT PRIMARY KEY, name TEXT, country TEXT,
  base_url TEXT, platform TEXT);
CREATE TABLE IF NOT EXISTS crawl_runs (id INTEGER PRIMARY KEY, retailer_id TEXT,
  started REAL, finished REAL, status TEXT, products INTEGER, errors INTEGER,
  message TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
  title, body, concepts, brand, tokenize = "unicode61");
"""


def connect(path: str | Path = "data/furniture.db") -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def _concepts_for(p: Product) -> str:
    toks = []
    if p.category:
        toks.append(concept_token("category", p.category))
        toks += [concept_token("category", c) for c in CATEGORY_PARENTS.get(p.category, [])]
    toks += [concept_token("attribute", a) for a in p.attributes]
    toks += [concept_token("color", c) for c in p.colors]
    toks += [concept_token("material", m) for m in p.materials]
    return " ".join(toks)


def upsert(conn: sqlite3.Connection, p: Product) -> int:
    now = time.time()
    d = asdict(p)
    d["attributes"] = ",".join(p.attributes)
    d["colors"] = ",".join(p.colors)
    d["materials"] = ",".join(p.materials)
    d["in_stock"] = None if p.in_stock is None else int(p.in_stock)
    prev = conn.execute("SELECT id, price FROM products WHERE retailer_id=? AND external_id=?",
                        (p.retailer_id, p.external_id)).fetchone()
    cols = list(d.keys())
    if prev:
        pid = prev["id"]
        conn.execute(f"UPDATE products SET {', '.join(c + '=?' for c in cols)}, "
                     "last_seen=?, active=1 WHERE id=?", [d[c] for c in cols] + [now, pid])
        if p.price is not None and prev["price"] != p.price:
            conn.execute("INSERT INTO price_history VALUES (?,?,?,?)",
                         (pid, now, p.price, p.currency))
    else:
        cur = conn.execute(
            f"INSERT INTO products ({', '.join(cols)}, first_seen, last_seen) "
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)", [d[c] for c in cols] + [now, now])
        pid = cur.lastrowid
        if p.price is not None:
            conn.execute("INSERT INTO price_history VALUES (?,?,?,?)",
                         (pid, now, p.price, p.currency))
    conn.execute("DELETE FROM product_colors WHERE product_id=?", (pid,))
    conn.executemany("INSERT OR IGNORE INTO product_colors VALUES (?,?)",
                     [(pid, c) for c in p.colors])
    conn.execute("DELETE FROM product_materials WHERE product_id=?", (pid,))
    conn.executemany("INSERT OR IGNORE INTO product_materials VALUES (?,?)",
                     [(pid, m) for m in p.materials])
    conn.execute("DELETE FROM products_fts WHERE rowid=?", (pid,))
    conn.execute("INSERT INTO products_fts(rowid, title, body, concepts, brand) "
                 "VALUES (?,?,?,?,?)",
                 (pid, " ".join(tokenize(p.title)), " ".join(tokenize(p.description[:4000])),
                  _concepts_for(p), " ".join(tokenize(p.brand or ""))))
    return pid


def deactivate_unseen(conn: sqlite3.Connection, retailer_id: str, since: float) -> int:
    """Products not seen in a *complete* crawl are hidden, not deleted (keeps history)."""
    cur = conn.execute("UPDATE products SET active=0 WHERE retailer_id=? AND last_seen<?",
                       (retailer_id, since))
    return cur.rowcount


# ---------------------------------------------------------------------------- search

_STOP = {fold(w) for w in
         "a an the and or with for of in on to i og med til af en et den det på "
         "der die das und mit für fuer von im am zu ein eine einen".split()}


def build_match(q: str) -> tuple[str | None, dict[str, list[str]]]:
    """FTS5 MATCH expression + concepts recognised in the query (for the UI)."""
    toks = [t for t in tokenize(q) if t not in _STOP]
    if not toks:
        return None, {}
    recognised: dict[str, list[str]] = {}
    spans: dict[int, dict[str, tuple[int, str]]] = {}   # pos -> group -> (len, concept)
    for group, matcher in MATCHERS.items():
        for pos, n, cid in matcher.find_spans(toks):
            spans.setdefault(pos, {})[group] = (n, cid)
    clauses: list[str] = []
    i = 0
    while i < len(toks):
        groups = spans.get(i, {})
        # Most specific reading wins: "spisebord" is a dining *table*, not any dining
        # item; "oak" is oak *material*, not anything wood-coloured.
        extra: list[tuple[str, str]] = []
        if "category" in groups:
            cat = groups["category"][1]
            att = groups.get("attribute")
            # "havestol" = chair AND outdoor; "spisebord" = dining table only
            if att and att[0] == 1 and att[1] not in CATEGORY_IMPLIES.get(cat, set()):
                extra.append(("attribute", att[1]))
            groups = {"category": groups["category"]}
        elif "material" in groups:
            groups = {"material": groups["material"]}
        n = max((g[0] for g in groups.values()), default=1)
        words = toks[i:i + n]
        if n > 1:
            alts = ['"' + " ".join(words) + '"']
        elif groups or len(words[0]) < 3:
            alts = [f'"{words[0]}"']  # known word: concept covers compounds/inflections
        else:
            alts = [f'"{words[0]}"*']
        for group, (_, cid) in sorted(groups.items()):
            alts.append(f"concepts:{concept_token(group, cid)}")
            recognised.setdefault(group, [])
            if cid not in recognised[group]:
                recognised[group].append(cid)
        clauses.append("(" + " OR ".join(alts) + ")")
        for group, cid in extra:
            clauses.append(f"concepts:{concept_token(group, cid)}")
            recognised.setdefault(group, [])
            if cid not in recognised[group]:
                recognised[group].append(cid)
        i += n
    return " AND ".join(clauses), recognised


FACETS = ("country", "retailer_id", "category", "color", "material")


def _where(f: dict, exclude: str | None = None) -> tuple[list[str], list]:
    w, a = ["p.active=1"], []

    def multi(col, key):
        vals = f.get(key) or []
        if vals and exclude != key:
            w.append(f"{col} IN ({','.join('?' * len(vals))})")
            a.extend(vals)

    multi("p.country", "country")
    multi("p.retailer_id", "retailer_id")
    multi("p.category", "category")
    if f.get("color") and exclude != "color":
        w.append(f"p.id IN (SELECT product_id FROM product_colors WHERE color IN "
                 f"({','.join('?' * len(f['color']))}))")
        a.extend(f["color"])
    if f.get("material") and exclude != "material":
        w.append(f"p.id IN (SELECT product_id FROM product_materials WHERE material IN "
                 f"({','.join('?' * len(f['material']))}))")
        a.extend(f["material"])
    for col, lo, hi in (("width_cm", "wmin", "wmax"), ("depth_cm", "dmin", "dmax"),
                        ("height_cm", "hmin", "hmax"), ("price_eur", "pmin_eur", "pmax_eur"),
                        ("seats", "seats_min", "seats_max")):
        if f.get(lo) is not None:
            w.append(f"p.{col} >= ?"); a.append(f[lo])
        if f.get(hi) is not None:
            w.append(f"p.{col} <= ?"); a.append(f[hi])
    if f.get("in_stock"):
        w.append("COALESCE(p.in_stock,1)=1")
    if f.get("has_dimensions"):
        w.append("p.width_cm IS NOT NULL")
    return w, a


def search(conn: sqlite3.Connection, q: str = "", filters: dict | None = None,
           sort: str = "relevance", page: int = 1, per_page: int = 24,
           currency: str = "EUR") -> dict:
    f = dict(filters or {})
    match, recognised = build_match(q)

    def base(exclude=None):
        w, a = _where(f, exclude)
        frm = "products p"
        if match:
            frm = "products_fts JOIN products p ON p.id = products_fts.rowid"
            w.insert(0, "products_fts MATCH ?")
            a.insert(0, match)
        return frm, w, a

    frm, w, a = base()
    where = " AND ".join(w)
    score = "bm25(products_fts, 10.0, 1.0, 6.0, 3.0)" if match else "0"
    # Matching variants, ranked inside their product group (cheapest first).
    # (bm25() must be computed in its own subquery; FTS5 refuses it next to a window fn)
    matched = (f"SELECT *, ROW_NUMBER() OVER (PARTITION BY retailer_id, group_key "
               f"ORDER BY price_eur IS NULL, price_eur) AS rn FROM ("
               f"SELECT p.id, p.retailer_id, p.group_key, p.price_eur, p.first_seen, "
               f"p.last_seen, p.width_cm, {score} AS score FROM {frm} WHERE {where} "
               f"LIMIT -1)")
    order = {
        "price_asc": "min_eur IS NULL, min_eur ASC",
        "price_desc": "max_eur IS NULL, max_eur DESC",
        "newest": "first_seen DESC",
        "width_asc": "min_w IS NULL, min_w ASC",
    }.get(sort) or ("score ASC, min_eur ASC" if match else "last_seen DESC")
    # One result per product group: variants (colours/sizes) collapse into one card.
    total = conn.execute(f"SELECT COUNT(*) FROM (SELECT 1 FROM ({matched}) "
                         f"GROUP BY retailer_id, group_key)", a).fetchone()[0]
    rows = conn.execute(
        f"SELECT retailer_id, group_key, MIN(price_eur) AS min_eur, MAX(price_eur) AS max_eur, "
        f"MIN(score) AS score, MAX(first_seen) AS first_seen, MAX(last_seen) AS last_seen, "
        f"MIN(width_cm) AS min_w, MAX(CASE WHEN rn=1 THEN id END) AS rep_id "
        f"FROM ({matched}) GROUP BY retailer_id, group_key "
        f"ORDER BY {order} LIMIT ? OFFSET ?", a + [per_page, (page - 1) * per_page]).fetchall()
    items = []
    for r in rows:
        p = dict(conn.execute("SELECT * FROM products WHERE id=?", (r["rep_id"],)).fetchone())
        variants = conn.execute(
            "SELECT colors FROM products WHERE retailer_id=? AND group_key=? AND active=1",
            (r["retailer_id"], r["group_key"])).fetchall()
        colors = sorted({c for v in variants for c in (v["colors"] or "").split(",") if c})
        items.append(_present(p, currency, group_colors=colors, n_variants=len(variants),
                              min_eur=r["min_eur"], max_eur=r["max_eur"]))
    facets = {}
    for facet in FACETS:
        frm_f, w_f, a_f = base(exclude=facet)
        wh = " AND ".join(w_f)
        if facet == "color":
            sql = (f"SELECT pc.color AS v, COUNT(DISTINCT p.id) AS n FROM {frm_f} "
                   f"JOIN product_colors pc ON pc.product_id=p.id WHERE {wh} GROUP BY pc.color")
        elif facet == "material":
            sql = (f"SELECT pm.material AS v, COUNT(DISTINCT p.id) AS n FROM {frm_f} "
                   f"JOIN product_materials pm ON pm.product_id=p.id WHERE {wh} "
                   f"GROUP BY pm.material")
        else:
            sql = (f"SELECT p.{facet} AS v, COUNT(*) AS n FROM {frm_f} WHERE {wh} "
                   f"AND p.{facet} IS NOT NULL GROUP BY p.{facet}")
        facets[facet] = {r["v"]: r["n"] for r in conn.execute(sql, a_f)}
    return {"total": total, "page": page, "per_page": per_page, "items": items,
            "facets": facets, "recognised": recognised, "match": match}


def _present(p: dict, currency: str, **extra) -> dict:
    p = dict(p)
    for k in ("attributes", "colors", "materials"):
        p[k] = [x for x in (p.get(k) or "").split(",") if x]
    p["in_stock"] = None if p["in_stock"] is None else bool(p["in_stock"])
    p["display_currency"] = currency.upper()
    if p.get("currency") == currency.upper():
        p["display_price"] = p["price"]
    else:
        p["display_price"] = from_eur(p.get("price_eur"), currency)
    if "min_eur" in extra:
        extra["display_min"] = from_eur(extra.pop("min_eur"), currency)
        extra["display_max"] = from_eur(extra.pop("max_eur"), currency)
    p.pop("description", None)
    p.update(extra)
    return p


def product_detail(conn: sqlite3.Connection, pid: int, currency: str = "EUR") -> dict | None:
    row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not row:
        return None
    p = dict(row)
    desc = p.get("description")
    out = _present(p, currency)
    out["description"] = desc
    out["variants"] = [_present(dict(v), currency) for v in conn.execute(
        "SELECT * FROM products WHERE retailer_id=? AND group_key=? AND active=1 "
        "ORDER BY price_eur", (p["retailer_id"], p["group_key"]))]
    # Same physical product at other retailers (matched on GTIN/EAN).
    out["other_offers"] = [_present(dict(v), currency) for v in conn.execute(
        "SELECT * FROM products WHERE gtin=? AND gtin IS NOT NULL AND retailer_id<>? "
        "AND active=1 ORDER BY price_eur", (p["gtin"], p["retailer_id"]))] if p["gtin"] else []
    out["price_history"] = [dict(h) for h in conn.execute(
        "SELECT ts, price, currency FROM price_history WHERE product_id=? ORDER BY ts", (pid,))]
    return out


def retailer_stats(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
      SELECT r.*, (SELECT COUNT(*) FROM products p WHERE p.retailer_id=r.id AND p.active=1) AS products,
        (SELECT json_object(
           'size', ROUND(100.0 * AVG(p.width_cm IS NOT NULL)),
           'color', ROUND(100.0 * AVG(COALESCE(p.colors, '') <> '')),
           'category', ROUND(100.0 * AVG(p.category IS NOT NULL)),
           'price', ROUND(100.0 * AVG(p.price IS NOT NULL)),
           'image', ROUND(100.0 * AVG(p.image_url IS NOT NULL)))
         FROM products p WHERE p.retailer_id=r.id AND p.active=1) AS coverage,
        (SELECT json_object('status', status, 'finished', finished, 'products', products,
           'errors', errors, 'message', message) FROM crawl_runs c WHERE c.retailer_id=r.id
           ORDER BY started DESC LIMIT 1) AS last_run
      FROM retailers r ORDER BY r.country, r.name""").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["last_run"] = json.loads(d["last_run"]) if d["last_run"] else None
        d["coverage"] = json.loads(d["coverage"]) if d["coverage"] else None
        out.append(d)
    return out
