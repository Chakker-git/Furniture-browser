# Furniture Browser

Search furniture across Danish and German retailers in **English, Danish or German**, with
filters for **colour, size (W/D/H cm), seats, price (DKK/EUR), category, material, country,
retailer**.

Read [`docs/EVALUATION.md`](docs/EVALUATION.md) first. It covers what the platform needs,
what's built, the legal position, and what isn't solved yet.

## Quick start

```bash
pip install -r requirements.txt
python -m fb demo            # loads a synthetic catalogue from 4 fictional shops
python -m fb serve           # http://127.0.0.1:8000
python -m pytest -q          # 49 tests
```

## Real data

```bash
python -m fb probe                         # robots.txt, sitemaps, platform detection per retailer
python -m fb crawl --retailer jysk-dk      # one retailer
python -m fb crawl                         # all enabled retailers in retailers.toml
python -m fb ingest feed.xml --retailer home24-de --format google   # Google Merchant feed
python -m fb ingest awin.csv --retailer bolia-dk --format csv       # affiliate CSV
python -m fb stats                         # products + % with size/colour/category per retailer
```

`retailers.toml` lists about 40 DK/DE retailers. All are unverified (see the evaluation). The
large sites likely to block bots (IKEA, XXXLutz group, OTTO) are `enabled = false`, so get a
feed for them instead. Set `FB_USER_AGENT` to something that identifies you and includes a
contact URL.

## How it works

```
retailers.toml ─► adapters (feed | shopify | woocommerce | sitemap+JSON-LD)
                     │  PoliteClient: robots.txt, Crawl-delay, rate limit, backoff, stop on bot challenge
                     ▼
                RawProduct ─► extract.normalize()
                     │  category / colour / material via EN·DA·DE lexicon (compound-aware)
                     │  dimensions from 6+ text formats, seats, price → EUR
                     ▼
                SQLite (products, variants, colours, price history, crawl runs) + FTS5
                     │  concept tokens: "grå" / "grau" / "grey" → zzcolgrey
                     ▼
                FastAPI /api/search, /api/product/{id}, /api/meta  ─►  static web UI
```

| Path | What |
|---|---|
| `fb/lexicon.py` | The vocabulary. Most search-quality fixes happen here. |
| `fb/extract.py` | Dimensions, seats, colour, category, normalisation |
| `fb/db.py` | Schema, upsert, query building, faceted search |
| `fb/crawl/` | HTTP client, sitemap walker, adapters, runner |
| `fb/web/` | UI (vanilla JS, no build step), EN/DA, DKK/EUR, shareable URLs |
