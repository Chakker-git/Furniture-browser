import pytest

from fb.extract import normalize, parse_dimensions, parse_seats
from fb.lexicon import ATTRIBUTE_MATCHER, CATEGORY_MATCHER, COLOR_MATCHER, MATERIAL_MATCHER
from fb.models import RawProduct


@pytest.mark.parametrize("text,cat,expected", [
    ("B 200 x D 90 x H 80 cm", None, {"w": 200, "d": 90, "h": 80}),
    ("Mål: 220 x 95 x 82 cm", None, {"w": 220, "d": 95, "h": 82}),
    ("BxHxT: 200x80x90 cm", None, {"w": 200, "h": 80, "d": 90}),
    ("B/T/H: 180/45/75 cm", None, {"w": 180, "d": 45, "h": 75}),
    ("Bredde: 2000 Dybde: 900 Højde: 750", None, {"w": 200, "d": 90, "h": 75}),
    ("Breite: 200 cm, Höhe: 80cm, Tiefe 95 cm", None, {"w": 200, "h": 80, "d": 95}),
    ("Ø120 cm runder Esstisch", None, {"dia": 120}),
    ("Seng 140x200", "bed", {"w": 140, "l": 200}),
    ("Dimensions: 1800 x 900 x 740 mm", None, {"w": 180, "d": 90, "h": 74}),
    ("Bredde: 2,4 m", None, {"w": 240}),
    ("Sitzhöhe: 45 cm, Höhe: 85 cm", None, {"h": 85}),  # seat height is not height
    ("2x3 stk", None, {}),                              # no unit, not a bed: ignore
    ("Pakke med 4 stk", None, {}),
])
def test_parse_dimensions(text, cat, expected):
    assert parse_dimensions(text, cat) == expected


@pytest.mark.parametrize("text,seats", [("Hampton 3-pers. sofa", 3), ("2,5-Sitzer Sofa", 2.5),
                                        ("3 seater sofa", 3), ("Sofa", None)])
def test_parse_seats(text, seats):
    assert parse_seats(text) == seats


@pytest.mark.parametrize("text,cat", [
    ("Hampton sofabord, eg", "coffee_table"), ("Couchtisch Eiche", "coffee_table"),
    ("Esszimmerstuhl 2er-Set", "chair"), ("Spisebordsstol i wienerflet", "chair"),
    ("Bürosessel schwarz", "office_chair"), ("Oak dining tables", "dining_table"),
    ("Mørkegrå hjørnesofa med chaiselong", "sofa"), ("Boxspringbett 180x200", "bed"),
    ("Sitzkissen für Stuhl", "cushion"), ("Kleiderschrank weiß", "wardrobe"),
])
def test_category(text, cat):
    assert CATEGORY_MATCHER.ids(text)[0] == cat


def test_compound_colors_and_false_positives():
    assert COLOR_MATCHER.ids("mørkegrå") == ["grey"]
    assert COLOR_MATCHER.ids("Dunkelgrau") == ["grey"]
    assert COLOR_MATCHER.ids("Versand kostenlos, Signatur-Serie") == []
    assert ATTRIBUTE_MATCHER.ids("Gartenstuhl") == ["outdoor"]
    assert ATTRIBUTE_MATCHER.ids("essential collection") == []
    assert MATERIAL_MATCHER.ids("Samt-Sessel mit Eichenbeinen") == ["velvet"]


def test_normalize_prefers_structured_color_and_drops_wood_when_other_colors():
    raw = RawProduct("r", "1", "https://x/p/1", "Aarhus sofa, grå stof, egeben",
                     description="<p>B 210 x D 90 x H 80 cm</p>", price=7460, currency="DKK")
    p = normalize(raw, "DK")
    assert p.category == "sofa" and p.colors == ["grey"]
    assert (p.width_cm, p.depth_cm, p.height_cm) == (210, 90, 80)
    assert p.price_eur == pytest.approx(999.95, abs=0.1)
    raw2 = RawProduct("r", "2", "https://x/p/2", "Aarhus sofa", color_raw="Mosgrøn")
    assert normalize(raw2, "DK").colors == ["green"]
