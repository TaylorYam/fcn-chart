"""KO/K/KI 價位計算。"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

LEVEL_NAMES = ("KO", "K", "KI")

# 依幣別決定價位顯示的小數位數；未列出者用 2 位。
CURRENCY_DECIMALS = {"JPY": 0}


@dataclass(frozen=True)
class Level:
    name: str
    pct: float
    price: float


def price_decimals(currency: str) -> int:
    return CURRENCY_DECIMALS.get(currency.upper(), 2)


def compute_levels(
    ref_close: float,
    pcts: dict[str, float | None],
    currency: str,
) -> list[Level]:
    """依期初價與百分比算出各條線價位；百分比為 None 的線不畫。"""
    if ref_close <= 0:
        raise ValueError("期初價必須大於 0")

    decimals = price_decimals(currency)
    levels = []
    for name in LEVEL_NAMES:
        pct = pcts.get(name)
        if pct is None:
            continue
        if pct <= 0:
            raise ValueError(f"{name} 百分比必須大於 0")
        levels.append(
            Level(name=name, pct=pct, price=round_half_up(ref_close * pct / 100, decimals))
        )
    return levels


def round_half_up(value: float, decimals: int) -> float:
    """四捨五入（Python 內建 round 是銀行家捨入，且受浮點誤差影響）。"""
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP))
