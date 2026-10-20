"""E01 합성 데이터 생성: canonical 엔터티 + UCI 배분 SalesHistory + 생산계획안 + Vendor A/B 파일.

    .\\.venv\\Scripts\\python.exe scripts\\e01_generate.py [--out-root DIR]

- 마스터 값은 아래 SPEC 상수에 명시적 가정으로 둔다 (실제 기업 값 아님). 근거·가정 ID는 schema §1.1 ASM-xx.
- 난수는 UCI 일별 총주문을 제품에 배분하는 비율에만 쓰며 시드를 고정한다 (e01_common.SEED).
- 기대값(정답) 계산은 하지 않는다 → e01_expected.py.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import random
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font

from e01_common import (DATASET_ID, DATASET_VERSION, FIXED_ZIP_TIME, GT_VERSION, SEED, D, Paths, fmt, normalize_xlsx,
                        record_uid, sha256_file, write_json)
from e01_models import validate_entities

# ---------------------------------------------------------------------------
# SPEC — 명시적 가정값 (KRW, 단위 EA/kg/g/h)
# ---------------------------------------------------------------------------
REFERENCE_DATE = dt.date(2026, 11, 15)          # 재고 기준일 = 계획 시작 전날 (ASM-13)
HORIZON_START = dt.date(2026, 11, 16)           # 월요일
HORIZON_WEEKS = 4                               # ASM-08
HORIZON_END = HORIZON_START + dt.timedelta(days=7 * HORIZON_WEEKS - 1)
UCI_FIRST_DATE = dt.date(2026, 8, 5)            # UCI 1행(수요일)에 붙이는 합성 날짜 (원본에 날짜 없음)

UNITS = [  # unit_code, dimension, base_unit_code, to_base_factor
    ("EA", "COUNT", "EA", "1"), ("kg", "MASS", "kg", "1"), ("g", "MASS", "kg", "0.001"), ("h", "TIME", "h", "1"),
]
PRODUCTS = [  # id, name, type, base_unit, safety_stock, manuf_lt_days, outsourcing_allowed, outsourcing_unit_cost
    ("FG001", "가정용 히터 A", "FINISHED", "EA", "50", 3, False, None),
    ("FG002", "가정용 히터 B", "FINISHED", "EA", "30", 3, False, None),
    ("FG003", "산업용 송풍기 C", "FINISHED", "EA", "40", 2, True, "38000"),
    ("SF001", "히터 코어 모듈", "SEMI_FINISHED", "EA", "20", 2, False, None),
    ("SF002", "모터 하우징 조립품", "SEMI_FINISHED", "EA", "10", 2, False, None),
]
MATERIALS = [  # id, name, base_unit, unit_cost(KRW/base_unit), safety_stock
    ("M001", "강판", "kg", "1200", "50"), ("M002", "알루미늄 판재", "kg", "3500", "30"),
    ("M003", "구리선", "kg", "11000", "20"), ("M004", "ABS 수지", "kg", "2500", "20"),
    ("M005", "PCB 기판", "EA", "4500", "50"), ("M006", "전원 케이블", "EA", "1500", "50"),
    ("M007", "소형 모터", "EA", "18000", "20"), ("M008", "체결 볼트 세트", "EA", "300", "0"),
    ("M009", "분체 도료", "kg", "9000", "10"), ("M010", "포장 박스", "EA", "800", "50"),
]
SUPPLIERS = [("S001", "가나소재(가상)"), ("S002", "다라금속(가상)"), ("S003", "마바전자(가상)"), ("S004", "사아산업(가상)")]
SUPPLIER_MATERIALS = [  # supplier, material, lead_time_days, moq(base unit), preferred
    ("S001", "M001", 7, "100", True), ("S002", "M001", 4, "200", False), ("S002", "M002", 10, "50", True),
    ("S003", "M003", 12, "20", True), ("S002", "M004", 6, "25", True), ("S003", "M005", 10, "100", True),
    ("S004", "M006", 5, "100", True), ("S003", "M007", 21, "50", True), ("S004", "M007", 14, "50", False),
    ("S004", "M008", 3, "500", True), ("S001", "M009", 8, "10", True), ("S004", "M010", 4, "200", True),
]
BOMS = [  # bom_id, product, version, status, active, valid_from, valid_to, min_qty, max_qty, site, base_qty
    ("BOM-FG001-V1", "FG001", "V1", "APPROVED", True, "2026-01-01", "2026-11-30", "0", None, None, "1"),
    ("BOM-FG001-V2", "FG001", "V2", "APPROVED", True, "2026-12-01", None, "0", None, None, "1"),
    ("BOM-FG002-V1", "FG002", "V1", "APPROVED", True, "2026-01-01", None, "0", None, None, "1"),
    ("BOM-FG003-V1", "FG003", "V1", "APPROVED", True, "2026-01-01", None, "0", "500", None, "1"),
    ("BOM-FG003-V2", "FG003", "V2", "APPROVED", True, "2026-01-01", None, "500", None, None, "1"),
    ("BOM-SF001-V1", "SF001", "V1", "APPROVED", True, "2026-01-01", None, "0", None, None, "1"),
    ("BOM-SF002-V1", "SF002", "V1", "APPROVED", True, "2026-01-01", None, "0", None, None, "1"),
]
BOM_LINES = [  # bom_id, line_no, component_type, component_id, qty_per, unit, scrap_rate
    ("BOM-FG001-V1", 1, "PRODUCT", "SF001", "1", "EA", "0"),
    ("BOM-FG001-V1", 2, "MATERIAL", "M001", "1.2", "kg", "0"),
    ("BOM-FG001-V1", 3, "MATERIAL", "M006", "1", "EA", "0"),
    ("BOM-FG001-V1", 4, "MATERIAL", "M010", "1", "EA", "0"),
    ("BOM-FG001-V2", 1, "PRODUCT", "SF001", "1", "EA", "0"),
    ("BOM-FG001-V2", 2, "MATERIAL", "M001", "1000", "g", "0"),
    ("BOM-FG001-V2", 3, "MATERIAL", "M006", "1", "EA", "0"),
    ("BOM-FG001-V2", 4, "MATERIAL", "M010", "1", "EA", "0"),
    ("BOM-FG002-V1", 1, "PRODUCT", "SF001", "2", "EA", "0"),
    ("BOM-FG002-V1", 2, "MATERIAL", "M002", "0.8", "kg", "0"),
    ("BOM-FG002-V1", 3, "MATERIAL", "M010", "1", "EA", "0"),
    ("BOM-FG003-V1", 1, "PRODUCT", "SF002", "1", "EA", "0"),
    ("BOM-FG003-V1", 2, "MATERIAL", "M001", "0.6", "kg", "0"),
    ("BOM-FG003-V1", 3, "MATERIAL", "M009", "80", "g", "0"),
    ("BOM-FG003-V2", 1, "PRODUCT", "SF002", "1", "EA", "0"),
    ("BOM-FG003-V2", 2, "MATERIAL", "M001", "0.6", "kg", "0"),
    ("BOM-FG003-V2", 3, "MATERIAL", "M009", "60", "g", "0"),
    ("BOM-SF001-V1", 1, "MATERIAL", "M003", "300", "g", "0"),
    ("BOM-SF001-V1", 2, "MATERIAL", "M005", "1", "EA", "0"),
    ("BOM-SF001-V1", 3, "MATERIAL", "M004", "0.2", "kg", "0"),
    ("BOM-SF002-V1", 1, "MATERIAL", "M007", "1", "EA", "0"),
    ("BOM-SF002-V1", 2, "MATERIAL", "M002", "0.4", "kg", "0.02"),
    ("BOM-SF002-V1", 3, "MATERIAL", "M008", "1", "EA", "0"),
]
RESOURCES = [  # id, name, type, regular_h/day, overtime_max_h/day, cost/h, overtime_cost/h
    ("R1", "판금 라인", "LINE", "16", "2", "60000", "90000"),
    ("R2", "조립 라인", "LINE", "16", "2", "50000", "75000"),
    ("R3", "모듈 셀", "WORKCENTER", "8", "2", "55000", "82500"),
]
OPERATIONS = [  # id, product, seq, resource, run_time_h_per_unit, setup_h
    ("OP-FG001-10", "FG001", 10, "R1", "0.10", "1.0"), ("OP-FG001-20", "FG001", 20, "R2", "0.20", "0.5"),
    ("OP-FG002-10", "FG002", 10, "R1", "0.12", "1.0"), ("OP-FG002-20", "FG002", 20, "R2", "0.25", "0.5"),
    ("OP-FG003-10", "FG003", 10, "R1", "0.08", "1.0"), ("OP-FG003-20", "FG003", 20, "R2", "0.15", "0.5"),
    ("OP-SF001-10", "SF001", 10, "R3", "0.15", "1.0"), ("OP-SF002-10", "SF002", 10, "R1", "0.10", "1.0"),
]
INVENTORY = [  # item_type, item_id, on_hand, allocated, on_order, expected_receipt, unit
    ("PRODUCT", "FG001", "120", "20", "0", None, "EA"), ("PRODUCT", "FG002", "60", "0", "0", None, "EA"),
    ("PRODUCT", "FG003", "90", "10", "0", None, "EA"), ("PRODUCT", "SF001", "150", "0", "0", None, "EA"),
    ("PRODUCT", "SF002", "40", "0", "0", None, "EA"),
    ("MATERIAL", "M001", "800", "0", "150", "2026-11-20", "kg"), ("MATERIAL", "M002", "500", "0", "0", None, "kg"),
    ("MATERIAL", "M003", "200000", "0", "0", None, "g"),  # g 단위 재고 기록 (환산 경계 사례)
    ("MATERIAL", "M004", "300", "0", "0", None, "kg"), ("MATERIAL", "M005", "600", "0", "300", "2026-11-25", "EA"),
    ("MATERIAL", "M006", "500", "0", "0", None, "EA"), ("MATERIAL", "M007", "400", "0", "0", None, "EA"),
    ("MATERIAL", "M008", "1000", "0", "0", None, "EA"), ("MATERIAL", "M009", "50", "0", "0", None, "kg"),
    ("MATERIAL", "M010", "700", "0", "0", None, "EA"),
]
ORDERS = [  # id, product, qty, order_date, due_date, priority, status
    ("O001", "FG001", "80", "2026-11-02", "2026-11-20", "NORMAL", "OPEN"),
    ("O002", "FG002", "40", "2026-11-02", "2026-11-20", "NORMAL", "OPEN"),
    ("O003", "FG003", "120", "2026-11-03", "2026-11-21", "NORMAL", "OPEN"),
    ("O004", "FG001", "100", "2026-11-04", "2026-11-27", "NORMAL", "OPEN"),
    ("O005", "FG002", "60", "2026-11-05", "2026-11-27", "URGENT", "OPEN"),
    ("O006", "FG003", "150", "2026-11-05", "2026-11-27", "NORMAL", "OPEN"),
    ("O007", "FG001", "90", "2026-11-06", "2026-12-04", "NORMAL", "OPEN"),
    ("O008", "FG002", "50", "2026-11-09", "2026-12-04", "NORMAL", "OPEN"),
    ("O009", "FG003", "130", "2026-11-09", "2026-12-04", "NORMAL", "OPEN"),
    ("O010", "FG001", "110", "2026-11-10", "2026-12-11", "NORMAL", "OPEN"),
    ("O011", "FG002", "70", "2026-11-10", "2026-12-11", "NORMAL", "OPEN"),
    ("O012", "FG003", "160", "2026-11-11", "2026-12-11", "NORMAL", "OPEN"),
    ("O013", "FG001", "60", "2026-11-11", "2026-11-25", "URGENT", "OPEN"),
    ("O014", "FG003", "80", "2026-11-12", "2026-12-02", "NORMAL", "OPEN"),
    ("O015", "FG002", "30", "2026-11-12", "2026-12-09", "NORMAL", "OPEN"),
    ("O016", "FG001", "70", "2026-11-12", "2026-12-09", "NORMAL", "OPEN"),
    ("O017", "FG003", "100", "2026-11-13", "2026-11-24", "URGENT", "OPEN"),
    ("O018", "FG002", "45", "2026-11-03", "2026-12-01", "NORMAL", "CANCELLED"),
    ("O019", "FG001", "50", "2026-10-28", "2026-11-18", "NORMAL", "CLOSED"),
    ("O020", "FG003", "40", "2026-11-13", "2026-12-13", "NORMAL", "OPEN"),  # 계획 마지막 날 납기 (경계)
]
PLANS = [  # plan_id, plan_name, overtime_allowed, {product: 주별 외주 수량 상한} — 생산 수량(주문·안전재고 기준)은 세 안이 같음
    ("PLAN-REG", "정규생산안", False, {}),
    ("PLAN-OT", "잔업안", True, {}),
    ("PLAN-OUT", "외주안", False, {"FG003": "OUTSOURCER-1"}),
]
# 가상 외주처 (합성 가정): 외주 가능 제품은 FG003뿐. 주별 처리 능력·리드타임·자재 부담은 PoC 가정값
OUTSOURCERS = {
    "OUTSOURCER-1": {"name": "가상 외주처 1 (합성 가정)", "product_id": "FG003", "capacity_per_week": "150",
                     "lead_time_days": 7, "supplies_material": True, "origin_class": "SYNTHETIC"},
}
GT_V1_SHA256 = "89f1b075b281d4eaa53fb2b788f0b18b9296e534e195e272114bd36f7c2053a7"  # 보존된 v1 정답셋
PARAMETERS = {
    "reference_date": REFERENCE_DATE.isoformat(),
    "horizon_start": HORIZON_START.isoformat(),
    "horizon_end": HORIZON_END.isoformat(),
    "period_grain": "WEEK",
    "working_days": ["MON", "TUE", "WED", "THU", "FRI"],
    "currency": "KRW",
    "demand_source": "ORDERS",
    "include_safety_stock": True,
    "include_material_safety_stock": True,
    "net_semi_finished": True,
    "outsourcer_supplies_material": True,
    "overtime_in_order_check": False,
    "horizon_bom_selection_date": "horizon_start",
    "plan_bom_selection_date": "period_start",
    "site_id": None,
    "outsourcers": OUTSOURCERS,
    "plan_evaluation_rules": {
        "same_conditions": "세 계획안 모두 같은 주문·재고·자재·BOM·납기·완제품 주별 생산 수량을 쓴다",
        "inhouse_capacity": "정규생산안·외주안 = 정규시간, 잔업안 = 정규시간 + 잔업 최대",
        "completion": "자원·주별 가용/필요 비율로 사내 생산 수량을 비례 배분, 정수 EA로 내림. 완료일 = 해당 주 금요일",
        "outsourced_receipt": "외주 수량은 주 시작일 + 외주 리드타임에 입고",
        "worked_hours": "정규 근무 = min(필요, 정규 가용), 잔업 = min(max(0, 필요 − 정규 가용), 잔업 가용)",
    },
    "cq": {
        "CQ-03": {"resource_id": "R3"},
        "CQ-04": {"cases": [
            {"product_id": "FG001", "date": "2026-11-30", "qty": "460"},
            {"product_id": "FG001", "date": "2026-12-01", "qty": "460"},
            {"product_id": "FG003", "date": "2026-11-16", "qty": "499"},
            {"product_id": "FG003", "date": "2026-11-16", "qty": "500"},
            {"product_id": "FG002", "date": "2025-12-31", "qty": "10"},
        ]},
        "CQ-05": {"material_ids": ["M001", "M003"]},
        "CQ-09": {"material_ids": ["M001", "M007"]},
        "CQ-10": {"min_lead_time_days": 14},
        "CQ-11": {"material_id": "M003", "delay_days": 7},
    },
}
ASSUMPTIONS = [
    "모든 마스터·주문·재고 값은 PoC용 가정값이며 실제 기업 값이 아니다.",
    "계획 기간은 2026-11-16(월)~2026-12-13(일) 4주, 재고 기준일은 2026-11-15, 근무는 월~금(공휴일 없음).",
    "R1·R2는 2교대 가정으로 정규 16h/일, R3는 8h/일. 잔업 최대 2h/일.",
    "주문 1건 = 제품 1종. CLOSED·CANCELLED 주문은 수요에서 제외한다.",
    "공급사명은 가상 명칭이다. 구매 리드타임은 우선 공급사(is_preferred) 값을 쓴다.",
    "SalesHistory는 UCI 일별 총주문(Target)을 완제품 3종에 시드 고정 난수 비율로 배분한 합성값이다. 원본에 날짜가 없고 요일 코드(2~6)의 의미도 원본에서 확인되지 않으므로, 요일 코드는 숫자 그대로(source_day_of_week_code) 보존하고 period_start는 2026-08-05부터 연속 영업일로 붙인 합성 날짜(date_is_synthetic=true)다. 합성 날짜의 요일은 원본 요일 코드와 관계없다.",
    "생산계획안: 완제품 주별 수량은 세 안 모두 같은 lot-for-lot 순소요(안전재고 유지)다. 정규생산안은 정규시간 내 자체 생산, 잔업안은 정규 + 잔업 가용시간으로 같은 수량을 자체 생산, 외주안은 FG003의 주별 수량 중 가상 외주처 능력(150 EA/주)까지를 명시 수량으로 외주하고 나머지를 정규시간 내 자체 생산한다. 반제품 수요는 자체 생산 완제품에서만 생긴다.",
    "가상 외주처(OUTSOURCER-1)의 능력 150 EA/주, 리드타임 7일, 자재 외주처 부담은 합성 가정이다.",
    "계획 라인의 resource_id는 해당 제품 첫 공정(sequence 10)의 자원이다. 시간 계산은 제품의 모든 공정에 대해 한다.",
]
UCI_ATTRIBUTION = {
    "dataset": "Daily Demand Forecasting Orders",
    "license": "CC BY 4.0",
    "citation": "Ferreira, R., Martiniano, A., Ferreira, A., Ferreira, A., & Sassi, R. (2016). Daily Demand Forecasting Orders [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BC8T",
    "note": "원본 파일은 저장소에 포함하지 않는다. SalesHistory는 원본 총주문을 가상 제품에 배분한 합성값(SYNTHETIC/ALLOCATED)이다.",
}

# Vendor 코드 체계 (업체별로 다른 코드, Vendor A는 선행 0 포함)
A_CODES = {
    "FG001": "0001001", "FG002": "0001002", "FG003": "0001003", "SF001": "0002001", "SF002": "0002002",
    **{f"M{n:03d}": f"000{100 + n}" for n in range(1, 11)},
    "S001": "SUP-01", "S002": "SUP-02", "S003": "SUP-03", "S004": "SUP-04",
    "R1": "R01", "R2": "R02", "R3": "R03",
}
B_CODES = {
    "FG001": "HT-A", "FG002": "HT-B", "FG003": "BL-C", "SF001": "MD-CORE", "SF002": "MD-HOUS",
    **{f"M{n:03d}": f"MAT-{n:02d}" for n in range(1, 11)},
    "S001": "SP01", "S002": "SP02", "S003": "SP03", "S004": "SP04",
}


def _uid(entity: str, *key: str) -> str:
    return record_uid(DATASET_ID, DATASET_VERSION, entity, *key)


def _rec(entity: str, key: tuple, **fields) -> dict:
    return {"record_uid": _uid(entity, *map(str, key)), "origin_class": "SYNTHETIC", **fields}


# ---------------------------------------------------------------------------
# canonical 엔터티
# ---------------------------------------------------------------------------
def build_master() -> dict[str, list[dict]]:
    E: dict[str, list[dict]] = {}
    E["Unit"] = [_rec("Unit", (u,), unit_code=u, dimension=d, base_unit_code=b, to_base_factor=f) for u, d, b, f in UNITS]
    E["Product"] = [_rec("Product", (p,), product_id=p, product_name=n, product_type=t, base_unit=u, safety_stock_qty=ss,
                         manuf_lead_time_days=lt, outsourcing_allowed=oa, outsourcing_unit_cost=oc)
                    for p, n, t, u, ss, lt, oa, oc in PRODUCTS]
    E["Material"] = [_rec("Material", (m,), material_id=m, material_name=n, base_unit=u, unit_cost=c, safety_stock_qty=ss)
                     for m, n, u, c, ss in MATERIALS]
    E["Supplier"] = [_rec("Supplier", (s,), supplier_id=s, supplier_name=n) for s, n in SUPPLIERS]
    E["SupplierMaterial"] = [_rec("SupplierMaterial", (s, m), supplier_id=s, material_id=m, lead_time_days=lt,
                                  min_order_qty=moq, is_preferred=pref) for s, m, lt, moq, pref in SUPPLIER_MATERIALS]
    E["BOM"] = [_rec("BOM", (b,), bom_id=b, product_id=p, bom_version=v, status=st, is_active=a, valid_from=vf,
                     valid_to=vt, min_qty=mn, max_qty=mx, site_id=site, base_qty=bq)
                for b, p, v, st, a, vf, vt, mn, mx, site, bq in BOMS]
    E["BOMLine"] = [_rec("BOMLine", (b, ln), bom_id=b, line_no=ln, component_type=ct,
                         component_material_id=c if ct == "MATERIAL" else None,
                         component_product_id=c if ct == "PRODUCT" else None,
                         qty_per=q, unit=u, scrap_rate=s, line_type="ITEM")
                    for b, ln, ct, c, q, u, s in BOM_LINES]
    E["Order"] = [_rec("Order", (o,), order_id=o, product_id=p, order_qty=q, unit="EA", order_date=od, due_date=dd,
                       priority=pr, status=st) for o, p, q, od, dd, pr, st in ORDERS]
    E["Inventory"] = [_rec("Inventory", (t, i, REFERENCE_DATE.isoformat()), item_type=t, item_id=i,
                           as_of_date=REFERENCE_DATE.isoformat(), on_hand_qty=oh, allocated_qty=al, on_order_qty=oo,
                           expected_receipt_date=er, unit=u) for t, i, oh, al, oo, er, u in INVENTORY]
    E["Resource"] = [_rec("Resource", (r,), resource_id=r, resource_name=n, resource_type=t, regular_hours_per_day=h,
                          overtime_hours_per_day_max=ot, cost_per_hour=c, overtime_cost_per_hour=oc)
                     for r, n, t, h, ot, c, oc in RESOURCES]
    E["Operation"] = [_rec("Operation", (o,), operation_id=o, product_id=p, sequence_no=s, resource_id=r,
                           run_time_per_unit_h=rt, setup_time_h=su) for o, p, s, r, rt, su in OPERATIONS]
    return E


def read_uci_staging(paths: Paths) -> list[dict]:
    """UCI 원본을 수정 없이 읽어 원본 1행 = 1 스테이징 레코드로 만든다 (PUBLIC_REAL)."""
    raw = paths.uci_csv.read_bytes()
    file_sha = sha256_file(paths.uci_csv)
    rows = list(csv.reader(io.StringIO(raw.decode("ascii")), delimiter=";"))
    header, data = rows[0], rows[1:]
    out = []
    for n, r in enumerate(data, start=1):
        out.append({
            "record_uid": record_uid("uci_daily_demand", file_sha[:12], "", str(n + 1)),
            "origin_class": "PUBLIC_REAL",
            "source_file": "data/raw/public/uci_daily_demand/extracted/Daily_Demand_Forecasting_Orders.csv",
            "source_sha256": file_sha, "data_row": n, "file_line": n + 1,
            "day_of_week_code": int(r[1]), "week_of_month": int(r[0]), "target_total": r[12],
            "raw": dict(zip(header, r)),
        })
    return out


def build_sales_history(staging: list[dict]) -> tuple[list[dict], list[dict]]:
    """UCI 총주문을 완제품 3종에 배분 (SYNTHETIC/ALLOCATED).

    원본 요일 코드의 의미(예: 2=월)는 확인되지 않았으므로 날짜 계산에 쓰지 않는다.
    원본 행 순서대로 연속 영업일(월~금) 합성 날짜를 붙이고, 원본 코드는 숫자로만 보존한다.
    """
    rng = random.Random(SEED)
    fg = [p[0] for p in PRODUCTS if p[2] == "FINISHED"]
    sales, date_map = [], []
    d = None
    for st in staging:
        if d is None:
            d = UCI_FIRST_DATE
        else:
            d = d + dt.timedelta(days=1)
            while d.weekday() >= 5:
                d += dt.timedelta(days=1)
        date_map.append({"record_uid": st["record_uid"], "data_row": st["data_row"], "synthetic_date": d.isoformat(),
                         "source_day_of_week_code": st["day_of_week_code"], "date_is_synthetic": True})
        weights = [Decimal(rng.randint(20, 100)) for _ in fg]
        total_w = sum(weights)
        shares = [(w / total_w).quantize(Decimal("0.0001"), ROUND_HALF_EVEN) for w in weights[:-1]]
        shares.append(Decimal(1) - sum(shares))
        target = D(st["target_total"])
        qtys = [(target * s).quantize(Decimal("0.001"), ROUND_HALF_EVEN) for s in shares[:-1]]
        qtys.append(target - sum(qtys))  # 마지막 제품은 잔여량 → 합계 정확히 보존
        for p, s, q in zip(fg, shares, qtys):
            sales.append(_rec("SalesHistory", (p, d.isoformat(), "DAY"), product_id=p, period_start=d.isoformat(),
                              period_grain="DAY", sales_qty=fmt(q), source_series_id=None,
                              generation_method="ALLOCATED", derived_from_record_uid=st["record_uid"],
                              allocation_share=fmt(s), date_is_synthetic=True,
                              source_day_of_week_code=st["day_of_week_code"]))
    if d >= REFERENCE_DATE:
        raise ValueError("판매 이력이 재고 기준일 이후까지 이어짐")
    return sales, date_map


# ---------------------------------------------------------------------------
# 생산계획안 (입력 데이터 생성용 lot-for-lot; 기대값 계산 아님)
# ---------------------------------------------------------------------------
def _gen_to_base(units: dict, qty: Decimal, unit: str) -> Decimal:
    return qty * D(units[unit]["to_base_factor"])


def _gen_select_bom(E: dict, product: str, day: dt.date, qty: Decimal) -> str:
    hits = [b for b in E["BOM"] if b["product_id"] == product and b["status"] == "APPROVED" and b["is_active"]
            and dt.date.fromisoformat(b["valid_from"]) <= day
            and (b["valid_to"] is None or day <= dt.date.fromisoformat(b["valid_to"]))
            and D(b["min_qty"]) <= qty and (b["max_qty"] is None or qty < D(b["max_qty"]))]
    if len(hits) != 1:
        raise ValueError(f"계획 생성 중 BOM 선택 실패: {product} {day} {qty} → {len(hits)}개")
    return hits[0]["bom_id"]


def build_plans(E: dict) -> tuple[list[dict], list[dict]]:
    weeks = [HORIZON_START + dt.timedelta(days=7 * w) for w in range(HORIZON_WEEKS)]
    week_of = lambda day: next(i for i, ws in enumerate(weeks) if ws <= day < ws + dt.timedelta(days=7))
    prod = {p["product_id"]: p for p in E["Product"]}
    inv = {(i["item_type"], i["item_id"]): i for i in E["Inventory"]}
    first_res = {}
    for op in sorted(E["Operation"], key=lambda o: (o["product_id"], o["sequence_no"])):
        first_res.setdefault(op["product_id"], op["resource_id"])

    def lot_for_lot(item: str, demand: list[Decimal]) -> list[Decimal]:
        rec = inv[("PRODUCT", item)]
        poh = D(rec["on_hand_qty"]) - D(rec["allocated_qty"])
        receipt_week = None
        if rec["expected_receipt_date"]:
            receipt_week = week_of(dt.date.fromisoformat(rec["expected_receipt_date"]))
        ss, out = D(prod[item]["safety_stock_qty"]), []
        for w in range(HORIZON_WEEKS):
            if receipt_week == w:
                poh += D(rec["on_order_qty"])
            poh -= demand[w]
            q = max(Decimal(0), ss - poh)
            poh += q
            out.append(q)
        return out

    fg_demand = {p: [Decimal(0)] * HORIZON_WEEKS for p in prod if prod[p]["product_type"] == "FINISHED"}
    for o in E["Order"]:
        due = dt.date.fromisoformat(o["due_date"])
        if o["status"] == "OPEN" and HORIZON_START <= due <= HORIZON_END:
            fg_demand[o["product_id"]][week_of(due)] += D(o["order_qty"])
    fg_qty = {p: lot_for_lot(p, d) for p, d in fg_demand.items()}
    lines_by_bom = {}
    for ln in E["BOMLine"]:
        lines_by_bom.setdefault(ln["bom_id"], []).append(ln)

    plans, plan_lines = [], []
    for plan_id, plan_name, overtime_allowed, outsource in PLANS:
        plans.append(_rec("ProductionPlan", (plan_id,), plan_id=plan_id, plan_name=plan_name,
                          horizon_start=HORIZON_START.isoformat(), horizon_end=HORIZON_END.isoformat(), generated_by="RULE",
                          overtime_allowed=overtime_allowed))
        sf_demand: dict[str, list[Decimal]] = {}
        rows = []
        for p in sorted(fg_qty):
            for w, total in enumerate(fg_qty[p]):
                if total <= 0:
                    continue
                out_qty = Decimal(0)
                if p in outsource:
                    cap = D(OUTSOURCERS[outsource[p]]["capacity_per_week"])
                    out_qty = min(total, cap)  # 명시 외주 수량 = 외주처 주별 능력까지
                    rows.append((p, w, out_qty, "OUTSOURCE"))
                q = total - out_qty
                if q <= 0:
                    continue
                rows.append((p, w, q, "INHOUSE"))
                bom = _gen_select_bom(E, p, weeks[w], q)
                for ln in lines_by_bom[bom]:
                    if ln["component_type"] == "PRODUCT":
                        need = q * D(ln["qty_per"]) * (1 + D(ln["scrap_rate"])) / D(next(b for b in E["BOM"] if b["bom_id"] == bom)["base_qty"])
                        sf_demand.setdefault(ln["component_product_id"], [Decimal(0)] * HORIZON_WEEKS)[w] += need
        for sf in sorted(sf_demand):
            for w, q in enumerate(lot_for_lot(sf, sf_demand[sf])):
                if q > 0:
                    rows.append((sf, w, q, "INHOUSE"))
        for n, (p, w, q, mode) in enumerate(rows, start=1):
            plan_lines.append(_rec("ProductionPlanLine", (plan_id, n), plan_id=plan_id, line_no=n, product_id=p,
                                   period_start=weeks[w].isoformat(), planned_qty=fmt(q), unit="EA",
                                   production_mode=mode, resource_id=None if mode == "OUTSOURCE" else first_res[p]))
    return plans, plan_lines


# ---------------------------------------------------------------------------
# Vendor A/B 파일
# ---------------------------------------------------------------------------
def _write_csv(path: Path, header: list[str], rows: list[list[str]], encoding: str, newline: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=newline, quoting=csv.QUOTE_MINIMAL)
    w.writerow(header)
    w.writerows(rows)
    path.write_bytes(buf.getvalue().encode(encoding))


def _b_num(value: Decimal | str | None, places: int | None = None) -> str:
    """Vendor B 숫자 서식: 천 단위 쉼표."""
    if value is None:
        return ""
    v = D(value)
    s = fmt(v)
    whole, _, frac = s.partition(".")
    neg = whole.startswith("-")
    whole = f"{int(whole.lstrip('-')):,}"
    return ("-" if neg else "") + whole + (("." + frac) if frac else "")


def _b_date(value: str | None) -> str:
    return "" if value is None else value.replace("-", ".")


def _yn(v: bool) -> str:
    return "Y" if v else "N"


def _ko_yn(v: bool) -> str:
    return "예" if v else "아니오"


def build_vendor_files(E: dict, paths: Paths) -> tuple[list[dict], list[dict], dict]:
    units = {u["unit_code"]: u for u in E["Unit"]}
    mat = {m["material_id"]: m for m in E["Material"]}
    boms = {b["bom_id"]: b for b in E["BOM"]}
    row_map: list[dict] = []
    id_map: list[dict] = []
    for vendor, codes in (("A", A_CODES), ("B", B_CODES)):
        for cid, vcode in codes.items():
            ent = {"F": "Product", "S": "Product", "M": "Material", "R": "Resource"}.get(cid[0])
            if cid.startswith("S0"):
                ent = "Supplier"
            id_map.append({"vendor": vendor, "entity": ent, "vendor_code": vcode, "canonical_id": cid})
    a_bom = {b: f"BM-{A_CODES[boms[b]['product_id']]}-{boms[b]['bom_version'][1:]}" for b in boms}
    b_bom = {b: f"B-BOM-{n:02d}" for n, b in enumerate(boms, start=1)}
    for b in boms:
        id_map.append({"vendor": "A", "entity": "BOM", "vendor_code": a_bom[b], "canonical_id": b})
        id_map.append({"vendor": "B", "entity": "BOM", "vendor_code": b_bom[b], "canonical_id": b})
    for o in E["Order"]:
        id_map.append({"vendor": "A", "entity": "Order", "vendor_code": f"SO26{o['order_id'][1:].zfill(4)}", "canonical_id": o["order_id"]})
        id_map.append({"vendor": "B", "entity": "Order", "vendor_code": f"주문-{o['order_id'][1:]}", "canonical_id": o["order_id"]})
    a_order = {m["canonical_id"]: m["vendor_code"] for m in id_map if m["vendor"] == "A" and m["entity"] == "Order"}
    b_order = {m["canonical_id"]: m["vendor_code"] for m in id_map if m["vendor"] == "B" and m["entity"] == "Order"}

    def mass_to(qty: str, unit: str, target: str) -> Decimal:
        base = D(qty) * D(units[unit]["to_base_factor"])
        return base / D(units[target]["to_base_factor"])

    def comp_of(ln: dict) -> str:
        return ln["component_material_id"] or ln["component_product_id"]

    def comp_base_unit(ln: dict) -> str:
        return mat[ln["component_material_id"]]["base_unit"] if ln["component_material_id"] else "EA"

    def a_unit_qty(qty: str, unit: str, item_base: str) -> tuple[str, str]:
        """Vendor A: 항상 품목 기준 단위(kg)로 표기."""
        return fmt(mass_to(qty, unit, item_base)) if units[unit]["dimension"] == "MASS" else qty, item_base

    def b_unit_qty(qty: str, unit: str) -> tuple[Decimal, str]:
        """Vendor B: 질량은 항상 g."""
        if units[unit]["dimension"] == "MASS":
            return mass_to(qty, unit, "g"), "g"
        return D(qty), unit

    def add_map(vendor, file, sheet, row, entity, key, uid):
        row_map.append({"vendor": vendor, "file": file, "sheet": sheet, "row_number": row, "entity": entity,
                        "canonical_key": key, "canonical_record_uid": uid})

    col_map: dict = {"_note": "업체 파일 열 → canonical 필드 대응. 변환 규칙은 transform에 기재.", "files": []}

    # ---- Vendor A CSV ----
    A = paths.vendor_a
    spec_a = [
        ("products.csv", "utf-8", "\n", "Product",
         ["product_code", "product_name", "product_type", "uom", "safety_stock", "mfg_lead_time_days", "outsourcing_allowed", "outsourcing_unit_cost_krw"],
         [(p, [A_CODES[p["product_id"]], p["product_name"], "FG" if p["product_type"] == "FINISHED" else "SF", p["base_unit"],
               p["safety_stock_qty"], str(p["manuf_lead_time_days"]), _yn(p["outsourcing_allowed"]), p["outsourcing_unit_cost"] or ""],
           p["product_id"]) for p in E["Product"]]),
        ("materials.csv", "utf-8-sig", "\n", "Material",
         ["material_code", "material_name", "uom", "unit_cost_krw", "safety_stock"],
         [(m, [A_CODES[m["material_id"]], m["material_name"], m["base_unit"], m["unit_cost"], m["safety_stock_qty"]], m["material_id"]) for m in E["Material"]]),
        ("suppliers.csv", "utf-8", "\n", "Supplier", ["supplier_code", "supplier_name"],
         [(s, [A_CODES[s["supplier_id"]], s["supplier_name"]], s["supplier_id"]) for s in E["Supplier"]]),
        ("supplier_materials.csv", "utf-8", "\n", "SupplierMaterial",
         ["supplier_code", "material_code", "lead_time_days", "moq", "preferred"],
         [(sm, [A_CODES[sm["supplier_id"]], A_CODES[sm["material_id"]], str(sm["lead_time_days"]), sm["min_order_qty"] or "", _yn(sm["is_preferred"])],
           f"{sm['supplier_id']}|{sm['material_id']}") for sm in E["SupplierMaterial"]]),
        ("inventory.csv", "utf-8", "\n", "Inventory",
         ["item_type", "item_code", "as_of", "on_hand", "allocated", "on_order", "expected_receipt", "uom"],
         [(i, [i["item_type"][:3], A_CODES[i["item_id"]], i["as_of_date"],
               *[fmt(mass_to(i[f], i["unit"], mat[i["item_id"]]["base_unit"])) if i["item_type"] == "MATERIAL" else i[f]
                 for f in ("on_hand_qty", "allocated_qty", "on_order_qty")],
               i["expected_receipt_date"] or "", mat[i["item_id"]]["base_unit"] if i["item_type"] == "MATERIAL" else i["unit"]],
           f"{i['item_type']}|{i['item_id']}|{i['as_of_date']}") for i in E["Inventory"]]),
        ("orders.csv", "utf-8", "\n", "Order",
         ["order_no", "product_code", "qty", "uom", "order_date", "due_date", "priority", "status"],
         [(o, [a_order[o["order_id"]], A_CODES[o["product_id"]], o["order_qty"], o["unit"], o["order_date"], o["due_date"], o["priority"], o["status"]],
           o["order_id"]) for o in E["Order"]]),
        ("resources.csv", "utf-8", "\n", "Resource",
         ["resource_code", "resource_name", "resource_type", "regular_hours_per_day", "max_overtime_hours_per_day", "cost_per_hour_krw", "overtime_cost_per_hour_krw"],
         [(r, [A_CODES[r["resource_id"]], r["resource_name"], r["resource_type"], r["regular_hours_per_day"], r["overtime_hours_per_day_max"],
               r["cost_per_hour"], r["overtime_cost_per_hour"]], r["resource_id"]) for r in E["Resource"]]),
        ("routing.csv", "utf-8", "\n", "Operation",
         ["operation_code", "product_code", "seq", "resource_code", "run_time_h_per_unit", "setup_time_h"],
         [(op, [op["operation_id"], A_CODES[op["product_id"]], str(op["sequence_no"]), A_CODES[op["resource_id"]],
                op["run_time_per_unit_h"], op["setup_time_h"]], op["operation_id"]) for op in E["Operation"]]),
    ]
    bom_header_a = ["bom_code", "product_code", "bom_version", "status", "active", "valid_from", "valid_to", "min_qty",
                    "max_qty", "site", "base_qty", "line_no", "component_type", "component_code", "qty_per", "uom", "scrap_rate"]
    bom_rows_a = []
    for ln in E["BOMLine"]:
        b = boms[ln["bom_id"]]
        q, u = a_unit_qty(ln["qty_per"], ln["unit"], comp_base_unit(ln))
        bom_rows_a.append((ln, [a_bom[b["bom_id"]], A_CODES[b["product_id"]], b["bom_version"], b["status"], _yn(b["is_active"]),
                                b["valid_from"], b["valid_to"] or "", b["min_qty"], b["max_qty"] or "", b["site_id"] or "", b["base_qty"],
                                str(ln["line_no"]), "MAT" if ln["component_type"] == "MATERIAL" else "PRD", A_CODES[comp_of(ln)],
                                q, u, ln["scrap_rate"]], f"{ln['bom_id']}|{ln['line_no']}"))
    spec_a.insert(4, ("bom.csv", "utf-8", "\n", "BOMLine", bom_header_a, bom_rows_a))
    for fname, enc, nl, entity, header, rows in spec_a:
        _write_csv(A / fname, header, [r[1] for r in rows], enc, nl)
        for n, (rec, _, key) in enumerate(rows, start=2):
            add_map("A", f"vendor_a/{fname}", "", n, entity, key, rec["record_uid"])
            if fname == "bom.csv":
                add_map("A", f"vendor_a/{fname}", "", n, "BOM", rec["bom_id"], boms[rec["bom_id"]]["record_uid"])
        col_map["files"].append({"vendor": "A", "file": f"vendor_a/{fname}", "format": "csv", "encoding": enc,
                                 "delimiter": ",", "header_rows": 1, "entity": entity, "columns": header})

    # ---- Vendor A XLSX (여러 시트, 1행 헤더) ----
    wb = openpyxl.Workbook()
    wb.properties.created = wb.properties.modified = dt.datetime(*FIXED_ZIP_TIME)
    wb.properties.creator = "e01_generate"
    first = True
    for sheet, fname in (("Products", "products.csv"), ("Materials", "materials.csv"), ("BOM", "bom.csv")):
        fname_spec = next(s for s in spec_a if s[0] == fname)
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = sheet
        ws.append(fname_spec[4])
        for n, (rec, values, key) in enumerate(fname_spec[5], start=2):
            ws.append(values)
            for c in range(1, len(values) + 1):
                ws.cell(row=n, column=c).number_format = "@"  # 선행 0 보존을 위해 텍스트 셀
            add_map("A", "vendor_a/vendor_a_master.xlsx", sheet, n, fname_spec[3], key, rec["record_uid"])
            if fname == "bom.csv":
                add_map("A", "vendor_a/vendor_a_master.xlsx", sheet, n, "BOM", rec["bom_id"], boms[rec["bom_id"]]["record_uid"])
        col_map["files"].append({"vendor": "A", "file": "vendor_a/vendor_a_master.xlsx", "sheet": sheet, "format": "xlsx",
                                 "header_rows": 1, "entity": fname_spec[3], "columns": fname_spec[4], "cell_type": "text"})
    xa = A / "vendor_a_master.xlsx"
    wb.save(xa)
    normalize_xlsx(xa)

    # ---- Vendor B XLSX (병합 헤더 2행, 한글 열, 질량 g, 날짜 YYYY.MM.DD, 손실률 %) ----
    B = paths.vendor_b
    B.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    wb.properties.created = wb.properties.modified = dt.datetime(*FIXED_ZIP_TIME)
    wb.properties.creator = "e01_generate"
    b_sheets = []
    b_sheets.append(("제품", "Product", [("기본정보", ["품목코드", "품목명", "구분", "단위"]),
                                         ("관리기준", ["안전재고", "생산리드타임(일)", "외주가능", "외주단가(원)"])],
                     [(p, [B_CODES[p["product_id"]], p["product_name"], "완제품" if p["product_type"] == "FINISHED" else "반제품",
                           "개" if p["base_unit"] == "EA" else p["base_unit"], _b_num(p["safety_stock_qty"]), p["manuf_lead_time_days"],
                           _ko_yn(p["outsourcing_allowed"]), _b_num(p["outsourcing_unit_cost"])], p["product_id"]) for p in E["Product"]]))

    def b_mat_row(m):
        if units[m["base_unit"]]["dimension"] == "MASS":
            per_g = D(m["unit_cost"]) * D(units["g"]["to_base_factor"]) / D(units[m["base_unit"]]["to_base_factor"])
            return [B_CODES[m["material_id"]], m["material_name"], "g", _b_num(per_g), _b_num(mass_to(m["safety_stock_qty"], m["base_unit"], "g"))]
        return [B_CODES[m["material_id"]], m["material_name"], "개", _b_num(m["unit_cost"]), _b_num(m["safety_stock_qty"])]

    b_sheets.append(("자재", "Material", [("기본정보", ["자재코드", "자재명", "단위"]), ("관리기준", ["단가(원/단위)", "안전재고"])],
                     [(m, b_mat_row(m), m["material_id"]) for m in E["Material"]]))
    sup_name = {s["supplier_id"]: s["supplier_name"] for s in E["Supplier"]}

    def b_moq(sm):
        m = mat[sm["material_id"]]
        if sm["min_order_qty"] is None:
            return ""
        if units[m["base_unit"]]["dimension"] == "MASS":
            return _b_num(mass_to(sm["min_order_qty"], m["base_unit"], "g"))
        return _b_num(sm["min_order_qty"])

    b_sheets.append(("공급조건", "SupplierMaterial", [("공급사", ["공급사코드", "공급사명"]),
                                                      ("공급조건", ["자재코드", "리드타임(일)", "최소주문량", "우선공급"])],
                     [(sm, [B_CODES[sm["supplier_id"]], sup_name[sm["supplier_id"]], B_CODES[sm["material_id"]], sm["lead_time_days"],
                            b_moq(sm), _ko_yn(sm["is_preferred"])], f"{sm['supplier_id']}|{sm['material_id']}") for sm in E["SupplierMaterial"]]))
    bom_b_rows = []
    for ln in E["BOMLine"]:
        b = boms[ln["bom_id"]]
        q, u = b_unit_qty(ln["qty_per"], ln["unit"])
        bom_b_rows.append((ln, [b_bom[b["bom_id"]], B_CODES[b["product_id"]], b["bom_version"], "승인" if b["status"] == "APPROVED" else "초안",
                                "예" if b["is_active"] else "아니오", _b_date(b["valid_from"]), _b_date(b["valid_to"]),
                                _b_num(b["min_qty"]), _b_num(b["max_qty"]), b["site_id"] or "", _b_num(b["base_qty"]),
                                ln["line_no"], "자재" if ln["component_type"] == "MATERIAL" else "제품", B_CODES[comp_of(ln)],
                                _b_num(q), "개" if u == "EA" else u, _b_num(D(ln["scrap_rate"]) * 100)],
                           f"{ln['bom_id']}|{ln['line_no']}"))
    b_sheets.append(("BOM", "BOMLine", [("BOM 정보", ["BOM번호", "모품목코드", "버전", "상태", "활성"]),
                                        ("유효조건", ["시작일", "종료일", "최소수량", "최대수량", "사이트"]),
                                        ("구성", ["기준수량", "순번", "자품목구분", "자품목코드", "소요량", "단위", "손실률(%)"])],
                     bom_b_rows))
    first = True
    for sheet, entity, groups, rows in b_sheets:
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = sheet
        col = 1
        flat = []
        for gname, cols in groups:
            ws.cell(row=1, column=col, value=gname).font = Font(bold=True)
            ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")
            if len(cols) > 1:
                ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + len(cols) - 1)
            for c in cols:
                ws.cell(row=2, column=col, value=c).font = Font(bold=True)
                col += 1
            flat.extend(cols)
        for n, (rec, values, key) in enumerate(rows, start=3):
            for c, v in enumerate(values, start=1):
                cell = ws.cell(row=n, column=c, value=v if v != "" else None)
                if isinstance(v, str):
                    cell.number_format = "@"
            add_map("B", "vendor_b/vendor_b_master.xlsx", sheet, n, entity, key, rec["record_uid"])
            if entity == "BOMLine":
                add_map("B", "vendor_b/vendor_b_master.xlsx", sheet, n, "BOM", rec["bom_id"], boms[rec["bom_id"]]["record_uid"])
            if entity == "SupplierMaterial":
                add_map("B", "vendor_b/vendor_b_master.xlsx", sheet, n, "Supplier", rec["supplier_id"],
                        next(s for s in E["Supplier"] if s["supplier_id"] == rec["supplier_id"])["record_uid"])
        col_map["files"].append({"vendor": "B", "file": "vendor_b/vendor_b_master.xlsx", "sheet": sheet, "format": "xlsx",
                                 "header_rows": 2, "merged_group_header": [g for g, _ in groups], "entity": entity, "columns": flat})
    xb = B / "vendor_b_master.xlsx"
    wb.save(xb)
    normalize_xlsx(xb)

    # ---- Vendor B CSV (CP949, CRLF, 천 단위 쉼표, YYYY.MM.DD) ----
    status_ko = {"OPEN": "진행", "CLOSED": "완료", "CANCELLED": "취소"}
    order_rows = [(o, [b_order[o["order_id"]], B_CODES[o["product_id"]], _b_num(o["order_qty"]), "개", _b_date(o["order_date"]),
                       _b_date(o["due_date"]), "긴급" if o["priority"] == "URGENT" else "일반", status_ko[o["status"]]], o["order_id"])
                  for o in E["Order"]]
    inv_rows = []
    for i in E["Inventory"]:
        if i["item_type"] == "MATERIAL":
            q = [b_unit_qty(i[f], i["unit"]) for f in ("on_hand_qty", "allocated_qty", "on_order_qty")]
            unit = q[0][1]
            qs = [x[0] for x in q]
        else:
            qs, unit = [D(i[f]) for f in ("on_hand_qty", "allocated_qty", "on_order_qty")], i["unit"]
        inv_rows.append((i, ["제품" if i["item_type"] == "PRODUCT" else "자재", B_CODES[i["item_id"]], _b_date(i["as_of_date"]),
                             *[_b_num(x) for x in qs], _b_date(i["expected_receipt_date"]), "개" if unit == "EA" else unit],
                         f"{i['item_type']}|{i['item_id']}|{i['as_of_date']}"))
    for fname, entity, header, rows in (
        ("vendor_b_orders.csv", "Order", ["주문번호", "품목코드", "수량", "단위", "주문일자", "납기일자", "긴급여부", "상태"], order_rows),
        ("vendor_b_inventory.csv", "Inventory", ["구분", "품목코드", "기준일", "현재고", "할당", "입고예정", "입고예정일", "단위"], inv_rows),
    ):
        _write_csv(B / fname, header, [r[1] for r in rows], "cp949", "\r\n")
        for n, (rec, _, key) in enumerate(rows, start=2):
            add_map("B", f"vendor_b/{fname}", "", n, entity, key, rec["record_uid"])
        col_map["files"].append({"vendor": "B", "file": f"vendor_b/{fname}", "format": "csv", "encoding": "cp949",
                                 "delimiter": ",", "header_rows": 1, "entity": entity, "columns": header})
    col_map["conventions"] = {
        "A": {"mass_unit": "material base unit (kg)", "date": "YYYY-MM-DD", "number": "plain decimal", "bool": "Y/N",
              "product_type": {"FG": "FINISHED", "SF": "SEMI_FINISHED"}, "component_type": {"MAT": "MATERIAL", "PRD": "PRODUCT"},
              "item_type": {"PRO": "PRODUCT", "MAT": "MATERIAL"}, "scrap_rate": "ratio"},
        "B": {"mass_unit": "g", "date": "YYYY.MM.DD", "number": "thousands separator ','", "bool": "예/아니오",
              "unit_label": {"개": "EA"}, "product_type": {"완제품": "FINISHED", "반제품": "SEMI_FINISHED"},
              "component_type": {"자재": "MATERIAL", "제품": "PRODUCT"}, "item_type": {"제품": "PRODUCT", "자재": "MATERIAL"},
              "status": {"승인": "APPROVED", "초안": "DRAFT"}, "order_status": {v: k for k, v in status_ko.items()},
              "priority": {"긴급": "URGENT", "일반": "NORMAL"}, "scrap_rate": "percent", "material_unit_cost": "KRW per material unit shown"},
    }
    return row_map, id_map, col_map


def _write_map_csv(path: Path, rows: list[dict]) -> None:
    header = list(rows[0])
    _write_csv(path, header, [[str("" if r[h] is None else r[h]) for h in header] for r in rows], "utf-8", "\n")


def generate(paths: Paths) -> dict:
    E = build_master()
    staging = read_uci_staging(paths)
    E["SalesHistory"], date_map = build_sales_history(staging)
    E["ProductionPlan"], E["ProductionPlanLine"] = build_plans(E)
    order = ["Unit", "Product", "Material", "Supplier", "SupplierMaterial", "BOM", "BOMLine", "Order", "SalesHistory",
             "Inventory", "Resource", "Operation", "ProductionPlan", "ProductionPlanLine"]
    E = {k: E[k] for k in order}
    counts = validate_entities(E)
    # 공개 원본 스테이징 (PUBLIC_REAL) — Git 미추적 경로에 저장
    stg_dir = paths.root / "data" / "raw" / "public" / "uci_daily_demand"
    write_json(stg_dir / "staging_uci_daily_orders_v1.json", {"records": staging, "synthetic_date_map": date_map})
    gt = {
        "dataset": {"id": DATASET_ID, "version": GT_VERSION, "record_uid_namespace": DATASET_VERSION, "seed": SEED,
                    "previous_version": {"version": "v1", "file": "data/canonical/ground_truth_v1.json", "sha256": GT_V1_SHA256,
                                         "status": "보존 (재생성하지 않음)",
                                         "changes_in_v2": ["생산계획안 의미 재정의: 잔업은 계획 단위 정책(정규+잔업 가용), 외주는 명시 수량",
                                                           "계획안 납기 평가(공급 시점 기반) 추가, 외주처 조건 합성 가정 명시",
                                                           "UCI 요일 코드 해석 제거: 원본 코드 숫자 보존 + 연속 영업일 합성 날짜 표시"]},
                    "generator": "scripts/e01_generate.py",
                    "currency": "KRW", "site_count": 1, "assumptions": ASSUMPTIONS, "public_sources": [UCI_ATTRIBUTION],
                    "record_counts": counts},
        "parameters": PARAMETERS,
        "entities": E,
    }
    write_json(paths.ground_truth, gt)
    row_map, id_map, col_map = build_vendor_files(E, paths)
    _write_map_csv(paths.row_map, row_map)
    _write_map_csv(paths.id_map, id_map)
    write_json(paths.column_map, col_map)
    return {"record_counts": counts, "vendor_rows_mapped": len(row_map), "uci_rows": len(staging)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=Path, default=None)
    args = ap.parse_args(argv)
    info = generate(Paths(args.out_root))
    print(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
