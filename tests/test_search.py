import pytest

from fb import db, demo
from fb.crawl import runner


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    c = db.connect(tmp_path_factory.mktemp("d") / "t.db")
    cat = demo.generate()
    for r in demo.RETAILERS:
        runner.ingest(c, r, cat[r["id"]], "demo")
    return c


@pytest.mark.parametrize("queries", [
    ("grey sofa", "grå sofa", "Sofa grau", "graue Sofa"),
    ("dining table", "spisebord", "Esstisch"),
    ("dining chair", "spisebordsstol", "Esszimmerstuhl"),
    ("garden chair", "havestol", "Gartenstuhl"),
    ("chair", "stol", "Stuhl", "chairs", "stole"),
    ("coffee table", "sofabord", "Couchtisch"),
])
def test_cross_lingual_parity(conn, queries):
    totals = {q: db.search(conn, q)["total"] for q in queries}
    assert len(set(totals.values())) == 1, totals
    assert next(iter(totals.values())) > 0


def test_specific_beats_broad(conn):
    assert db.search(conn, "spisebord")["total"] < db.search(conn, "bord")["total"]
    assert db.search(conn, "havestol")["total"] < db.search(conn, "stol")["total"]


def test_filters_and_facets(conn):
    r = db.search(conn, "sofa", {"color": ["grey"], "wmax": 220, "country": ["DE"]})
    assert r["total"] > 0
    for item in r["items"]:
        assert item["country"] == "DE" and item["width_cm"] <= 220
    # disjunctive facet: colour counts ignore the colour filter itself
    assert len(r["facets"]["color"]) > 1


def test_currency_display(conn):
    r = db.search(conn, "sofa", {"country": ["DE"]}, currency="DKK")
    item = r["items"][0]
    assert item["currency"] == "EUR" and item["display_currency"] == "DKK"
    assert item["display_price"] == pytest.approx(item["price_eur"] * 7.46038, rel=1e-3)


def test_detail_and_cross_retailer_offers(conn):
    row = conn.execute("SELECT gtin FROM products WHERE gtin IS NOT NULL GROUP BY gtin "
                       "HAVING COUNT(DISTINCT retailer_id) > 1 LIMIT 1").fetchone()
    assert row, "demo data should contain shared GTINs"
    pid = conn.execute("SELECT id FROM products WHERE gtin=?", (row["gtin"],)).fetchone()["id"]
    d = db.product_detail(conn, pid)
    assert d["other_offers"] and all(o["gtin"] == row["gtin"] for o in d["other_offers"])


def test_empty_and_odd_queries(conn):
    assert db.search(conn, "")["total"] > 0
    assert db.search(conn, '"; DROP TABLE products; --')["total"] == 0
    assert db.search(conn, "og med til")["total"] > 0  # stopwords only -> browse
