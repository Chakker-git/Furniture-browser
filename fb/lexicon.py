"""Trilingual (EN/DA/DE) vocabulary: categories, attributes, colors, materials.

Every concept has:
  terms  - whole words or phrases that mean the concept on their own
  heads  - compound *endings* (Danish/German put the head noun last:
           "spisebordsstol" -> "stol", "Esszimmerstuhl" -> "stuhl")
  mods   - compound *beginnings* used for attribute concepts
           ("havestol" -> "have" = outdoor, "Gartenstuhl" -> "garten")

Terms are written in their natural spelling and folded at import time, so the
lexicon is easy to extend by hand. This file is the single biggest lever on
search quality: add words here when a query misses.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .textnorm import fold, tokenize


@dataclass
class Concept:
    id: str
    label_en: str
    label_da: str
    terms: list[str] = field(default_factory=list)
    heads: list[str] = field(default_factory=list)
    mods: list[str] = field(default_factory=list)
    hex: str | None = None  # colors only


def _c(id, en, da, terms=(), heads=(), mods=(), hex=None) -> Concept:
    return Concept(id, en, da,
                   [fold(t) for t in terms], [fold(t) for t in heads],
                   [fold(t) for t in mods], hex)


# --- Product categories -----------------------------------------------------
# Order matters only for display. Matching picks the longest term.
CATEGORIES: list[Concept] = [
    _c("sofa", "Sofa", "Sofa",
       ["sofa", "sofas", "couch", "couches", "settee", "loveseat", "sofaer", "sofaen",
        "wohnlandschaft", "ecksofa", "hjørnesofa", "chaiselong", "chaiselongsofa"],
       ["sofa", "couch", "sofaer"]),
    _c("sofa_bed", "Sofa bed", "Sovesofa",
       ["sofa bed", "sleeper sofa", "sovesofa", "schlafsofa", "schlafcouch", "bettsofa"],
       ["sovesofa", "schlafsofa", "schlafcouch"]),
    _c("armchair", "Armchair", "Lænestol",
       ["armchair", "armchairs", "lounge chair", "accent chair", "recliner", "lænestol",
        "loungestol", "hvilestol", "sessel", "ohrensessel", "relaxsessel", "loungesessel",
        "fauteuil"],
       ["lænestol", "loungestol", "hvilestol", "sessel"]),
    _c("chair", "Chair", "Stol",
       ["chair", "chairs", "stol", "stole", "spisebordsstol", "spisestol",
        "stuhl", "stühle", "esszimmerstuhl", "küchenstuhl", "freischwinger"],
       ["stol", "stole", "stuhl", "stühle"]),
    _c("office_chair", "Office chair", "Kontorstol",
       ["office chair", "desk chair", "kontorstol", "bürostuhl", "schreibtischstuhl",
        "drehstuhl", "bürosessel", "chefsessel", "gamingstol", "gaming chair"],
       ["kontorstol", "bürostuhl", "drehstuhl", "schreibtischstuhl", "bürosessel"]),
    _c("stool", "Stool", "Skammel",
       ["stool", "stools", "bar stool", "barstool", "skammel", "taburet", "barstol",
        "hocker", "barhocker", "pouf", "puf"],
       ["skammel", "taburet", "barstol", "hocker", "puf", "pouf"]),
    _c("bench", "Bench", "Bænk",
       ["bench", "benches", "bænk", "sitzbank", "bank"],
       ["bænk", "bank"]),
    _c("dining_table", "Dining table", "Spisebord",
       ["dining table", "kitchen table", "spisebord", "køkkenbord", "esstisch",
        "esszimmertisch", "küchentisch"],
       ["spisebord", "esstisch", "küchentisch"]),
    _c("coffee_table", "Coffee table", "Sofabord",
       ["coffee table", "sofa table", "sofabord", "couchtisch", "wohnzimmertisch",
        "sofatisch"],
       ["sofabord", "couchtisch", "sofatisch"]),
    _c("side_table", "Side table", "Sidebord",
       ["side table", "end table", "sidebord", "hjørnebord", "beistelltisch",
        "konsolbord", "konsolentisch", "console table"],
       ["sidebord", "beistelltisch", "konsolbord", "konsolentisch"]),
    _c("desk", "Desk", "Skrivebord",
       ["desk", "desks", "writing desk", "skrivebord", "hæve sænkebord", "hævesænkebord",
        "schreibtisch", "sekretär"],
       ["skrivebord", "schreibtisch", "sænkebord"]),
    _c("table", "Table", "Bord",
       ["table", "tables", "bord", "borde", "tisch", "tische"],
       ["bord", "tisch"]),
    _c("bed", "Bed", "Seng",
       ["bed", "beds", "bed frame", "seng", "senge", "sengeramme", "kontinentalseng",
        "boxmadras", "bett", "betten", "bettgestell", "boxspringbett", "doppelbett",
        "polsterbett", "daybed"],
       ["seng", "bett", "sengeramme", "bettgestell"]),
    _c("mattress", "Mattress", "Madras",
       ["mattress", "mattresses", "madras", "madrasser", "topmadras", "matratze",
        "matratzen", "topper"],
       ["madras", "matratze"]),
    _c("nightstand", "Nightstand", "Natbord",
       ["nightstand", "bedside table", "night table", "natbord", "sengebord", "nachttisch",
        "nachtkommode", "nachtschrank"],
       ["natbord", "nachttisch", "nachtschrank"]),
    _c("wardrobe", "Wardrobe", "Garderobeskab",
       ["wardrobe", "closet", "garderobeskab", "klædeskab", "kleiderschrank",
        "drehtürenschrank", "schwebetürenschrank"],
       ["garderobeskab", "klædeskab", "kleiderschrank"]),
    _c("dresser", "Chest of drawers", "Kommode",
       ["dresser", "chest of drawers", "kommode", "kommoder", "kommoden", "highboard"],
       ["kommode"]),
    _c("sideboard", "Sideboard", "Skænk",
       ["sideboard", "credenza", "buffet", "skænk", "anrichte"],
       ["skænk", "sideboard", "anrichte"]),
    _c("tv_unit", "TV unit", "TV-bord",
       ["tv unit", "tv stand", "tv bench", "media unit", "tv bord", "tvbord", "tv møbel",
        "tv board", "lowboard", "tv schrank", "tv möbel", "tv bank"],
       ["tvbord", "lowboard"]),
    _c("shelf", "Shelving", "Reol",
       ["shelf", "shelves", "shelving", "bookcase", "bookshelf", "reol", "reoler",
        "hylde", "hylder", "bogreol", "væghylde", "regal", "regale", "bücherregal",
        "wandregal", "standregal"],
       ["reol", "hylde", "regal"]),
    _c("cabinet", "Cabinet", "Skab",
       ["cabinet", "cupboard", "display cabinet", "skab", "skabe", "vitrineskab",
        "vitrine", "schrank", "schränke", "hochschrank"],
       ["skab", "schrank", "vitrine"]),
    _c("lamp", "Lamp", "Lampe",
       ["lamp", "lamps", "lighting", "pendant", "floor lamp", "table lamp", "lampe",
        "lamper", "pendel", "standerlampe", "loftlampe", "bordlampe", "leuchte",
        "leuchten", "stehlampe", "pendelleuchte", "tischleuchte", "deckenleuchte"],
       ["lampe", "lamper", "leuchte", "pendel"]),
    _c("rug", "Rug", "Tæppe",
       ["rug", "rugs", "carpet", "gulvtæppe", "tæppe", "teppich", "teppiche",
        "läufer", "runner"],
       ["gulvtæppe", "teppich"]),
    _c("mirror", "Mirror", "Spejl",
       ["mirror", "mirrors", "spejl", "spiegel"],
       ["spejl", "spiegel"]),
    _c("cushion", "Cushion", "Pude",
       ["cushion", "cushions", "pillow", "pude", "puder", "hynde", "hynder", "kissen",
        "sitzkissen", "zierkissen", "seat pad"],
       ["pude", "hynde", "kissen"]),
    _c("cover", "Cover", "Betræk",
       ["cover", "slipcover", "betræk", "bezug", "hussen", "husse"],
       ["betræk", "bezug"]),
    _c("coat_rack", "Coat rack", "Knagerække",
       ["coat rack", "coat stand", "knagerække", "stumtjener", "garderobe",
        "garderobenständer", "kleiderständer"],
       ["knagerække", "garderobe"]),
]

# --- Attribute concepts (room / use). Matched as modifiers too. -------------
ATTRIBUTES: list[Concept] = [
    _c("outdoor", "Outdoor", "Udendørs",
       ["outdoor", "garden", "patio", "udendørs", "havemøbler", "havemøbel",
        "gartenmöbel", "garten", "balkon", "terrasse", "loungemøbler"],
       [], ["have", "garten", "outdoor", "terrassen", "balkon"]),
    _c("dining", "Dining", "Spisestue",
       ["dining", "spisestue", "esszimmer"],
       [], ["spise", "spisebords", "esszimmer"]),
    _c("kids", "Kids", "Børn",
       ["kids", "children", "child", "junior", "børn", "børne", "kinder", "kinderzimmer"],
       [], ["børne", "kinder", "junior"]),
    _c("office", "Office", "Kontor",
       ["office", "kontor", "büro", "home office", "hjemmekontor"],
       [], ["kontor", "büro"]),
    _c("bathroom", "Bathroom", "Badeværelse",
       ["bathroom", "badeværelse", "badezimmer"],
       [], ["bade", "badezimmer"]),
    _c("extendable", "Extendable", "Udtræk",
       ["extendable", "extending", "udtræk", "udtræksbord", "ausziehbar", "ausziehtisch"],
       [], ["udtræks", "auszieh"]),
    _c("corner", "Corner", "Hjørne",
       ["corner", "hjørne", "hjørnesofa", "ecksofa", "ecke", "l-shaped"],
       [], ["hjørne", "eck"]),
]

# --- Colors ------------------------------------------------------------------
COLORS: list[Concept] = [
    _c("black", "Black", "Sort",
       ["black", "sort", "schwarz", "charcoal", "kulsort", "noir", "ebony"],
       ["sort", "schwarz", "black"], hex="#1b1b1b"),
    _c("white", "White", "Hvid",
       ["white", "hvid", "hvide", "weiß", "weiss", "off-white", "offwhite", "snow", "kalk"],
       ["hvid", "weiß", "white"], hex="#ffffff"),
    _c("grey", "Grey", "Grå",
       ["grey", "gray", "grå", "grau", "anthracite", "antracit", "anthrazit", "graphite",
        "grafit", "slate", "stone", "steingrau", "concrete grey"],
       ["grå", "grau", "grey", "gray", "anthrazit"], hex="#8d8d8d"),
    _c("beige", "Beige", "Beige",
       ["beige", "sand", "cream", "creme", "crème", "ecru", "ivory", "taupe", "latte",
        "natural white", "linen", "elfenbein", "nougat", "kit"],
       ["beige", "creme"], hex="#d8c7a6"),
    _c("brown", "Brown", "Brun",
       ["brown", "brun", "braun", "cognac", "chocolate", "chokolade", "schoko",
        "mocca", "mokka", "caramel", "karamel", "tobacco", "rust"],
       ["brun", "braun", "brown"], hex="#7a5230"),
    _c("wood", "Wood / natural", "Træ / natur",
       ["natural", "natur", "nature", "wood", "træ", "holz", "holzoptik", "woodgrain",
        "oak look", "egetræ", "eiche natur", "oak", "eg", "eiche", "walnut", "valnød",
        "nussbaum", "teak", "ash", "ask", "esche", "beech", "bøg", "buche", "pine",
        "fyr", "kiefer", "acacia", "akacie", "akazie", "bamboo", "bambus"],
       ["træ", "holz"], hex="#c19a6b"),
    _c("green", "Green", "Grøn",
       ["green", "grøn", "grønne", "grün", "olive", "oliven", "oliv", "sage", "salvie",
        "salbei", "moss", "mos", "moos", "khaki", "petrol", "forest", "flaske"],
       ["grøn", "grün", "green", "oliv"], hex="#55784b"),
    _c("blue", "Blue", "Blå",
       ["blue", "blå", "blau", "navy", "marine", "marineblå", "dusty blue", "denim",
        "indigo", "royal", "türkis", "turquoise", "turkis"],
       ["blå", "blau", "blue"], hex="#3d5f96"),
    _c("red", "Red", "Rød",
       ["red", "rød", "rot", "bordeaux", "burgundy", "wine", "vinrød", "weinrot",
        "terracotta", "terrakotta", "cherry"],
       ["rød", "rot", "red"], hex="#b23b3b"),
    _c("yellow", "Yellow", "Gul",
       ["yellow", "gul", "gelb", "mustard", "sennep", "senf", "ochre", "okker", "ocker",
        "curry", "honey"],
       ["gul", "gelb", "yellow"], hex="#e2bf3f"),
    _c("orange", "Orange", "Orange",
       ["orange", "apricot", "abrikos", "aprikose", "peach", "fersken", "pfirsich",
        "amber", "rav"],
       ["orange"], hex="#dd8530"),
    _c("pink", "Pink", "Lyserød",
       ["pink", "rosa", "lyserød", "rosé", "rose", "blush", "dusty rose", "dusty pink",
        "altrosa", "støvet rosa"],
       ["rosa", "pink", "lyserød"], hex="#e6a4b6"),
    _c("purple", "Purple", "Lilla",
       ["purple", "lilla", "lila", "violet", "violett", "aubergine", "lavender",
        "lavendel", "plum", "blomme"],
       ["lilla", "lila", "violett"], hex="#7d5a96"),
    _c("gold", "Gold / brass", "Guld / messing",
       ["gold", "guld", "brass", "messing", "copper", "kobber", "kupfer", "bronze"],
       ["guld", "gold", "messing"], hex="#c8a24a"),
    _c("silver", "Silver / chrome", "Sølv / krom",
       ["silver", "sølv", "silber", "chrome", "krom", "chrom", "stainless", "rustfri",
        "edelstahl", "aluminium", "alu", "metallic"],
       ["sølv", "silber", "krom", "chrom"], hex="#bfc4c9"),
    _c("transparent", "Clear / transparent", "Klar / transparent",
       ["transparent", "clear", "klar", "glas", "glass", "acrylic", "akryl", "acryl"],
       [], hex="#e8f2f6"),
    _c("multi", "Multicolour", "Flerfarvet",
       ["multicolour", "multicolor", "multi", "flerfarvet", "mehrfarbig", "bunt",
        "mixed", "mønstret", "gemustert", "patterned", "striped", "stribet"],
       [], hex=None),
]

# --- Materials ----------------------------------------------------------------
MATERIALS: list[Concept] = [
    _c("oak", "Oak", "Eg", ["oak", "eg", "egetræ", "eiche", "eichenholz", "egefinér"],
       ["eiche", "egetræ"]),
    _c("walnut", "Walnut", "Valnød", ["walnut", "valnød", "nussbaum", "nussbaumholz"],
       ["valnød", "nussbaum"]),
    _c("ash", "Ash", "Ask", ["ash", "ask", "asketræ", "esche"], ["esche"]),
    _c("beech", "Beech", "Bøg", ["beech", "bøg", "bøgetræ", "buche", "buchenholz"],
       ["bøg", "buche"]),
    _c("pine", "Pine", "Fyr", ["pine", "fyr", "fyrretræ", "kiefer", "kiefernholz"],
       ["fyr", "kiefer"]),
    _c("teak", "Teak", "Teak", ["teak", "teaktræ", "teakholz"], ["teak"]),
    _c("acacia", "Acacia", "Akacie", ["acacia", "akacie", "akacietræ", "akazie",
                                      "akazienholz"], ["akacie", "akazie"]),
    _c("bamboo", "Bamboo", "Bambus", ["bamboo", "bambus"], ["bambus"]),
    _c("rattan", "Rattan / wicker", "Rattan / flet",
       ["rattan", "wicker", "flet", "flettet", "geflecht", "korb", "kurv", "cane",
        "wienerflet", "wiener geflecht", "papercord", "seagrass", "søgræs", "seegras"],
       ["rattan", "flet", "geflecht"]),
    _c("metal", "Metal", "Metal",
       ["metal", "steel", "stål", "stahl", "iron", "jern", "eisen", "aluminium", "alu",
        "chrome", "krom", "chrom", "brass", "messing", "edelstahl"],
       ["metal", "stål", "stahl", "jern", "eisen"]),
    _c("glass", "Glass", "Glas", ["glass", "glas", "hærdet glas", "sicherheitsglas"],
       ["glas"]),
    _c("stone", "Stone / marble", "Sten / marmor",
       ["marble", "marmor", "stone", "sten", "stein", "granite", "granit", "travertine",
        "travertin", "terrazzo", "keramik", "ceramic", "concrete", "beton"],
       ["marmor", "sten", "stein"]),
    _c("velvet", "Velvet", "Velour / fløjl",
       ["velvet", "velour", "fløjl", "samt", "cord", "corduroy", "fløjlsstof"],
       ["velour", "fløjl", "samt"]),
    _c("boucle", "Bouclé", "Bouclé", ["boucle", "bouclé", "teddy"], ["boucle"]),
    _c("leather", "Leather", "Læder",
       ["leather", "læder", "leder", "echtleder", "semi-aniline", "aniline", "nubuck",
        "kunstleder", "kunstlæder", "faux leather", "pu leather"],
       ["læder", "leder"]),
    _c("linen", "Linen", "Hør", ["linen", "hør", "leinen"], ["leinen"]),
    _c("cotton", "Cotton", "Bomuld", ["cotton", "bomuld", "baumwolle"], ["bomuld"]),
    _c("wool", "Wool", "Uld", ["wool", "uld", "wolle", "uldstof"], ["uld", "wolle"]),
    _c("fabric", "Fabric", "Stof",
       ["fabric", "textile", "upholstered", "stof", "polstret", "stoff", "gepolstert",
        "webstoff", "polyester", "chenille"],
       ["stof", "stoff"]),
    _c("plastic", "Plastic", "Plast", ["plastic", "plast", "kunststoff", "polypropylen",
                                       "polypropylene"], ["plast", "kunststoff"]),
    _c("veneer", "Veneer / MDF", "Finér / MDF",
       ["veneer", "finér", "furnier", "mdf", "spånplade", "spanplatte", "melamin",
        "melamine", "laminat", "laminate"], ["finér", "furnier"]),
]

CONCEPT_GROUPS = {"category": CATEGORIES, "attribute": ATTRIBUTES,
                  "color": COLORS, "material": MATERIALS}
BY_ID = {(g, c.id): c for g, cs in CONCEPT_GROUPS.items() for c in cs}

# Danish/German/English inflection endings stripped before matching.
_ENDINGS = ("erne", "ene", "ers", "er", "en", "es", "e", "s", "n")


def _candidates(word: str) -> list[str]:
    out = [word]
    for end in _ENDINGS:
        if word.endswith(end) and len(word) - len(end) >= 3:
            out.append(word[: -len(end)])
    return out


class Matcher:
    """Finds concepts of one group in text, with phrase, compound and plural handling."""

    def __init__(self, concepts: list[Concept]):
        self.exact: dict[str, str] = {}
        self.phrases: list[tuple[list[str], str]] = []
        self.heads: list[tuple[str, str]] = []
        self.mods: list[tuple[str, str]] = []
        for c in concepts:
            for t in c.terms:
                toks = tokenize(t)
                if len(toks) == 1:
                    self.exact.setdefault(toks[0], c.id)
                elif toks:
                    self.phrases.append((toks, c.id))
            for h in c.heads:
                self.heads.append(("".join(tokenize(h)), c.id))
            for m in c.mods:
                self.mods.append(("".join(tokenize(m)), c.id))
        self.phrases.sort(key=lambda p: -len(p[0]))
        self.heads.sort(key=lambda p: -len(p[0]))

    def match_word(self, word: str) -> tuple[str, int] | None:
        """Best concept for a single word -> (concept_id, matched_length)."""
        best: tuple[str, int] | None = None
        for cand in _candidates(word):
            cid = self.exact.get(cand)
            if cid and (best is None or len(cand) > best[1]):
                best = (cid, len(cand) + 100)  # exact beats compound
        if best:
            return best
        for head, cid in self.heads:  # longest first
            for cand in _candidates(word):
                if cand.endswith(head) and len(cand) - len(head) >= 3:
                    return cid, len(head)
        return None

    def find_spans(self, text: str | list[str]) -> list[tuple[int, int, str]]:
        """All matches as (start_token, n_tokens, concept_id), in reading order."""
        toks = tokenize(text) if isinstance(text, str) else text
        hits: list[tuple[int, int, str]] = []
        used: set[int] = set()
        for ptoks, cid in self.phrases:
            n = len(ptoks)
            for i in range(len(toks) - n + 1):
                if any(j in used for j in range(i, i + n)):
                    continue
                window = toks[i:i + n]
                # allow plural on last phrase word ("dining tables")
                if window[:-1] == ptoks[:-1] and ptoks[-1] in _candidates(window[-1]):
                    hits.append((i, n, cid))
                    used.update(range(i, i + n))
        for i, w in enumerate(toks):
            if i in used:
                continue
            m = self.match_word(w)
            if m:
                hits.append((i, 1, m[0]))
                continue
            for mod, cid in self.mods:
                if w.startswith(mod) and len(w) - len(mod) >= 3:
                    hits.append((i, 1, cid))
                    break
        hits.sort()
        return hits

    def find(self, text: str | list[str]) -> list[tuple[int, str]]:
        """All matches as (token_position, concept_id), in reading order."""
        return [(i, cid) for i, _, cid in self.find_spans(text)]

    def ids(self, text: str | list[str]) -> list[str]:
        seen: list[str] = []
        for _, cid in self.find(text):
            if cid not in seen:
                seen.append(cid)
        return seen


CATEGORY_MATCHER = Matcher(CATEGORIES)
ATTRIBUTE_MATCHER = Matcher(ATTRIBUTES)
COLOR_MATCHER = Matcher(COLORS)
MATERIAL_MATCHER = Matcher(MATERIALS)
MATCHERS = {"category": CATEGORY_MATCHER, "attribute": ATTRIBUTE_MATCHER,
            "color": COLOR_MATCHER, "material": MATERIAL_MATCHER}


def concept_token(group: str, cid: str) -> str:
    """Synthetic, language-neutral token stored in the full-text index."""
    return f"zz{group[:3]}{cid.replace('_', '')}"

# Broader concepts a category also belongs to, so "table"/"bord"/"Tisch" also finds
# "spisebord" and "Couchtisch", and "chair"/"stol" finds "kontorstol".
CATEGORY_PARENTS: dict[str, list[str]] = {
    "dining_table": ["table"], "coffee_table": ["table"], "side_table": ["table"],
    "desk": ["table"], "nightstand": ["table"],
    "office_chair": ["chair"], "armchair": ["chair"],
    "sofa_bed": ["sofa", "bed"], "wardrobe": ["cabinet"], "sideboard": ["cabinet"],
    "tv_unit": ["cabinet"], "dresser": ["cabinet"],
}

# Attributes a category already implies; not required again when a query word
# carries both ("spisebord" = dining table, no separate "dining" clause needed).
CATEGORY_IMPLIES: dict[str, set[str]] = {
    "dining_table": {"dining"}, "office_chair": {"office"}, "desk": {"office"},
    "corner": set(),
}
