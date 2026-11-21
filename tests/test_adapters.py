import json

import httpx
import pytest

from fb import db
from fb.crawl import adapters, runner
from fb.crawl.http import Blocked, PoliteClient

R = {"id": "t", "name": "T", "country": "DK", "base_url": "https://shop.test", "currency": "DKK",
     "max_pages": 50}

SHOPIFY = {"products": [{
    "id": 1, "title": "Aarhus 3-pers. sofa", "handle": "aarhus-sofa", "vendor": "Nordic",
    "body_html": "<p>Mål: B 210 x D 90 x H 80 cm</p>", "product_type": "Sofaer",
    "tags": ["stue", "bouclé"],
    "options": [{"name": "Farve"}, {"name": "Ben"}],
    "images": [{"src": "https://cdn.test/a.jpg"}],
    "variants": [
        {"id": 11, "title": "Grå / Eg", "option1": "Grå", "option2": "Eg", "price": "7999.00",
         "available": True, "sku": "A-G"},
        {"id": 12, "title": "Mosgrøn / Eg", "option1": "Mosgrøn", "option2": "Eg",
         "price": "8499.00", "available": False, "sku": "A-M"}]}]}

PRODUCT_PAGE = """<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
 {"@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Möbel"},
   {"@type":"ListItem","position":2,"item":{"name":"Esstische"}}]},
 {"@type":"Product","name":"Esstisch Lund Eiche massiv","sku":"L-1","gtin13":"5701234567890",
  "brand":{"@type":"Brand","name":"Lund"},"image":["https://cdn.test/l.jpg"],"color":"Natur",
  "material":"Eiche","width":{"@type":"QuantitativeValue","value":1800,"unitCode":"MMT"},
  "depth":{"value":90,"unitCode":"CMT"},"height":"75 cm",
  "offers":{"@type":"Offer","price":"1.299,00","priceCurrency":"EUR",
            "availability":"https://schema.org/InStock"}}]}
</script></head><body></body></html>"""

GROUP_PAGE = """<script type="application/ld+json">{"@type":"ProductGroup","productGroupID":"G1",
"name":"Sessel Kiel","description":"B 80 x T 85 x H 95 cm","hasVariant":[
 {"@type":"Product","sku":"K-B","name":"Sessel Kiel blau","color":"Blau","offers":{"price":499,"priceCurrency":"EUR"}},
 {"@type":"Product","sku":"K-S","name":"Sessel Kiel schwarz","color":"Schwarz","offers":{"price":529,"priceCurrency":"EUR"}}]}
</script>"""

SITEMAP_INDEX = """<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://shop.test/sitemap-products.xml</loc></sitemap>
<sitemap><loc>https://shop.test/sitemap-blog.xml</loc></sitemap></sitemapindex>"""
SITEMAP = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://shop.test/p/lund-esstisch</loc></url>
<url><loc>https://shop.test/p/kiel-sessel</loc></url>
<url><loc>https://shop.test/p/secret-item</loc></url>
<url><loc>https://shop.test/inspiration/blog-post</loc></url></urlset>"""


def make_client(routes: dict, robots="User-agent: *\nDisallow: /p/secret\nSitemap: https://shop.test/sitemap.xml"):
    calls = []

    def handler(req: httpx.Request):
        calls.append(str(req.url))
        path = req.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=robots)
        if path in routes:
            body = routes[path]
            if callable(body):
                return body(req)
            ct = "application/json" if isinstance(body, (dict, list)) else (
                "application/xml" if str(body).startswith("<?xml") else "text/html")
            content = json.dumps(body) if isinstance(body, (dict, list)) else body
            return httpx.Response(200, text=content, headers={"content-type": ct})
        return httpx.Response(404, text="nope")

    c = PoliteClient(delay=0, transport=httpx.MockTransport(handler))
    c.sleep = lambda s: None
    return c, calls


def test_shopify_variants_and_paging():
    def products(req):
        page = int(req.url.params.get("page", 1))
        return httpx.Response(200, json=SHOPIFY if page == 1 else {"products": []})
    client, calls = make_client({"/products.json": products})
    assert adapters.detect_platform(client, R) == "shopify"
    raws = list(adapters.shopify(client, R))
    assert [r.color_raw for r in raws] == ["Grå", "Mosgrøn"]
    assert raws[0].price == 7999.0 and raws[0].group_key == "1"
    assert raws[1].url.endswith("?variant=12") and raws[1].in_stock is False


def test_sitemap_jsonld_respects_robots_and_parses():
    client, calls = make_client({"/sitemap.xml": SITEMAP_INDEX,
                                 "/sitemap-products.xml": SITEMAP,
                                 "/p/lund-esstisch": PRODUCT_PAGE,
                                 "/p/kiel-sessel": GROUP_PAGE})
    raws = list(adapters.sitemap_jsonld(client, {**R, "currency": "EUR"}))
    assert not any("secret" in u for u in calls), "robots.txt Disallow must be honoured"
    assert not any("sitemap-blog" in u for u in calls)
    lund = next(r for r in raws if r.sku == "L-1")
    assert lund.price == 1299.0 and lund.currency == "EUR" and lund.gtin == "5701234567890"
    assert (lund.width_cm, lund.depth_cm, lund.height_cm) == (180.0, 90.0, 75.0)
    assert lund.source_category == "Möbel / Esstische" and lund.in_stock is True
    kiel = [r for r in raws if r.group_key == "G1"]
    assert {r.color_raw for r in kiel} == {"Blau", "Schwarz"}


def test_woocommerce_minor_units():
    items = [{"id": 5, "name": "Reol Ribe", "permalink": "https://shop.test/reol-ribe",
              "prices": {"price": "149900", "currency_code": "DKK", "currency_minor_unit": 2},
              "attributes": [{"name": "Farve", "terms": [{"name": "Hvid"}]}],
              "categories": [{"name": "Reoler"}], "images": [], "is_in_stock": True}]

    def api(req):
        return httpx.Response(200, json=items if req.url.params.get("page") == "1" else [])
    client, _ = make_client({"/wp-json/wc/store/v1/products": api})
    raws = list(adapters.woocommerce(client, R))
    assert raws[0].price == 1499.0 and raws[0].color_raw == "Hvid"


def test_google_feed():
    xml = b"""<?xml version="1.0"?><rss xmlns:g="http://base.google.com/ns/1.0"><channel>
    <item><g:id>9</g:id><title>Couchtisch Ribe</title><link>https://shop.test/ribe</link>
    <g:price>349.00 EUR</g:price><g:color>Schwarz</g:color><g:gtin>4001234567890</g:gtin>
    <g:product_width>110 cm</g:product_width><g:product_height>40 cm</g:product_height>
    <g:availability>in_stock</g:availability></item></channel></rss>"""
    raws = list(adapters.parse_google_feed(xml, R))
    assert raws[0].price == 349.0 and raws[0].currency == "EUR" and raws[0].in_stock
    assert "B 110 cm" in raws[0].dimensions_raw


def test_csv_feed_awin_style():
    text = ("aw_product_id;product_name;aw_deep_link;search_price;currency;colour;dimensions\n"
            "1;Lænestol Fanø;https://shop.test/fano;2.499,00;DKK;Cognac;B 80 x D 85 x H 90 cm\n")
    raws = list(adapters.parse_csv_feed(text, R))
    assert raws[0].price == 2499.0 and raws[0].color_raw == "Cognac"


def test_ingest_deactivates_vanished_products(tmp_path):
    conn = db.connect(tmp_path / "x.db")
    client, _ = make_client({"/products.json": lambda req: httpx.Response(
        200, json=SHOPIFY if req.url.params.get("page") == "1" else {"products": []})})
    res = runner.crawl_retailer(conn, {**R, "platform": "shopify"}, client)
    assert res["status"] == "ok" and res["products"] == 2
    one_variant = {"products": [{**SHOPIFY["products"][0],
                                 "variants": SHOPIFY["products"][0]["variants"][:1]}]}
    client2, _ = make_client({"/products.json": lambda req: httpx.Response(
        200, json=one_variant if req.url.params.get("page") == "1" else {"products": []})})
    res2 = runner.crawl_retailer(conn, {**R, "platform": "shopify"}, client2)
    assert res2["deactivated"] == 1
    assert db.search(conn, "sofa")["items"][0]["n_variants"] == 1


def test_bot_challenge_is_reported_not_bypassed():
    client, _ = make_client({"/p/x": lambda req: httpx.Response(
        403, text="<html>Please complete the captcha</html>")})
    with pytest.raises(Blocked):
        client.get("https://shop.test/p/x")


def test_retry_on_429():
    hits = {"n": 0}

    def flaky(req):
        hits["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "1"}) if hits["n"] == 1 else \
            httpx.Response(200, text="ok")
    client, _ = make_client({"/p/y": flaky})
    assert client.get("https://shop.test/p/y").text == "ok" and hits["n"] == 2


def test_registry_loads():
    from fb import registry
    rs = registry.load()
    assert len(rs) > 30 and {r["country"] for r in rs} == {"DK", "DE"}


def test_robots_429_means_back_off_not_retry_storm():
    hits = []

    def handler(req):
        hits.append(req.url.path)
        return httpx.Response(429, headers={"Retry-After": "10"})
    client = PoliteClient(delay=0, transport=httpx.MockTransport(handler))
    client.sleep = lambda s: None
    res = runner.probe({**R}, client)
    assert res["status"] == "blocked" and res["robots"] == 429
    assert hits == ["/robots.txt"], "nothing beyond robots.txt may be requested"


def test_probe_reports_403_robots_as_blocked():
    client, calls = make_client({}, robots="")
    client.client._transport = httpx.MockTransport(lambda req: httpx.Response(403, text="no"))
    res = runner.probe({**R}, client)
    assert res == {"id": "t", "status": "blocked", "robots": 403, "reason": "refuses bots (403)"}
