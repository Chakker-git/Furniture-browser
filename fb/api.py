from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .currency import to_eur
from .lexicon import ATTRIBUTES, CATEGORIES, COLORS, MATERIALS

WEB = Path(__file__).resolve().parent / "web"


def create_app(db_path: str | None = None) -> FastAPI:
    conn = db.connect(db_path or os.environ.get("FB_DB", "data/furniture.db"))
    app = FastAPI(title="Furniture Browser", version="0.1.0")

    @app.get("/api/search")
    def search(
        q: str = "",
        country: list[str] = Query(default=[]),
        retailer: list[str] = Query(default=[]),
        category: list[str] = Query(default=[]),
        color: list[str] = Query(default=[]),
        material: list[str] = Query(default=[]),
        wmin: float | None = None, wmax: float | None = None,
        dmin: float | None = None, dmax: float | None = None,
        hmin: float | None = None, hmax: float | None = None,
        pmin: float | None = None, pmax: float | None = None,
        seats_min: float | None = None, seats_max: float | None = None,
        in_stock: bool = False, has_dimensions: bool = False,
        currency: str = "EUR",
        sort: str = "relevance",
        page: int = Query(1, ge=1), per_page: int = Query(24, ge=1, le=100),
    ):
        filters = {
            "country": country, "retailer_id": retailer, "category": category,
            "color": color, "material": material, "wmin": wmin, "wmax": wmax,
            "dmin": dmin, "dmax": dmax, "hmin": hmin, "hmax": hmax,
            "pmin_eur": to_eur(pmin, currency), "pmax_eur": to_eur(pmax, currency),
            "seats_min": seats_min, "seats_max": seats_max,
            "in_stock": in_stock, "has_dimensions": has_dimensions,
        }
        return db.search(conn, q, filters, sort=sort, page=page, per_page=per_page,
                         currency=currency)

    @app.get("/api/product/{pid}")
    def product(pid: int, currency: str = "EUR"):
        p = db.product_detail(conn, pid, currency)
        if not p:
            raise HTTPException(404, "not found")
        return p

    @app.get("/api/meta")
    def meta():
        def lab(cs, hexes=False):
            return [{"id": c.id, "en": c.label_en, "da": c.label_da,
                     **({"hex": c.hex} if hexes else {})} for c in cs]
        return {"categories": lab(CATEGORIES), "attributes": lab(ATTRIBUTES),
                "colors": lab(COLORS, True), "materials": lab(MATERIALS),
                "retailers": [{"id": r["id"], "name": r["name"], "country": r["country"]}
                              for r in db.retailer_stats(conn)]}

    @app.get("/api/retailers")
    def retailers():
        return db.retailer_stats(conn)

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    return app
