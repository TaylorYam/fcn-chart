"""代號正規化：把使用者輸入轉成 Yahoo Finance 代號。

規則：
- 4 碼且數字開頭（如 6758、130A）視為東證日股，自動補 `.T`。
- 已帶 `.T` 後綴者照用。
- 其餘視為美股；`BRK.B` 這類 class share 轉成 Yahoo 格式 `BRK-B`。
"""

import re

JP_CODE = re.compile(r"^\d[0-9A-Z]{3}$")
JP_SUFFIX = ".T"
US_TICKER = re.compile(r"^[A-Z][A-Z0-9]*([.-][A-Z0-9]+)?$")


class InvalidSymbolError(ValueError):
    pass


def normalize_symbol(raw: str) -> str:
    text = raw.strip().upper()
    if not text:
        raise InvalidSymbolError("代號不可空白")

    if text.endswith(JP_SUFFIX):
        code = text[: -len(JP_SUFFIX)]
        if JP_CODE.match(code):
            return text
        raise InvalidSymbolError(f"無法辨識的日股代號：{raw.strip()}")

    if JP_CODE.match(text):
        return text + JP_SUFFIX

    if US_TICKER.match(text):
        return text.replace(".", "-")

    raise InvalidSymbolError(f"無法辨識的代號：{raw.strip()}")


def display_ticker(yahoo_symbol: str) -> str:
    """表格用的代號：美股不加後綴（BRK-B → BRK.B），日股為「代號 JT」（Bloomberg 東證後綴）。"""
    if yahoo_symbol.endswith(JP_SUFFIX):
        return f"{yahoo_symbol[: -len(JP_SUFFIX)]} JT"
    return yahoo_symbol.replace("-", ".")
