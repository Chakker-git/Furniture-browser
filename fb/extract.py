"""Turn messy retailer text into structured, filterable fields.

Dimensions are the hard one: retailers write "B 200 x D 90 x H 80 cm",
"Breite: 200 cm", "BxHxT: 200x80x90", "Ø120 cm", "140x200" (bed) or bury it in
description HTML. We parse into centimetres and keep only plausible values.
"""
from __future__ import annotations

import re

from .currency import to_eur
from .lexicon import (ATTRIBUTE_MATCHER, CATEGORY_MATCHER, COLOR_MATCHER,
                      MATERIAL_MATCHER, MATERIALS)
from .models import Product, RawProduct
from .textnorm import strip_html

NUM = r"(\d{1,4}(?:[.,]\d{1,2})?)"
UNIT = r"(mm|cm|m)\b"

AXIS_BY_LABEL = {
    "b": "w", "br": "w", "w": "w", "bredde": "w", "breite": "w", "width": "w",
    "d": "d", "t": "d", "dybde": "d", "tiefe": "d", "depth": "d",
    "h": "h", "højde": "h", "höhe": "h", "hoehe": "h", "height": "h",
    "l": "l", "længde": "l", "länge": "l", "laenge": "l", "length": "l",
    "ø": "dia", "diameter": "dia", "durchmesser": "dia",
}
_LONG_LABELS = "bredde|breite|width|dybde|tiefe|depth|højde|höhe|hoehe|height|længde|länge|laenge|length|diameter|durchmesser"
_SHORT = "[bwdthl]"

# "BxHxT: 200x80x90 cm" / "B/T/H 200/90/80 cm"
_LETTER_CHAIN = re.compile(
    rf"\b({_SHORT})\s*[x×*/]\s*({_SHORT})(?:\s*[x×*/]\s*({_SHORT}))?\s*(?:\(\s*cm\s*\)|in\s+cm)?\s*[:=]?\s*"
    rf"{NUM}\s*[x×*/]\s*{NUM}(?:\s*[x×*/]\s*{NUM})?\s*(?:{UNIT})?", re.I)
# "B 200 x D 90 x H 80 cm" / "200 x 90 x 80 cm" / "140x200"
_PART = rf"(?:({_SHORT}|{_LONG_LABELS})\.?\s*[:=]?\s*)?{NUM}\s*(?:mm|cm)?"
_NUM_CHAIN = re.compile(
    rf"(?<![\w.,]){_PART}\s*[x×*]\s*{_PART}(?:\s*[x×*]\s*{_PART})?\s*(?:{UNIT})?", re.I)
# "Bredde: 200 cm", "Höhe 80cm", "Ø 120 cm"
_LABELED = re.compile(
    rf"(?<![\w])({_LONG_LABELS}|ø|{_SHORT})\.?\s*(?:ca\.?\s*)?[:=]?\s*{NUM}\s*(?:{UNIT})?", re.I)
_SEATS = re.compile(
    r"(\d(?:[.,]5)?)\s*(?:-|\s)?\s*(?:pers\b|pers\.|personers|personer|seater|sitzer|"
    r"sits|pladser|places|-sitzer|er[\s-]sofa)", re.I)


def _to_cm(value: str, unit: str | None, labeled_word: bool = False) -> float | None:
    v = float(value.replace(",", "."))
    unit = (unit or "").lower()
    if unit == "mm":
        v /= 10
    elif unit == "m":
        v *= 100
    elif not unit and labeled_word and v > 400:
        v /= 10  # "Bredde: 2000" is almost certainly mm
    return round(v, 1) if 1 <= v <= 600 else None


def parse_dimensions(text: str, category: str | None = None) -> dict[str, float]:
    """Return {'w','d','h','l','dia'} in cm, first plausible hit per axis wins."""
    if not text:
        return {}
    text = text.replace(" ", " ")
    out: dict[str, float] = {}

    def put(axis: str, cm: float | None):
        if cm is not None and axis not in out:
            out[axis] = cm

    for m in _LETTER_CHAIN.finditer(text):
        labels = [g for g in m.groups()[0:3]]
        nums = m.groups()[3:6]
        unit = m.group(7)
        if not unit and not re.search(r"cm", text[max(0, m.start() - 15):m.end() + 5], re.I):
            unit = "cm"
        for lab, num in zip(labels, nums):
            if lab and num:
                put(AXIS_BY_LABEL[lab.lower()], _to_cm(num, unit))

    for m in _NUM_CHAIN.finditer(text):
        g = m.groups()
        parts = [(g[0], g[1]), (g[2], g[3]), (g[4], g[5])]
        parts = [(lab, num) for lab, num in parts if num]
        unit = g[6]
        has_cm = unit or re.search(r"\b(mm|cm)\b", m.group(0), re.I)
        if not has_cm and len(parts) < 3 and category not in ("bed", "mattress", "rug"):
            continue  # "2x3" without unit is too ambiguous outside beds/rugs
        unit = unit or ("mm" if re.search(r"\bmm\b", m.group(0), re.I) else "cm")
        if all(lab for lab, _ in parts):
            for lab, num in parts:
                put(AXIS_BY_LABEL[lab.lower()], _to_cm(num, unit))
        elif len(parts) == 2 and category in ("bed", "mattress", "rug"):
            put("w", _to_cm(parts[0][1], unit))
            put("l", _to_cm(parts[1][1], unit))
        else:  # unlabeled: retailer convention is W x D x H (B x T x H)
            for axis, (lab, num) in zip(("w", "d", "h"), parts):
                put(AXIS_BY_LABEL[lab.lower()] if lab else axis, _to_cm(num, unit))

    for m in _LABELED.finditer(text):
        lab, num, unit = m.group(1).lower(), m.group(2), m.group(3)
        long_label = len(lab) > 2 or lab == "ø"
        if not long_label and not unit:
            continue  # bare "H 80" without unit: skip, too noisy
        put(AXIS_BY_LABEL[lab], _to_cm(num, unit, labeled_word=long_label))
    return out


def parse_seats(text: str) -> float | None:
    m = _SEATS.search(text or "")
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return v if 1 <= v <= 8 else None


_WOOD_MATERIALS = {"oak", "walnut", "ash", "beech", "pine", "teak", "acacia", "bamboo"}


def extract_colors(raw: RawProduct) -> list[str]:
    if raw.color_raw:
        colors = COLOR_MATCHER.ids(raw.color_raw)
        if colors:
            return colors
    colors = COLOR_MATCHER.ids(raw.title)
    if not colors:
        # explicit "Farve: ..."/"Farbe: ..."/"Colour: ..." line in the description
        m = re.search(r"(?:farve|farbe|colou?r)\s*[:=]\s*([^\n.;|<]{2,40})",
                      raw.description or "", re.I)
        if m:
            colors = COLOR_MATCHER.ids(m.group(1))
    if len(colors) > 1 and "wood" in colors:
        colors = [c for c in colors if c != "wood"]  # "grey sofa, oak legs" -> grey
    return colors


def classify_category(raw: RawProduct) -> str | None:
    for text in (raw.title, raw.source_category or "", " ".join(raw.tags)):
        ids = CATEGORY_MATCHER.ids(text)
        if ids:
            return ids[0]
    return None


def normalize(raw: RawProduct, country: str) -> Product:
    desc = strip_html(raw.description)
    raw.description = desc
    category = classify_category(raw)
    all_text = " ".join(filter(None, [raw.title, raw.source_category, " ".join(raw.tags)]))
    attributes = ATTRIBUTE_MATCHER.ids(all_text + " " + desc[:400])
    materials = MATERIAL_MATCHER.ids(" ".join(filter(None, [raw.material_raw, raw.title,
                                                            desc[:1500]])))
    colors = extract_colors(raw)

    dims = {}
    for source in (raw.dimensions_raw, raw.title, desc):
        for axis, v in parse_dimensions(source or "", category).items():
            dims.setdefault(axis, v)
    width = raw.width_cm or dims.get("w")
    depth = raw.depth_cm or dims.get("d") or dims.get("l")
    height = raw.height_cm or dims.get("h")
    dia = dims.get("dia")
    if dia and not width:
        width = depth = dia
    if not width and dims.get("l"):
        width = dims["l"]  # tables often give only length

    price_eur = to_eur(raw.price, raw.currency) if raw.price is not None else None
    return Product(
        retailer_id=raw.retailer_id, country=country, external_id=raw.external_id,
        group_key=raw.group_key or raw.external_id, url=raw.url, title=raw.title.strip(),
        description=desc, brand=raw.brand, category=category, attributes=attributes,
        colors=colors, color_raw=raw.color_raw, materials=materials,
        width_cm=width, depth_cm=depth, height_cm=height, diameter_cm=dia,
        seats=parse_seats(raw.title) or (parse_seats(desc[:300]) if category in
                                         ("sofa", "sofa_bed") else None),
        price=raw.price, currency=(raw.currency or "").upper() or None, price_eur=price_eur,
        image_url=raw.image_url, gtin=_clean_gtin(raw.gtin), sku=raw.sku,
        in_stock=raw.in_stock,
    )


def _clean_gtin(g: str | None) -> str | None:
    if not g:
        return None
    digits = re.sub(r"\D", "", str(g))
    return digits.zfill(14) if 8 <= len(digits) <= 14 else None


MATERIAL_IDS = [m.id for m in MATERIALS]
