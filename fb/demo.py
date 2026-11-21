"""Synthetic demo catalogue (fictional retailers) so the UI and search can be tried
without network access. Titles/descriptions deliberately use the messy, mixed
formats real shops use, and go through the same normalize() as crawled data."""
from __future__ import annotations

import random

from .models import RawProduct

RETAILERS = [
    {"id": "demo-nordhjem-dk", "name": "Nordhjem (demo)", "country": "DK",
     "base_url": "https://nordhjem.example", "currency": "DKK"},
    {"id": "demo-stuen-dk", "name": "Stuen Design (demo)", "country": "DK",
     "base_url": "https://stuen.example", "currency": "DKK"},
    {"id": "demo-wohnwerk-de", "name": "Wohnwerk (demo)", "country": "DE",
     "base_url": "https://wohnwerk.example", "currency": "EUR"},
    {"id": "demo-moebelhof-de", "name": "Möbelhof (demo)", "country": "DE",
     "base_url": "https://moebelhof.example", "currency": "EUR"},
]

# (kind, da_noun, de_noun, (w range), (d range), (h range), base EUR price)
KINDS = [
    ("sofa", "{n}-pers. sofa", "{n}-Sitzer Sofa", (160, 280), (85, 100), (75, 90), 900),
    ("corner", "Hjørnesofa med chaiselong", "Ecksofa mit Recamiere", (240, 320), (150, 200),
     (78, 88), 1500),
    ("sofabed", "Sovesofa", "Schlafsofa", (180, 220), (90, 100), (80, 90), 700),
    ("armchair", "Lænestol", "Sessel", (70, 90), (75, 90), (75, 100), 450),
    ("chair", "Spisebordsstol", "Esszimmerstuhl", (45, 55), (50, 58), (78, 85), 140),
    ("dining", "Spisebord", "Esstisch", (160, 240), (90, 100), (74, 76), 800),
    ("coffee", "Sofabord", "Couchtisch", (80, 130), (50, 80), (35, 45), 300),
    ("desk", "Skrivebord", "Schreibtisch", (120, 160), (60, 80), (74, 76), 350),
    ("bed", "Seng", "Bett", (140, 180), (200, 210), (90, 110), 900),
    ("shelf", "Reol", "Regal", (60, 120), (30, 40), (150, 200), 250),
    ("sideboard", "Skænk", "Sideboard", (140, 200), (40, 50), (65, 80), 700),
    ("lamp", "Gulvlampe", "Stehlampe", (30, 50), (30, 50), (140, 170), 180),
    ("garden", "Havestol", "Gartenstuhl", (55, 65), (55, 65), (80, 90), 120),
]
COLORS = [("grå", "grau"), ("mørkegrå", "dunkelgrau"), ("sort", "schwarz"),
          ("hvid", "weiß"), ("beige", "beige"), ("grøn", "grün"), ("blå", "blau"),
          ("cognac", "cognac"), ("rosa", "rosa"), ("sennep", "senf"), ("natur", "natur")]
MATERIALS = [("bouclé", "Bouclé"), ("velour", "Samt"), ("læder", "Leder"), ("stof", "Stoff"),
             ("eg", "Eiche"), ("valnød", "Nussbaum"), ("metal", "Metall"),
             ("rattan", "Rattan")]
NAMES = ["Aalborg", "Skagen", "Hamburg", "Kiel", "Lund", "Fanø", "Bremen", "Odense", "Lübeck",
         "Møn", "Rügen", "Vejle", "Sylt", "Aarhus", "Husum", "Ribe", "Flensburg", "Ærø"]


def _dims_text(rng, w, d, h, lang):
    style = rng.randrange(5)
    if style == 0:
        return f"B {w} x D {d} x H {h} cm" if lang == "da" else f"B {w} x T {d} x H {h} cm"
    if style == 1:
        return (f"Bredde: {w} cm, Dybde: {d} cm, Højde: {h} cm" if lang == "da"
                else f"Breite: {w} cm, Tiefe: {d} cm, Höhe: {h} cm")
    if style == 2:
        return f"Mål: {w}x{d}x{h} cm" if lang == "da" else f"Maße (BxTxH): {w}x{d}x{h} cm"
    if style == 3:
        return f"{w * 10} x {d * 10} x {h * 10} mm"
    return "" if rng.random() < 0.5 else f"B/T/H: {w}/{d}/{h} cm"


def generate(seed: int = 7, per_retailer: int = 90) -> dict[str, list[RawProduct]]:
    rng = random.Random(seed)
    out: dict[str, list[RawProduct]] = {r["id"]: [] for r in RETAILERS}
    shared: list[tuple] = []  # products carried by several retailers (same GTIN)
    for r in RETAILERS:
        lang = "da" if r["country"] == "DK" else "de"
        for i in range(per_retailer):
            if shared and rng.random() < 0.15:
                spec = rng.choice(shared)
            else:
                kind = rng.choice(KINDS)
                spec = (kind, rng.choice(NAMES), rng.choice(MATERIALS),
                        rng.randint(*kind[3]), rng.randint(*kind[4]), rng.randint(*kind[5]),
                        rng.choice([2, 2.5, 3, 4]), f"57{rng.randrange(10**10, 10**11)}",
                        kind[6] * rng.uniform(0.6, 1.6))
                shared.append(spec)
            kind, name, mat, w, d, h, seats, gtin, eur = spec
            noun = (kind[1] if lang == "da" else kind[2]).format(
                n=str(seats).replace(".", ","))
            if kind[0] in ("bed",):
                w = rng.choice([140, 160, 180])
                noun = f"{noun} {w}x200"
            n_colors = rng.choice([1, 1, 2, 3])
            colors = rng.sample(COLORS, n_colors)
            mat_word = mat[0] if lang == "da" else mat[1]
            group = f"{r['id']}-{gtin}"
            for c in colors:
                cword = c[0] if lang == "da" else c[1]
                price = eur * (7.46 if r["currency"] == "DKK" else 1) * rng.uniform(0.9, 1.1)
                price = round(price, -1) - (5 if r["currency"] == "DKK" else 0.05)
                desc = (f"<p>{name} {noun.lower()} i {mat_word} – tidløst skandinavisk design.</p>"
                        if lang == "da" else
                        f"<p>{noun} {name} aus {mat_word} – zeitloses skandinavisches Design.</p>")
                desc += f"<p>{_dims_text(rng, w, d, h, lang)}</p>"
                out[r["id"]].append(RawProduct(
                    retailer_id=r["id"], external_id=f"{gtin}-{c[0]}",
                    url=f"{r['base_url']}/p/{gtin}?farve={c[0]}",
                    title=f"{name} {noun}, {mat_word}, {cword}" if rng.random() < 0.6
                    else f"{name} {noun} – {mat_word}",
                    description=desc, price=price, currency=r["currency"],
                    brand=r["name"].replace(" (demo)", ""), gtin=gtin if n_colors == 1 else None,
                    in_stock=rng.random() > 0.1, group_key=group, color_raw=cword))
    return out
