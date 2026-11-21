"""Platform adapters. Each yields RawProduct for one retailer.

Preference order (most structured / least load on the retailer first):
  feed        - affiliate / Google Merchant feed (legal, complete, cheap)
  shopify     - public /products.json
  woocommerce - public Store API /wp-json/wc/store/v1/products
  sitemap     - sitemap.xml -> product pages -> schema.org JSON-LD (generic fallback)
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Iterator
from urllib.parse import urljoin

from lxml import etree
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..models import RawProduct
from .http import Blocked, PoliteClient
from .sitemap import iter_sitemap_urls, looks_like_product_url

COLOR_OPT = re.compile(r"farve|farbe|colou?r|stof|bezug|fabric|finish|udførelse|ausführung", re.I)
SIZE_OPT = re.compile(r"størrelse|grösse|größe|groesse|size|mål|maße|masse|dimension", re.I)


def _float(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        s = str(v).strip().replace(" ", "").replace(" ", "")
        if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):   # 1.299,00 (DE/DK)
            s = s.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d+,\d{1,2}", s):               # 1299,00
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
        s = re.sub(r"[^\d.]", "", s)
        return float(s) if s else None
    except ValueError:
        return None


# ----------------------------------------------------------------------------- Shopify

def shopify(client: PoliteClient, r: dict) -> Iterator[RawProduct]:
    base = r["base_url"].rstrip("/")
    page = 1
    while page <= r.get("max_pages", 400):
        data = client.get_json(f"{base}/products.json", {"limit": 250, "page": page})
        products = data.get("products") or []
        if not products:
            return
        for p in products:
            yield from _shopify_product(base, r, p)
        page += 1


def _shopify_product(base: str, r: dict, p: dict) -> Iterator[RawProduct]:
    options = [o.get("name", "") for o in p.get("options") or []]
    color_idx = next((i for i, n in enumerate(options) if COLOR_OPT.search(n)), None)
    size_idx = next((i for i, n in enumerate(options) if SIZE_OPT.search(n)), None)
    tags = p.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    images = p.get("images") or []
    default_img = images[0]["src"] if images else None
    for v in p.get("variants") or [{}]:
        opt = [v.get("option1"), v.get("option2"), v.get("option3")]
        title = p.get("title", "")
        vt = v.get("title")
        if vt and vt.lower() != "default title":
            title = f"{title} – {vt}"
        img = (v.get("featured_image") or {}).get("src") or default_img
        yield RawProduct(
            retailer_id=r["id"], external_id=str(v.get("id") or p["id"]),
            url=f"{base}/products/{p['handle']}" + (f"?variant={v['id']}" if v.get("id") else ""),
            title=title, description=p.get("body_html") or "",
            price=_float(v.get("price")), currency=r.get("currency"),
            image_url=img, brand=p.get("vendor"), gtin=v.get("barcode"), sku=v.get("sku"),
            in_stock=v.get("available"), group_key=str(p["id"]),
            source_category=p.get("product_type"), tags=tags,
            color_raw=opt[color_idx] if color_idx is not None else None,
            dimensions_raw=opt[size_idx] if size_idx is not None else None,
        )


# ------------------------------------------------------------------------- WooCommerce

def woocommerce(client: PoliteClient, r: dict) -> Iterator[RawProduct]:
    base = r["base_url"].rstrip("/")
    page = 1
    while page <= r.get("max_pages", 400):
        resp = client.get(f"{base}/wp-json/wc/store/v1/products",
                          {"per_page": 100, "page": page})
        if resp.status_code != 200:
            return
        items = resp.json()
        if not items:
            return
        for p in items:
            prices = p.get("prices") or {}
            minor = int(prices.get("currency_minor_unit", 2) or 0)
            price = _float(prices.get("price"))
            if price is not None:
                price = price / (10 ** minor)
            attrs = {a.get("name", ""): [t.get("name") for t in a.get("terms") or []]
                     for a in p.get("attributes") or []}
            color = next((", ".join(v) for k, v in attrs.items() if COLOR_OPT.search(k)), None)
            mat = next((", ".join(v) for k, v in attrs.items()
                        if re.search(r"materiale?|material", k, re.I)), None)
            size = next((", ".join(v) for k, v in attrs.items() if SIZE_OPT.search(k)), None)
            imgs = p.get("images") or []
            yield RawProduct(
                retailer_id=r["id"], external_id=str(p["id"]), url=p.get("permalink", ""),
                title=_text(p.get("name")),
                description=(p.get("short_description") or "") + " " + (p.get("description") or ""),
                price=price, currency=prices.get("currency_code") or r.get("currency"),
                image_url=imgs[0].get("src") if imgs else None, sku=p.get("sku"),
                in_stock=p.get("is_in_stock"),
                source_category=" / ".join(c.get("name", "") for c in p.get("categories") or []),
                color_raw=color, material_raw=mat, dimensions_raw=size)
        page += 1


def _text(s):
    return HTMLParser(s).text(strip=True) if s and "<" in s else (s or "")


# ---------------------------------------------------------------- Sitemap + JSON-LD

def sitemap_jsonld(client: PoliteClient, r: dict) -> Iterator[RawProduct]:
    limit = r.get("max_pages", 5000)
    n = 0
    for url in iter_sitemap_urls(client, r["base_url"], sitemap_filter=r.get("sitemap_filter")):
        if not looks_like_product_url(url, r.get("product_url_pattern")):
            continue
        if n >= limit:
            return
        n += 1
        try:
            resp = client.get(url)
        except Blocked:
            continue
        if resp.status_code != 200 or "html" not in resp.headers.get("content-type", "html"):
            continue
        yield from parse_product_page(resp.text, str(resp.url), r)


def _walk(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _walk(x)
    elif isinstance(obj, dict):
        yield obj
        for k in ("@graph", "mainEntity", "itemListElement"):
            if k in obj:
                yield from _walk(obj[k])


def _types(o: dict) -> set[str]:
    t = o.get("@type", [])
    return set(t if isinstance(t, list) else [t])


def _qv_cm(v) -> float | None:
    if isinstance(v, dict):
        val = _float(v.get("value"))
        unit = (v.get("unitCode") or v.get("unitText") or "CMT").upper()
    else:
        m = re.match(r"\s*([\d.,]+)\s*([a-zA-Z]*)", str(v or ""))
        if not m:
            return None
        val, unit = _float(m.group(1)), (m.group(2) or "CM").upper()
    if val is None:
        return None
    factor = {"MMT": 0.1, "MM": 0.1, "MTR": 100, "M": 100}.get(unit, 1)
    cm = val * factor
    return round(cm, 1) if 1 <= cm <= 600 else None


def _first(v):
    return v[0] if isinstance(v, list) and v else v


def _image(v):
    v = _first(v)
    return v.get("url") or v.get("contentUrl") if isinstance(v, dict) else v


def _brand(v):
    v = _first(v)
    return v.get("name") if isinstance(v, dict) else v


def _offer(o) -> tuple[float | None, str | None, bool | None]:
    offers = o.get("offers")
    offers = _first(offers) if isinstance(offers, list) else offers
    if not isinstance(offers, dict):
        return None, None, None
    if "offers" in offers and isinstance(offers["offers"], list):  # AggregateOffer
        offers = {**offers, **(_first(offers["offers"]) or {})}
    price = _float(offers.get("price") or offers.get("lowPrice") or
                   (offers.get("priceSpecification") or {}).get("price"))
    cur = offers.get("priceCurrency") or (offers.get("priceSpecification") or {}).get(
        "priceCurrency")
    av = str(offers.get("availability") or "")
    stock = None if not av else ("InStock" in av or "LimitedAvailability" in av
                                 or "PreOrder" in av)
    return price, cur, stock


def parse_product_page(html: str, url: str, r: dict) -> Iterator[RawProduct]:
    tree = HTMLParser(html)
    blobs = []
    for s in tree.css('script[type="application/ld+json"]'):
        try:
            blobs.append(json.loads(s.text(strip=False)))
        except (json.JSONDecodeError, ValueError):
            continue
    objs = [o for b in blobs for o in _walk(b)]
    crumbs = []
    for o in objs:
        if "BreadcrumbList" in _types(o):
            for it in o.get("itemListElement") or []:
                item = it.get("item")
                name = it.get("name") or (item.get("name") if isinstance(item, dict) else None)
                if name:
                    crumbs.append(name)
    source_cat = " / ".join(crumbs) or None
    found = False
    for o in objs:
        t = _types(o)
        if "ProductGroup" in t:
            group = str(o.get("productGroupID") or o.get("sku") or url)
            for v in o.get("hasVariant") or []:
                merged = {**{k: o[k] for k in o if k not in ("hasVariant", "@type")}, **v}
                yield _from_ld(merged, url, r, group, source_cat)
                found = True
        elif "Product" in t and not found:
            yield _from_ld(o, url, r, None, source_cat)
            found = True
    if not found:  # OpenGraph fallback
        meta = {m.attributes.get("property") or m.attributes.get("name"): m.attributes.get(
            "content") for m in tree.css("meta")}
        if meta.get("og:type", "").startswith("product") or meta.get("product:price:amount"):
            yield RawProduct(
                retailer_id=r["id"], external_id=url, url=url,
                title=meta.get("og:title") or (tree.css_first("title").text() if
                                               tree.css_first("title") else url),
                description=meta.get("og:description") or "",
                price=_float(meta.get("product:price:amount")),
                currency=meta.get("product:price:currency") or r.get("currency"),
                image_url=meta.get("og:image"), source_category=source_cat)


def _from_ld(o: dict, url: str, r: dict, group: str | None, source_cat) -> RawProduct:
    price, cur, stock = _offer(o)
    gtin = next((o.get(k) for k in ("gtin13", "gtin", "gtin14", "gtin12", "gtin8", "ean")
                 if o.get(k)), None)
    purl = o.get("url") or url
    color = o.get("color")
    material = o.get("material")
    if isinstance(material, list):
        material = ", ".join(map(str, material))
    return RawProduct(
        retailer_id=r["id"], external_id=str(o.get("sku") or o.get("productID") or purl),
        url=urljoin(url, purl) if isinstance(purl, str) else url,
        title=str(o.get("name") or ""), description=str(o.get("description") or ""),
        price=price, currency=cur or r.get("currency"), image_url=_image(o.get("image")),
        brand=_brand(o.get("brand")), gtin=str(gtin) if gtin else None, sku=o.get("sku"),
        in_stock=stock, group_key=group,
        source_category=source_cat or (o.get("category") if isinstance(o.get("category"),
                                                                         str) else None),
        color_raw=color if isinstance(color, str) else None,
        material_raw=material if isinstance(material, str) else None,
        width_cm=_qv_cm(o.get("width")), depth_cm=_qv_cm(o.get("depth")),
        height_cm=_qv_cm(o.get("height")),
    )


# -------------------------------------------------------------------------- Feeds

G = "{http://base.google.com/ns/1.0}"


def parse_google_feed(content: bytes, r: dict) -> Iterator[RawProduct]:
    """Google Merchant Center RSS/Atom feed (what most shops already produce)."""
    root = etree.fromstring(content, parser=etree.XMLParser(recover=True, huge_tree=True,
                                                            resolve_entities=False))
    for item in root.iter("item", "{http://www.w3.org/2005/Atom}entry"):
        def g(name):
            el = item.find(G + name)
            if el is None:
                el = item.find(name)
            return el.text.strip() if el is not None and el.text else None

        price_s = g("sale_price") or g("price") or ""
        m = re.match(r"\s*([\d.,]+)\s*([A-Z]{3})?", price_s)
        dims = " ".join(f"{lab} {g(k)}" for lab, k in (("B", "product_width"),
                                                         ("D", "product_length"),
                                                         ("H", "product_height")) if g(k))
        yield RawProduct(
            retailer_id=r["id"], external_id=g("id") or g("link"), url=g("link") or "",
            title=g("title") or "", description=g("description") or "",
            price=_float(m.group(1)) if m else None,
            currency=(m.group(2) if m and m.group(2) else r.get("currency")),
            image_url=g("image_link"), brand=g("brand"), gtin=g("gtin"), sku=g("mpn"),
            in_stock=(g("availability") or "in stock").replace("_", " ") == "in stock",
            group_key=g("item_group_id"),
            source_category=g("product_type") or g("google_product_category"),
            color_raw=g("color"), material_raw=g("material"),
            dimensions_raw=" ".join(filter(None, [dims, g("size")])) or None)


CSV_ALIASES = {
    "external_id": ["aw_product_id", "id", "product_id", "sku", "merchant_product_id"],
    "title": ["product_name", "title", "name"],
    "url": ["aw_deep_link", "merchant_deep_link", "deeplink", "link", "url", "product_url"],
    "description": ["description", "product_short_description", "long_description"],
    "price": ["search_price", "sale_price", "price", "store_price"],
    "currency": ["currency"],
    "image_url": ["merchant_image_url", "aw_image_url", "image_url", "image_link", "imageurl"],
    "brand": ["brand_name", "brand"],
    "gtin": ["ean", "gtin", "product_gtin", "upc"],
    "source_category": ["merchant_category", "category_name", "product_type", "category"],
    "color_raw": ["colour", "color", "farve", "farbe"],
    "material_raw": ["material", "materiale"],
    "dimensions_raw": ["dimensions", "size", "maal", "masse"],
    "group_key": ["item_group_id", "parent_product_id"],
}


def parse_csv_feed(text: str, r: dict) -> Iterator[RawProduct]:
    """Affiliate network CSV (Awin / Adtraction / Partner-ads style)."""
    sample = text[:5000]
    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|") if sample else csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    cols = {c.lower().strip(): c for c in reader.fieldnames or []}
    mapping = {field: next((cols[a] for a in aliases if a in cols), None)
               for field, aliases in CSV_ALIASES.items()}
    mapping.update(r.get("csv_columns") or {})
    for row in reader:
        def v(field):
            col = mapping.get(field)
            return (row.get(col) or "").strip() or None if col else None
        if not v("title") or not v("url"):
            continue
        yield RawProduct(
            retailer_id=r["id"], external_id=v("external_id") or v("url"), url=v("url"),
            title=v("title"), description=v("description") or "", price=_float(v("price")),
            currency=v("currency") or r.get("currency"), image_url=v("image_url"),
            brand=v("brand"), gtin=v("gtin"), source_category=v("source_category"),
            color_raw=v("color_raw"), material_raw=v("material_raw"),
            dimensions_raw=v("dimensions_raw"), group_key=v("group_key"))


def feed(client: PoliteClient, r: dict) -> Iterator[RawProduct]:
    resp = client.get(r["feed_url"])
    resp.raise_for_status()
    if r.get("feed_format", "google") == "csv":
        yield from parse_csv_feed(resp.text, r)
    else:
        yield from parse_google_feed(resp.content, r)


# ------------------------------------------------------------------------- detect

def detect_platform(client: PoliteClient, r: dict) -> str:
    base = r["base_url"].rstrip("/")
    try:
        resp = client.get(f"{base}/products.json", {"limit": 1})
        if resp.status_code == 200 and "products" in resp.text[:200]:
            resp.json()
            return "shopify"
    except (Blocked, ValueError, Exception):
        pass
    try:
        resp = client.get(f"{base}/wp-json/wc/store/v1/products", {"per_page": 1})
        if resp.status_code == 200 and resp.text.lstrip().startswith("["):
            return "woocommerce"
    except (Blocked, Exception):
        pass
    return "sitemap"


ADAPTERS = {"shopify": shopify, "woocommerce": woocommerce, "sitemap": sitemap_jsonld,
            "feed": feed}
