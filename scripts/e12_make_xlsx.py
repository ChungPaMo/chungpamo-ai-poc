"""E12 합성 XLSX 시험 파일 + 정답 생성 (XlsxWriter, 결정적).

    .\\.venv\\Scripts\\python.exe scripts\\e12_make_xlsx.py

- 출력: data/e12/X12-01_orders.xlsx, data/canonical/e12/xlsx_truth_v1.json (정답은 이 생성기 명세 — 어느 읽기 도구의 출력도 쓰지 않음)
- 시험 항목: 일반 주문 표, 여러 시트, 병합 셀, 날짜, 금액·수량, 문자열로 저장된 숫자, 수식과 캐시된 계산값, 숨긴 행·열, 빈 셀, 잘못된 입력값
- 값은 E01 정답셋의 제품 코드·단위를 쓴 합성 값이다 (실제 기업 데이터 아님).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import xlsxwriter

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "data" / "e12" / "X12-01_orders.xlsx"
XLSX_NOCACHE = ROOT / "data" / "e12" / "X12-02_orders_no_formula_cache.xlsx"
TRUTH = ROOT / "data" / "canonical" / "e12" / "xlsx_truth_v1.json"
EPOCH = dt.date(1899, 12, 30)


def col(c: int) -> str:
    return chr(ord("A") + c)


def build(path=XLSX, cache=True):
    """cache=False: 수식 셀에 계산 결과 캐시를 넣지 않는다 (XlsxWriter는 0을 기록) — 다른 도구로 저장되어 캐시가 없어진 파일을 흉내낸 변형."""
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path), {"strings_to_numbers": False, "strings_to_formulas": False})
    wb.set_properties({"title": "E12 synthetic orders", "author": "chungpamo-poc (synthetic)", "created": dt.datetime(2026, 10, 23, 9, 0, 0)})
    date_f = wb.add_format({"num_format": "yyyy-mm-dd"})
    money_f = wb.add_format({"num_format": "#,##0"})
    cells, merges, hidden_rows, hidden_cols = [], [], [], []

    def put(ws, sheet, r, c, kind, value, display=None, formula=None, fmt=None, note=None):
        ref = f"{col(c)}{r + 1}"
        if kind == "text":
            ws.write_string(r, c, value, fmt)
        elif kind == "number":
            ws.write_number(r, c, value, fmt)
        elif kind == "date":
            ws.write_datetime(r, c, dt.datetime.combine(value, dt.time()), fmt)
        elif kind == "formula":
            if cache:
                ws.write_formula(r, c, formula, fmt, value)
            else:
                ws.write_formula(r, c, formula, fmt)             # 캐시값 인수 없음 → XlsxWriter 기본 0
        cells.append({"sheet": sheet, "cell": ref, "kind": kind, "value": value.isoformat() if kind == "date" else value, "display": display if display is not None else
                      (value.isoformat() if kind == "date" else str(value)), "formula": formula, "note": note})

    # --- 시트 1: 주문 (일반 표, 날짜, 금액·수량, 문자열 숫자, 잘못된 값, 빈 셀, 수식, 숨긴 행·열)
    ws = wb.add_worksheet("Orders")
    head = ["주문번호", "제품코드", "수량", "단위", "단가", "금액", "주문일", "납기일", "비고"]
    for c, h in enumerate(head):
        put(ws, "Orders", 0, c, "text", h)
    rows = [("SO260101", "FG001", 50, "EA", 120000, dt.date(2026, 11, 10), dt.date(2026, 11, 25), None),
            ("SO260102", "FG002", "30", "EA", 95000, dt.date(2026, 11, 11), dt.date(2026, 11, 28), "수량이 문자열로 저장됨"),
            ("SO260103", "FG003", "1O50", "EA", 210000, dt.date(2026, 11, 12), dt.date(2026, 12, 2), "잘못된 수량 (영문자 O)"),
            ("SO260104", "SF001", 120, "EA", 40000, dt.date(2026, 11, 13), dt.date(2026, 11, 30), "숨긴 행"),
            ("SO260105", "FG001", 15, "EA", None, dt.date(2026, 11, 14), dt.date(2026, 12, 1), "단가 빈 셀")]
    for i, (oid, pid, qty, unit, price, od, du, memo) in enumerate(rows):
        r = i + 1
        put(ws, "Orders", r, 0, "text", oid)
        put(ws, "Orders", r, 1, "text", pid)
        put(ws, "Orders", r, 2, "text" if isinstance(qty, str) else "number", qty, note="number_stored_as_text" if qty == "30" else ("invalid_number" if qty == "1O50" else None))
        put(ws, "Orders", r, 3, "text", unit)
        if price is not None:
            put(ws, "Orders", r, 4, "number", price, display=f"{price:,}", fmt=money_f)
        else:
            cells.append({"sheet": "Orders", "cell": f"E{r + 1}", "kind": "blank", "value": None, "display": "", "formula": None, "note": "blank"})
        q = int(qty) if isinstance(qty, int) else (int(qty) if qty.isdigit() else None)
        if q is not None and price is not None and isinstance(qty, int):
            amount = q * price
            put(ws, "Orders", r, 5, "formula", amount, display=f"{amount:,}", formula=f"=C{r + 1}*E{r + 1}", fmt=money_f)
        elif qty == "30":
            # 텍스트 숫자 × 숫자: Excel은 "30"*95000 = 2,850,000 으로 계산 (텍스트 숫자를 산술에서 자동 변환)
            put(ws, "Orders", r, 5, "formula", 30 * price, display=f"{30 * price:,}", formula=f"=C{r + 1}*E{r + 1}", fmt=money_f, note="text_number_in_formula")
        elif qty == "1O50":
            put(ws, "Orders", r, 5, "formula", "#VALUE!", display="#VALUE!", formula=f"=C{r + 1}*E{r + 1}", fmt=money_f, note="formula_error")
        else:
            put(ws, "Orders", r, 5, "formula", 0, display="0", formula=f"=C{r + 1}*E{r + 1}", fmt=money_f, note="blank_operand")
        put(ws, "Orders", r, 6, "date", od, fmt=date_f)
        put(ws, "Orders", r, 7, "date", du, fmt=date_f)
        if memo:
            put(ws, "Orders", r, 8, "text", memo)
    ws.set_row(4, None, None, {"hidden": True})
    hidden_rows.append({"sheet": "Orders", "row": 5})
    ws.set_column(8, 8, None, None, {"hidden": True})
    hidden_cols.append({"sheet": "Orders", "col": "I"})
    total = 50 * 120000 + 30 * 95000 + 120 * 40000 + 0
    ws.merge_range(7, 0, 7, 4, "합계 (수식 결과는 캐시값)", None)
    cells.append({"sheet": "Orders", "cell": "A8", "kind": "text", "value": "합계 (수식 결과는 캐시값)", "display": "합계 (수식 결과는 캐시값)", "formula": None, "note": "merged A8:E8"})
    merges.append({"sheet": "Orders", "range": "A8:E8"})
    put(ws, "Orders", 7, 5, "formula", total, display=f"{total:,}", formula="=SUM(F2,F3,F5,F6)", fmt=money_f, note="SUM 일부 (오류 셀 F4 제외)")
    # --- 시트 2: 병합 머리글이 있는 BOM 표 (가로·세로 병합)
    bm = wb.add_worksheet("BOM")
    bm.merge_range(0, 0, 0, 1, "구성품", None)
    bm.merge_range(0, 2, 0, 3, "소요량", None)
    merges += [{"sheet": "BOM", "range": "A1:B1"}, {"sheet": "BOM", "range": "C1:D1"}]
    cells += [{"sheet": "BOM", "cell": "A1", "kind": "text", "value": "구성품", "display": "구성품", "formula": None, "note": "merged A1:B1"},
              {"sheet": "BOM", "cell": "C1", "kind": "text", "value": "소요량", "display": "소요량", "formula": None, "note": "merged C1:D1"}]
    for c, h in enumerate(["코드", "명칭", "수량", "단위"]):
        put(bm, "BOM", 1, c, "text", h)
    bm.merge_range(2, 4, 3, 4, "FG001 V1", None)
    merges.append({"sheet": "BOM", "range": "E3:E4"})
    cells.append({"sheet": "BOM", "cell": "E3", "kind": "text", "value": "FG001 V1", "display": "FG001 V1", "formula": None, "note": "merged E3:E4 (세로)"})
    for i, (code, name, q, u) in enumerate([("M001", "강판", 1.2, "kg"), ("M006", "전원 케이블", 1, "EA")]):
        put(bm, "BOM", 2 + i, 0, "text", code)
        put(bm, "BOM", 2 + i, 1, "text", name)
        put(bm, "BOM", 2 + i, 2, "number", q)
        put(bm, "BOM", 2 + i, 3, "text", u)
    # --- 시트 3: 제품 마스터 (여러 시트, 다른 시트 참조 수식)
    ms = wb.add_worksheet("Products")
    for c, h in enumerate(["제품코드", "제품명", "안전재고"]):
        put(ms, "Products", 0, c, "text", h)
    for i, (p, n, s) in enumerate([("FG001", "가정용 히터 A", 50), ("FG002", "가정용 히터 B", 30), ("FG003", "산업용 송풍기 C", 40)]):
        put(ms, "Products", i + 1, 0, "text", p)
        put(ms, "Products", i + 1, 1, "text", n)
        put(ms, "Products", i + 1, 2, "number", s)
    put(ms, "Products", 4, 2, "formula", 120, formula="=SUM(C2:C4)", note="같은 시트 합")
    put(ms, "Products", 5, 2, "formula", 50, formula="=Orders!C2", note="다른 시트 참조")
    wb.close()
    return cells, merges, hidden_rows, hidden_cols


def main():
    cells, merges, hidden_rows, hidden_cols = build(XLSX, True)
    build(XLSX_NOCACHE, False)
    truth = {"schema": "chungpamo.e12_xlsx_truth", "version": "v1", "created": "2026-10-23", "file": XLSX.relative_to(ROOT).as_posix(),
             "sha256": hashlib.sha256(XLSX.read_bytes()).hexdigest(),
             "variant_no_formula_cache": {"file": XLSX_NOCACHE.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(XLSX_NOCACHE.read_bytes()).hexdigest(),
                                          "note": "같은 셀·수식, 수식 캐시값만 0 — 정답 값은 X12-01과 같은 계산 결과"},
             "status": "GENERATED (생성기 명세 — 생성 정답)",
             "sheets": ["Orders", "BOM", "Products"], "cells": cells, "merges": merges, "hidden_rows": hidden_rows, "hidden_cols": hidden_cols,
             "note": "수식 셀의 value는 생성 시 함께 저장한 캐시 계산값. display는 Excel 표시 형식 기준 기대 문자열"}
    TRUTH.parent.mkdir(parents=True, exist_ok=True)
    TRUTH.write_text(json.dumps(truth, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print({"xlsx_sha256": truth["sha256"], "no_cache_sha256": truth["variant_no_formula_cache"]["sha256"], "cells": len(cells), "merges": len(merges)})


if __name__ == "__main__":
    main()
