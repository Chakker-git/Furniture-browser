# Critical evaluation: furniture search for Denmark + Germany

Written before building, then updated with what the MVP showed.

## 1. The brief, stress-tested

> "Scrape in depth **all** furniture retailers in Denmark and Germany, search in English or
> Danish, filter by colour and size."

| Assumption in the brief | Reality | Consequence |
|---|---|---|
| "All retailers" is achievable | Germany alone: ~EUR 33bn furniture market, hundreds of chains plus a long tail of webshops; OTTO's marketplace alone has ~6,200 partners. Denmark's top-100 furniture sites are listed by Semrush, and there are many more. | Aim for **coverage of the market by revenue/traffic**, not a count of shops. ~40 retailers per country cover most of what people buy online. The generic adapter picks up some of the long tail. |
| Scraping is the way to get the data | The biggest players (IKEA, XXXLutz group, OTTO, Amazon) are the most likely to run bot protection and restrictive terms. Many retailers **already publish product feeds** for Google Shopping and affiliate networks (Awin, Adtraction, Partner-ads). | **Feeds first, scraping second.** Feeds are legal, complete, structured, cheap to process, and affiliate links pay you. |
| Search in English or Danish | Half the catalogue is written in **German**. | The search must map EN/DA queries onto DE (and DA) product text. Translating the query isn't enough because of compounds (*Esszimmerstuhl*, *spisebordsstol*). |
| "Colour" and "size" filters are simple | Neither is structured on most sites. Colour is a variant option named *Farve*, *Farbe*, *Bezug* or *Stof*, or is only in the title, with values like *mosgrøn* or *Anthrazit*. Size is free text in at least six formats (*B 200 x D 90*, *BxHxT*, *B/T/H*, *Ø120*, *140x200*, mm or cm). | **Normalisation is the actual product.** Without it the filters silently drop most items. |
| One product = one row | A sofa in 12 fabrics is 12 variants at one URL. | Index variants, show grouped cards, and filter at variant level ("this sofa *in green*"). |

## 2. Legal / risk (not legal advice; check with a lawyer before going public)

- **EU database right** (DE: §87a/§87b UrhG; DK: ophavsretsloven §71). Retailers' catalogues
  count as protected databases. The OLG Köln (6 U 128/19, 2020) held that repeated, systematic
  automated extraction by a competitor infringed even if each part taken was insubstantial.
  Building a **public, commercial** index of scraped catalogues is the riskiest version of this project.
- **Images and descriptions** are copyrighted. The MVP hotlinks thumbnails and links out to
  the retailer. It doesn't rehost images or republish full descriptions.
- **Terms of service and bot protection.** The crawler identifies itself, obeys robots.txt and
  Crawl-delay, rate-limits, and **stops when it hits a challenge** instead of evading it. This is
  a deliberate design choice, not a missing feature.
- **Personal use is lower risk.** For a public launch, use affiliate feeds and partnerships.
  The architecture already supports this (`platform = "feed"`).

## 3. Feature set, prioritised

**Must have (built in the MVP)**
1. Cross-lingual search EN/DA/DE with compound-word handling, e.g. *havestol* = *Gartenstuhl* = *garden chair*
2. Colour filter on canonical colours (17), with variant-level matching
3. Size filters: width, depth, height ranges in cm, plus seat count; parsing of all common formats
4. Price filter and display in DKK or EUR (DKK is pegged, so the conversion is exact enough)
5. Category, material, country and retailer facets with live counts
6. Variant grouping, and outbound links to the retailer (the transaction happens there)
7. Crawl health and data-quality coverage per retailer (`python -m fb stats`)
8. Removed products are hidden, not deleted, and price history is recorded

**Should have (next)**
- Scheduled recrawls and alerting when a retailer's coverage drops (adapters break silently)
- Price comparison of the same item across shops via GTIN/EAN. The data model and UI exist,
  but it depends on retailers exposing a GTIN
- Shipping: "ships to Denmark" for German shops. This matters for Danish users and isn't in
  any feed, so it has to be curated per retailer
- Saved searches and price-drop alerts
- "Fits my space": enter the room niche (W×D×H) once and filter everything to it

**Later / maybe**
- Semantic search (multilingual embeddings) for vague queries like "cosy reading chair"
- Visual similarity ("more like this")
- LLM-assisted extraction for the long tail of free-text descriptions. Only worth doing per
  retailer where the regex coverage stays low, because of cost.

**Deliberately not built**
- Accounts, checkout, reviews. Out of scope, and they bring GDPR and payment overhead.
- CAPTCHA solving or residential proxies. See §2.

## 4. Architecture decisions

| Decision | Why | When to revisit |
|---|---|---|
| Python + SQLite FTS5 | Zero-ops, a single file, handles low millions of rows | More than about 2M rows, or facet queries over 300 ms: move `fb/db.py:search` to Meilisearch or OpenSearch (the interface is already isolated) |
| Concept tokens instead of machine translation | Deterministic, explainable ("Understood: Grey, Sofa"), no API cost, handles compounds | When queries fall outside the lexicon: add embeddings alongside, not instead |
| Platform adapters (Shopify / WooCommerce / JSON-LD / feeds) instead of per-site CSS selectors | Selectors break every redesign. Structured endpoints and schema.org rarely change. | A high-value retailer has none of these: write one bespoke adapter |
| Hotlinked images, link-out | Legal posture and storage cost | Never, unless you have image licences |

## 5. Known gaps in this MVP (stated plainly)

- **Not run against live retailers.** The build sandbox couldn't reach retailer hosts. All
  adapters are tested against realistic mocked responses. Run `python -m fb probe` on a
  networked machine first, and expect to tune `product_url_pattern` for some sites.
- The lexicon is hand-built (about 800 terms). It will miss words, and every miss is a one-line fix in `fb/lexicon.py`.
- English-language stemming is crude. Danish/German inflection is handled by suffix stripping, not a real morphological analyser.
- No scheduler is included. Use cron or a systemd timer: `python -m fb crawl` is idempotent.

## Sources
- Handelsdaten.de, ranking of German furniture retailers by 2025 revenue (IKEA ~EUR 6.5bn; market EUR 33.4bn; online EUR 5.6bn)
- Semrush, most-visited furniture websites in Denmark, Oct 2026 (jysk.dk, ilva.dk, beliani.dk, vidaxl.dk, boligcenter.dk, ...)
- Reuters, 10 Jan 2025: Wayfair exits Germany (wayfair.de no longer takes orders), so it's excluded
- OLG Köln, judgment 28.02.2020, 6 U 128/19 (database right and web scraping)
- §87b UrhG (gesetze-im-internet.de)
