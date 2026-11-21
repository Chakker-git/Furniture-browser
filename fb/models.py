from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawProduct:
    """What an adapter hands over: as close to the source as possible."""
    retailer_id: str
    external_id: str
    url: str
    title: str
    description: str = ""
    price: float | None = None
    currency: str | None = None
    image_url: str | None = None
    brand: str | None = None
    gtin: str | None = None
    sku: str | None = None
    in_stock: bool | None = None
    group_key: str | None = None          # variants of one product share this
    source_category: str | None = None    # retailer's own category/breadcrumb/product_type
    color_raw: str | None = None          # structured color field (variant option, feed column)
    material_raw: str | None = None
    # structured dimensions in cm when the source provides them
    width_cm: float | None = None
    depth_cm: float | None = None
    height_cm: float | None = None
    dimensions_raw: str | None = None     # e.g. feed "dimensions" column
    tags: list[str] = field(default_factory=list)


@dataclass
class Product:
    retailer_id: str
    country: str
    external_id: str
    group_key: str
    url: str
    title: str
    description: str
    brand: str | None
    category: str | None
    attributes: list[str]
    colors: list[str]
    color_raw: str | None
    materials: list[str]
    width_cm: float | None
    depth_cm: float | None
    height_cm: float | None
    diameter_cm: float | None
    seats: float | None
    price: float | None
    currency: str | None
    price_eur: float | None
    image_url: str | None
    gtin: str | None
    sku: str | None
    in_stock: bool | None
