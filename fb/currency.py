"""Currency conversion. DKK is pegged to EUR (ERM II central rate 7.46038),
so a fixed rate is accurate to well under 1% for filtering purposes.
Override other rates via FB_RATES='{"SEK": 11.2}' (units per EUR)."""
from __future__ import annotations

import json
import os

PER_EUR = {"EUR": 1.0, "DKK": 7.46038}
PER_EUR.update({k.upper(): float(v) for k, v in
                json.loads(os.environ.get("FB_RATES", "{}")).items()})


def to_eur(amount: float | None, currency: str | None) -> float | None:
    if amount is None:
        return None
    rate = PER_EUR.get((currency or "EUR").upper())
    return round(amount / rate, 2) if rate else None


def from_eur(amount: float | None, currency: str) -> float | None:
    if amount is None:
        return None
    rate = PER_EUR.get(currency.upper())
    return round(amount * rate, 2) if rate else None
