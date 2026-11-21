from __future__ import annotations

import tomllib
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "retailers.toml"


def load(path: str | Path = DEFAULT_PATH) -> list[dict]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    out = []
    for r in data.get("retailer", []):
        merged = {**defaults, "enabled": True, "platform": "auto", **r}
        missing = {"id", "name", "country", "base_url"} - merged.keys()
        if missing:
            raise ValueError(f"retailer {r.get('id', '?')} missing {sorted(missing)}")
        out.append(merged)
    ids = [r["id"] for r in out]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate retailer ids: {sorted(dupes)}")
    return out
