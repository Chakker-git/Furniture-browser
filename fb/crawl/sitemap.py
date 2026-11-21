"""Sitemap discovery: robots.txt Sitemap: lines -> sitemap indexes -> URLs."""
from __future__ import annotations

import gzip
import re
from typing import Iterator

from lxml import etree

from .http import Blocked, PoliteClient

_PRODUCT_HINT = re.compile(
    r"/(p|product|products|produkt|produkte|produkter|artikel|item|dp|vare)/|"
    r"-p-?\d+|/\d{5,}(\.html)?$|\.html$", re.I)
_SKIP = re.compile(r"/(blog|magasin|magazin|inspiration|ratgeber|kategorie|category|"
                   r"collections?|kampagne|brand|marken|stores?|butikker|filialen)/", re.I)


def _parse(content: bytes) -> etree._Element | None:
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    try:
        return etree.fromstring(content, parser=etree.XMLParser(recover=True,
                                                                resolve_entities=False))
    except etree.XMLSyntaxError:
        return None


def iter_sitemap_urls(client: PoliteClient, base_url: str, max_sitemaps: int = 200,
                      sitemap_filter: str | None = None) -> Iterator[str]:
    queue = client.sitemaps_from_robots(base_url) or [base_url.rstrip("/") + "/sitemap.xml"]
    seen: set[str] = set()
    sm_filter = re.compile(sitemap_filter, re.I) if sitemap_filter else None
    while queue and len(seen) < max_sitemaps:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            r = client.get(sm)
        except Blocked:
            continue
        if r.status_code != 200:
            continue
        root = _parse(r.content)
        if root is None:
            continue
        tag = etree.QName(root).localname
        locs = [el.text.strip() for el in root.iter("{*}loc") if el.text]
        if tag == "sitemapindex":
            # product sitemaps first; skip obvious non-product ones
            locs.sort(key=lambda u: 0 if re.search(r"product|produkt|artikel", u, re.I) else 1)
            for loc in locs:
                if sm_filter and not sm_filter.search(loc):
                    continue
                if re.search(r"blog|cms|page|image|video|categor|store|brand", loc, re.I) and \
                        not re.search(r"product|produkt", loc, re.I):
                    continue
                queue.append(loc)
        else:
            yield from locs


def looks_like_product_url(url: str, pattern: str | None = None) -> bool:
    if pattern:
        return re.search(pattern, url, re.I) is not None
    return bool(_PRODUCT_HINT.search(url)) and not _SKIP.search(url)
