"""E02 값 정규화: 숫자·날짜·불리언·단위 환산.

모든 함수는 실패 시 NormalizeError(error_code, message)를 던진다. 오류 코드는 evaluation_protocol.md §2.4 체계를 쓴다.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation

_PLAIN = re.compile(r"^-?\d+(\.\d+)?$")
_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})*(\.\d+)?$")


class NormalizeError(Exception):
    def __init__(self, error_code: str, message: str, column: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.column = column  # 원인 값이 다른 열에 있으면 그 열 (예: 단위 차원 불일치 → 단위 열)


def is_empty(raw) -> bool:
    return raw is None or (isinstance(raw, str) and raw.strip() == "")


def as_text(raw) -> str:
    if isinstance(raw, float) and raw.is_integer():
        return str(int(raw))
    return str(raw).strip()


def parse_number(raw, number_format: str) -> Decimal:
    """number_format: 'plain'(1500.5) 또는 'thousands'(1,500.5 — 쉼표 없는 수도 허용)."""
    if isinstance(raw, bool):
        raise NormalizeError("ERR-NUMFMT", f"숫자가 아닌 값: {raw!r}")
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, float):
        return Decimal(repr(raw))
    s = as_text(raw)
    ok = _PLAIN.match(s) if number_format == "plain" else (_THOUSANDS.match(s) or _PLAIN.match(s))
    if not ok:
        raise NormalizeError("ERR-NUMFMT", f"숫자 형식 오류: {s!r} (형식 {number_format})")
    try:
        return Decimal(s.replace(",", ""))
    except InvalidOperation as exc:  # 정규식 통과 후에는 발생하지 않아야 함
        raise NormalizeError("ERR-NUMFMT", f"숫자 변환 실패: {s!r}") from exc


def parse_int(raw, number_format: str) -> int:
    d = parse_number(raw, number_format)
    if d != d.to_integral_value():
        raise NormalizeError("ERR-NUMFMT", f"정수가 아닌 값: {raw!r}")
    return int(d)


def parse_date(raw, date_format: str) -> dt.date:
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    s = as_text(raw)
    try:
        return dt.datetime.strptime(s, date_format).date()
    except ValueError as exc:
        raise NormalizeError("ERR-DATE", f"날짜 형식 오류 또는 존재하지 않는 날짜: {s!r} (형식 {date_format})") from exc


def parse_bool(raw, mapping: dict) -> bool:
    s = as_text(raw)
    if s not in mapping:
        raise NormalizeError("ERR-VALUE", f"허용되지 않는 값: {s!r} (허용 {sorted(mapping)})")
    return mapping[s]


def parse_enum(raw, mapping: dict) -> str:
    s = as_text(raw)
    if s not in mapping:
        raise NormalizeError("ERR-VALUE", f"허용되지 않는 값: {s!r} (허용 {sorted(mapping)})")
    return mapping[s]


def normalize_unit(raw, units: dict, labels: dict) -> str:
    s = labels.get(as_text(raw), as_text(raw))
    if s not in units:
        raise NormalizeError("ERR-UNIT", f"알 수 없는 단위: {raw!r}")
    return s


def to_standard(qty: Decimal, unit: str, units: dict, standard: dict) -> tuple[Decimal, str]:
    """qty를 같은 차원의 사내 표준 단위로 환산."""
    dim = units[unit]["dimension"]
    std = standard[dim]
    return qty * Decimal(units[unit]["factor"]) / Decimal(units[std]["factor"]), std


def price_to_standard(price: Decimal, unit: str, units: dict, standard: dict) -> Decimal:
    """단위당 가격(원/unit) → 원/표준단위."""
    std = standard[units[unit]["dimension"]]
    return price * Decimal(units[std]["factor"]) / Decimal(units[unit]["factor"])


def fmt(d: Decimal | None) -> str | None:
    if d is None:
        return None
    s = format(d.normalize(), "f")
    return "0" if s in ("-0", "") else s
