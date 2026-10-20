"""E02 채점기 — 파서 출력과 정답 비교 (파서 구현과 분리).

src/parsers, src/normalization을 import하지 않는다. 정답은 다음에서만 읽는다:
  data/canonical/ground_truth_v2.json, vendor_row_map_v1.csv, vendor_id_map_v1.csv, vendor_column_map_v1.json,
  injected_errors_v1.json, 그리고 원본 위치 검증을 위한 업체 파일 자체.
판정 규칙은 docs/evaluation_protocol.md §1.2, §3.2, §4, §4.1을 따른다.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CANON = DATA / "canonical"

REQUIRED = {
    "Product": ["product_id", "product_name", "product_type", "base_unit"],
    "Material": ["material_id", "material_name", "base_unit"],
    "Supplier": ["supplier_id", "supplier_name"],
    "SupplierMaterial": ["supplier_id", "material_id", "lead_time_days", "is_preferred"],
    "BOM": ["bom_id", "product_id", "bom_version", "status", "is_active", "valid_from", "min_qty", "base_qty"],
    "BOMLine": ["bom_id", "line_no", "component_type", "qty_per", "unit"],
    "Order": ["order_id", "product_id", "order_qty", "unit", "order_date", "due_date", "status"],
    "Inventory": ["item_type", "item_id", "as_of_date", "on_hand_qty", "unit"],
    "Resource": ["resource_id", "resource_name", "resource_type", "regular_hours_per_day"],
    "Operation": ["operation_id", "product_id", "sequence_no", "resource_id", "run_time_per_unit_h"],
}
KEYS = {"Product": ("product_id",), "Material": ("material_id",), "Supplier": ("supplier_id",),
        "SupplierMaterial": ("supplier_id", "material_id"), "BOM": ("bom_id",), "BOMLine": ("bom_id", "line_no"),
        "Order": ("order_id",), "Inventory": ("item_type", "item_id"), "Resource": ("resource_id",), "Operation": ("operation_id",)}
QTY = {"safety_stock_qty", "on_hand_qty", "allocated_qty", "on_order_qty", "order_qty", "min_order_qty", "qty_per"}
UNIT = {"base_unit", "unit"}
DATE = {"valid_from", "valid_to", "order_date", "due_date", "as_of_date", "expected_receipt_date"}
NUM = {"unit_cost", "outsourcing_unit_cost", "min_qty", "max_qty", "base_qty", "scrap_rate", "lead_time_days",
       "manuf_lead_time_days", "regular_hours_per_day", "overtime_hours_per_day_max", "cost_per_hour", "overtime_cost_per_hour",
       "run_time_per_unit_h", "setup_time_h", "line_no", "sequence_no"}
IDS = {"product_id", "material_id", "supplier_id", "resource_id", "order_id", "bom_id", "component_material_id",
       "component_product_id", "item_id", "operation_id"}
# E01 생성 명세(scripts/e01_generate.py의 Vendor B 시트 정의)에서 옮긴 병합 헤더 정답
B_HEADER = {
    "제품": [("기본정보", ["품목코드", "품목명", "구분", "단위"]), ("관리기준", ["안전재고", "생산리드타임(일)", "외주가능", "외주단가(원)"])],
    "자재": [("기본정보", ["자재코드", "자재명", "단위"]), ("관리기준", ["단가(원/단위)", "안전재고"])],
    "공급조건": [("공급사", ["공급사코드", "공급사명"]), ("공급조건", ["자재코드", "리드타임(일)", "최소주문량", "우선공급"])],
    "BOM": [("BOM 정보", ["BOM번호", "모품목코드", "버전", "상태", "활성"]), ("유효조건", ["시작일", "종료일", "최소수량", "최대수량", "사이트"]),
            ("구성", ["기준수량", "순번", "자품목구분", "자품목코드", "소요량", "단위", "손실률(%)"])],
}
# 파서 단계에서 구조적으로 판단할 수 없는 업무 규칙 오류 → E05 검증 대상
E05_SCOPE = {
    "E01-ERR-009": "납기일 < 주문일: 두 값 모두 형식은 정상이며 레코드 업무 규칙(QR-04 ②) 위반",
    "E01-ERR-010": "BOM 순환: 여러 BOM에 걸친 그래프 검사(QR-05)",
    "E01-ERR-011": "BOM 버전 유효조건 중복: 버전 간 기간·수량·사이트 비교(QR-06 ①)",
    "E01-ERR-012": "할당 > 보유: 두 수량 모두 형식은 정상이며 재고 업무 규칙(QR-07 ②) 위반",
}


def dec(x) -> Decimal | None:
    return None if x is None else Decimal(str(x))


def same_num(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return dec(a) == dec(b)


class Truth:
    def __init__(self) -> None:
        gt = json.loads((CANON / "ground_truth_v2.json").read_text(encoding="utf-8"))
        self.E = gt["entities"]
        self.unit = {u["unit_code"]: u for u in self.E["Unit"]}
        self.base = {**{p["product_id"]: p["base_unit"] for p in self.E["Product"]},
                     **{m["material_id"]: m["base_unit"] for m in self.E["Material"]}}
        self.by_uid = {r["record_uid"]: (ent, r) for ent, rows in self.E.items() for r in rows}
        with open(CANON / "vendor_row_map_v1.csv", encoding="utf-8", newline="") as f:
            self.row_map = list(csv.DictReader(f))
        with open(CANON / "vendor_id_map_v1.csv", encoding="utf-8", newline="") as f:
            self.id_map = list(csv.DictReader(f))
        self.colmap = json.loads((CANON / "vendor_column_map_v1.json").read_text(encoding="utf-8"))
        self.injected = json.loads((CANON / "injected_errors_v1.json").read_text(encoding="utf-8"))["errors"]

    def to_base(self, qty, unit: str, item: str) -> Decimal | None:
        if qty is None:
            return None
        return dec(qty) * dec(self.unit[unit]["to_base_factor"]) / dec(self.unit[self.base[item]]["to_base_factor"])

    def expected_values(self, ent: str, r: dict) -> dict:
        """정답 레코드를 '사내 표준 단위' 의미로 변환 (파서 출력과 같은 기준)."""
        v = {k: r[k] for k in r if k not in ("record_uid", "origin_class", "line_type")}
        if ent == "Product":
            v["safety_stock_qty"] = dec(r["safety_stock_qty"])
        elif ent == "Material":
            v["safety_stock_qty"] = dec(r["safety_stock_qty"])
        elif ent == "BOMLine":
            comp = r["component_material_id"] or r["component_product_id"]
            v["qty_per"] = self.to_base(r["qty_per"], r["unit"], comp)
            v["unit"] = self.base[comp]
        elif ent == "Inventory":
            for f in ("on_hand_qty", "allocated_qty", "on_order_qty"):
                v[f] = self.to_base(r[f], r["unit"], r["item_id"])
            v["unit"] = self.base[r["item_id"]]
        elif ent == "Order":
            v["order_qty"] = self.to_base(r["order_qty"], r["unit"], r["product_id"])
            v["unit"] = self.base[r["product_id"]]
        return v


def field_ok(f: str, got, want) -> bool:
    if f in QTY or f in NUM:
        return same_num(got, want)
    return got == want


def read_cells(path: Path, sheet: str, encoding: str | None):
    if sheet:
        wb = openpyxl.load_workbook(path, data_only=True)
        rows = [[c.value for c in r] for r in wb[sheet].iter_rows()]
        wb.close()
        return rows
    return list(csv.reader(io.StringIO(path.read_bytes().decode(encoding), newline="")))


def grade_dataset(T: Truth, outputs: dict[str, dict], dataset: str) -> dict:
    """dataset = 'clean' | 'invalid'. outputs: vendor → 파서 출력."""
    prefix = "" if dataset == "clean" else "invalid/"
    per_file = []
    trace_cache = {}
    enc_of = {f["file"]: f.get("encoding") for f in T.colmap["files"] if f["format"] == "csv"}
    for vendor, out in outputs.items():
        recs_by_file = defaultdict(list)
        for ent, rows in out["entities"].items():
            for r in rows:
                s = r["source"]
                recs_by_file[(s["file"], s.get("sheet", ""))].append(r)
        for finfo in out["files"]:
            rel, sheet = finfo["file"], finfo["sheet"]
            clean_rel = rel[len(prefix):]
            m = {"dataset": dataset, "vendor": vendor, "file": clean_rel, "sheet": sheet, "entity": finfo["entity"],
                 "run_ok": finfo["run_ok"], "output_generated": finfo["output_generated"],
                 "encoding_detected": finfo.get("encoding", ""), "encoding_expected": enc_of.get(clean_rel, "") if not sheet else "",
                 "delimiter": finfo.get("delimiter", ""), "header_rows": finfo.get("header_rows", 1 if not sheet else "")}
            expected = [x for x in T.row_map if x["vendor"] == vendor and x["file"] == clean_rel and x["sheet"] == sheet]
            parsed = recs_by_file[(rel, sheet)]

            def find(ent, row):
                for r in parsed:
                    if r["entity"] != ent:
                        continue
                    s = r["source"]
                    if s.get("row") == row or row in s.get("rows", []):
                        return r
                return None

            seen = set()
            c = Counter()
            mism = []
            for x in expected:
                ent, row = x["entity"], int(x["row_number"])
                if (ent, x["canonical_key"]) in seen:
                    continue  # BOM 헤더처럼 여러 행이 같은 레코드를 가리키는 경우 1회만
                seen.add((ent, x["canonical_key"]))
                c["records_expected"] += 1
                pr = find(ent, row)
                cent, crec = T.by_uid[x["canonical_record_uid"]]
                if pr is None:
                    c["records_missing"] += 1
                    mism.append({"entity": ent, "key": x["canonical_key"], "issue": "레코드 누락", "row": row})
                    continue
                want = T.expected_values(cent, crec)
                for f, got in pr["values"].items():
                    if f.startswith("_") or f not in want:
                        continue
                    ok = field_ok(f, got, want[f])
                    c["fields_total"] += 1
                    c["fields_match"] += ok
                    if f in REQUIRED.get(ent, []):
                        c["required_total"] += 1
                        c["required_match"] += ok
                    cat = "qty_unit" if (f in QTY or f in UNIT) else "date" if f in DATE else "number" if f in NUM else "id" if f in IDS else None
                    if cat:
                        c[f"{cat}_total"] += 1
                        c[f"{cat}_match"] += ok
                    if not ok:
                        mism.append({"entity": ent, "key": x["canonical_key"], "field": f, "got": str(got), "want": str(want[f]), "row": row})
                # 원본 위치 역추적: 행이 정답 대응표와 같고, 기록된 열·원문이 실제 파일 셀과 같은가
                cells = pr["source"].get("cells")
                if ent != "BOM" and cells:
                    c["trace_total"] += 1
                    key = (rel, sheet)
                    if key not in trace_cache:
                        trace_cache[key] = read_cells(DATA / rel, sheet, enc_of.get(clean_rel))
                    rows = trace_cache[key]
                    hdr_row = rows[1] if (sheet and vendor == "B") else rows[0]
                    rr = pr["source"]["row"]
                    ok = rr == row
                    for f, cell in cells.items():
                        ci = cell["col_index"] - 1
                        actual = rows[rr - 1][ci] if ci < len(rows[rr - 1]) else None
                        actual_s = None if actual is None else (str(int(actual)) if isinstance(actual, float) and actual.is_integer() else str(actual).strip())
                        if hdr_row[ci] != cell["column"] or actual_s != cell["raw"]:
                            ok = False
                    c["trace_success"] += ok
            keys = Counter((r["entity"], json.dumps([r["values"].get(k) for k in KEYS.get(r["entity"], ())]))
                           for r in parsed)
            c["records_duplicate"] = sum(n - 1 for n in keys.values() if n > 1)
            c["records_parsed"] = len(parsed)
            c["records_extra"] = sum(1 for r in parsed if r["entity"] != "BOM" and not any(
                int(x["row_number"]) == r["source"].get("row") and x["entity"] == r["entity"] for x in expected))
            m.update(c)
            m["_mismatches"] = mism
            per_file.append(m)
    return {"per_file": per_file}


def grade_headers(outputs: dict) -> list[dict]:
    rows = []
    for vendor, out in outputs.items():
        for h in out["headers"]:
            if not h["sheet"] or vendor != "B":
                continue
            exp = [(g, n) for g, names in B_HEADER[h["sheet"]] for n in names]
            got = [(c["group"], c["name"]) for c in h["header"]][:len(exp)]
            correct = sum(1 for a, b in zip(got, exp) if a == b)
            rows.append({"file": h["file"], "sheet": h["sheet"], "header_rows": h["header_rows"],
                         "cells_total": len(exp), "cells_correct": correct})
    return rows


def related_rows(e: dict) -> set[int]:
    rows = {e["row_number"]}
    if e["error_code"] == "ERR-DUPID":
        path = DATA / e["file"]
        enc = "utf-8-sig" if path.read_bytes().startswith(b"\xef\xbb\xbf") else "utf-8"
        data = list(csv.reader(io.StringIO(path.read_bytes().decode(enc), newline="")))
        col = data[0].index(e["field"])
        val = data[e["row_number"] - 1][col]
        rows |= {n for n, r in enumerate(data[1:], start=2) if r[col] == val}
    return rows


def grade_detection(T: Truth, outputs: dict, dataset: str, cells_checked: int, rows_checked: int) -> dict:
    reports = [d for out in outputs.values() for d in out["diagnostics"] if d["severity"] == "error"]
    warnings = [d for out in outputs.values() for d in out["diagnostics"] if d["severity"] != "error"]
    inj = T.injected if dataset == "invalid" else []
    rel = {e["error_id"]: related_rows(e) for e in inj}
    matched_report = set()
    per_error = []
    for e in inj:
        hits = [i for i, d in enumerate(reports) if d["file"] == e["file"] and (d["sheet"] or "") == (e["sheet"] or "")
                and d["row"] in rel[e["error_id"]] and d["column"] == e["field"] and d["error_code"] == e["error_code"]]
        partial = [i for i, d in enumerate(reports) if i not in hits and d["file"] == e["file"] and (d["sheet"] or "") == (e["sheet"] or "")
                   and d["row"] in rel[e["error_id"]]]
        matched_report |= set(hits) | set(partial)
        per_error.append({"error_id": e["error_id"], "error_code": e["error_code"], "file": e["file"], "sheet": e["sheet"],
                          "row": e["row_number"], "field": e["field"], "scope": "E05" if e["error_id"] in E05_SCOPE else "E02",
                          "detected": bool(hits), "reports": len(hits), "duplicate_reports": max(0, len(hits) - 1),
                          "partial": len(partial), "e05_reason": E05_SCOPE.get(e["error_id"])})
    fps = [d for i, d in enumerate(reports) if i not in matched_report]
    fp_fields = {(d["file"], d["sheet"], d["row"], d["column"]) for d in fps}
    fp_rows = {(d["file"], d["sheet"], d["row"]) for d in fps}
    inj_fields = {(e["file"], e["sheet"], r, e["field"]) for e in inj for r in rel[e["error_id"]]}
    inj_rows = {(e["file"], e["sheet"], r) for e in inj for r in rel[e["error_id"]]}
    by_type = defaultdict(lambda: Counter())
    for p in per_error:
        t = by_type[p["error_code"]]
        t["injected"] += 1
        t["detected"] += p["detected"]
        t["in_e02_scope"] += p["scope"] == "E02"
        t["detected_in_scope"] += p["detected"] and p["scope"] == "E02"
    for d in fps:
        by_type[d["error_code"]]["false_positive_reports"] += 1
    return {
        "dataset": dataset, "reports": len(reports), "warnings": len(warnings),
        "warning_codes": dict(Counter(w["error_code"] for w in warnings)),
        "per_error": per_error, "by_type": {k: dict(v) for k, v in sorted(by_type.items())},
        "false_positives": fps,
        "field_fp": {"numerator": len(fp_fields), "denominator": cells_checked - len(inj_fields)},
        "record_fp": {"numerator": len(fp_rows), "denominator": rows_checked - len(inj_rows)},
    }


def rate(num: int, den: int) -> str:
    return "N/A(분모 0)" if den == 0 else f"{num / den:.3f} ({num}/{den})"
