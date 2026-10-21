"""E05 독립 오류 평가셋 v1 생성 (E01 정답셋 v2 기준, 재현 가능).

    .\\.venv\\Scripts\\python.exe scripts\\e05_build_eval_set.py

- 정상(clean) / 단일 오류(single) / 경계 통과(pass, 오류가 없어야 함) / 복합 오류(compound) 데이터셋
- 주입마다: 원본 레코드·위치·오류 유형·원래 값·바꾼 값·기대 규칙·심각도·파생(연쇄) 영향을 기록
- 정답은 검증기 출력과 무관하게 이 명세로만 정한다. 주입이 실제로 들어갔는지는 ① 정상 데이터와의 상태 비교(diff),
  ② 관계형 오류는 이 파일 안의 별도 조건 함수(검증기와 다른 코드)로 확인한다.
- 출력: data/canonical/e05/eval_set_v1.json (명세·정답), manifest_v1.json (데이터셋 해시·규모), verification_v1.json
  데이터셋 본문은 저장하지 않고 정답셋 v2 + 연산으로 매번 같은 값을 만든다 (해시로 확인).
"""

from __future__ import annotations

import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

import e05_dataset as D

CREATED = "2026-10-21"   # 명세 작성일 고정 (재생성해도 해시가 같도록)
SEED = 20261021   # 연산은 결정적이며 난수를 쓰지 않는다. 새 레코드 record_uid는 (데이터셋, 연산 번호) 해시
OUT = D.EVAL_DIR


def T(entity, where, many=False):
    return {"entity": entity, "where": where, **({"many": True} if many else {})}


def E(rule, ref, field):
    return {"rule": rule, "ref": ref, "field": field}


def inj(iid, code, desc, ops, expected, acceptable=(), derived=(), severity="ERROR", boundary=False):
    return {"id": iid, "error_code": code, "description": desc, "ops": ops, "expected": list(expected), "acceptable": list(acceptable),
            "derived": list(derived), "severity": severity, "boundary_case": boundary}


def S(entity, where, field, value):
    return {"op": "set", "entity": entity, "where": where, "field": field, "value": value}


def ADD(entity, copy_of=None, **values):
    return {"op": "add", "entity": entity, **({"copy_of": copy_of} if copy_of else {}), "values": values}


def RM(entity, where, many=False):
    return {"op": "remove", "entity": entity, "where": where, **({"many": True} if many else {})}


def injections(gt) -> list[dict]:
    idmap = list(csv.DictReader(open(D.ROOT / "data" / "canonical" / "vendor_id_map_v1.csv", encoding="utf-8")))
    vendor_m007 = next(r["vendor_code"] for r in idmap if r["entity"] == "Material" and r["canonical_id"] == "M007")
    sh = gt["entities"]["SalesHistory"]
    g0 = sh[0]["derived_from_record_uid"]
    g4 = sh[4]["derived_from_record_uid"]
    PL = "ProductionPlanLine"
    L = []
    # ---------- 구조 ----------
    L.append(inj("I-S01a", "ERR-MISSING", "주문 수량 null", [S("Order", {"order_id": "O004"}, "order_qty", None)],
                 [E("S01", T("Order", {"order_id": "O004"}), "order_qty")]))
    L.append(inj("I-S01b", "ERR-MISSING", "BOM 유효 시작일 빈 문자열 (NULL과 빈 문자열 경계)", [S("BOM", {"bom_id": "BOM-SF002-V1"}, "valid_from", "")],
                 [E("S01", T("BOM", {"bom_id": "BOM-SF002-V1"}), "valid_from")],
                 derived=[E("B06", T(PL, {"product_id": "SF002", "production_mode": "INHOUSE"}, True), "product_id")], boundary=True))
    L.append(inj("I-S02a", "ERR-NUMFMT", "자재 단가에 영문자 O (1O50)", [S("Material", {"material_id": "M004"}, "unit_cost", "1O50")],
                 [E("S02", T("Material", {"material_id": "M004"}), "unit_cost")]))
    L.append(inj("I-S02b", "ERR-NUMFMT", "공정 가공시간 문자", [S("Operation", {"operation_id": "OP-FG002-20"}, "run_time_per_unit_h", "abc")],
                 [E("S02", T("Operation", {"operation_id": "OP-FG002-20"}), "run_time_per_unit_h")]))
    L.append(inj("I-S03a", "ERR-DATE", "존재하지 않는 날짜 2026-02-30", [S("Order", {"order_id": "O007"}, "due_date", "2026-02-30")],
                 [E("S03", T("Order", {"order_id": "O007"}), "due_date")], acceptable=[{"rule": "V07"}]))
    L.append(inj("I-S03b", "ERR-DATE", "날짜 구분자 형식 오류 2026/11/15", [S("Inventory", {"item_id": "M006"}, "as_of_date", "2026/11/15")],
                 [E("S03", T("Inventory", {"item_id": "M006"}), "as_of_date")]))
    L.append(inj("I-S04a", "ERR-ENUM", "주문 상태 허용값 아님", [S("Order", {"order_id": "O010"}, "status", "PENDING")],
                 [E("S04", T("Order", {"order_id": "O010"}), "status")]))
    L.append(inj("I-S04b", "ERR-ENUM", "BOM 상태 소문자 approved", [S("BOM", {"bom_id": "BOM-FG003-V2"}, "status", "approved")],
                 [E("S04", T("BOM", {"bom_id": "BOM-FG003-V2"}), "status")], acceptable=[{"rule": "B03"}],
                 derived=[E("B06", T(PL, {"product_id": "FG003", "production_mode": "INHOUSE", "planned_qty": {">=": "500"}}, True), "product_id")]))
    L.append(inj("I-S05", "ERR-IDFMT", "record_uid 형식 오류", [S("Supplier", {"supplier_id": "S002"}, "record_uid", "REC_bad")],
                 [E("S05", T("Supplier", {"supplier_id": "S002"}), "record_uid")]))
    L.append(inj("I-S06a", "ERR-NUMFMT", "소요량 0 (> 0 경계)", [S("BOMLine", {"bom_id": "BOM-SF001-V1", "line_no": 2}, "qty_per", "0")],
                 [E("S06", T("BOMLine", {"bom_id": "BOM-SF001-V1", "line_no": 2}), "qty_per")], boundary=True))
    L.append(inj("I-S06b", "ERR-NUMFMT", "음수 주문 수량", [S("Order", {"order_id": "O011"}, "order_qty", "-5")],
                 [E("S06", T("Order", {"order_id": "O011"}), "order_qty")]))
    L.append(inj("I-S06c", "ERR-NUMFMT", "손실률 1 (< 1 경계)", [S("BOMLine", {"bom_id": "BOM-FG002-V1", "line_no": 2}, "scrap_rate", "1")],
                 [E("S06", T("BOMLine", {"bom_id": "BOM-FG002-V1", "line_no": 2}), "scrap_rate")], boundary=True))
    L.append(inj("I-S06d", "ERR-NUMFMT", "배분 비율 1.2 (≤ 1 위반)", [S("SalesHistory", {"record_uid": sh[0]["record_uid"]}, "allocation_share", "1.2")],
                 [E("S06", T("SalesHistory", {"record_uid": sh[0]["record_uid"]}), "allocation_share")],
                 derived=[E("B12", T("SalesHistory", {"derived_from_record_uid": g0}, True), "allocation_share")]))
    L.append(inj("I-S07", "ERR-MISSING", "선택 필드 site_id 빈 문자열", [S("BOM", {"bom_id": "BOM-FG001-V2"}, "site_id", "")],
                 [E("S07", T("BOM", {"bom_id": "BOM-FG001-V2"}), "site_id")], severity="WARNING",
                 derived=[E("B06", T(PL, {"product_id": "FG001", "production_mode": "INHOUSE", "period_start": {">=": "2026-12-01"}}, True), "product_id")], boundary=True))
    L.append(inj("I-S08a", "ERR-DUPID", "같은 자재 ID를 다른 이름·단가로 중복 등록", [ADD("Material", {"material_id": "M005"}, material_name="중복 자재", unit_cost="999")],
                 [E("S08", {"added": 0}, "*")], acceptable=[{"rule": "S08", "ref": T("Material", {"material_id": "M005", "material_name": {"!=": "중복 자재"}})}]))
    L.append(inj("I-S08b", "ERR-DUPID", "같은 주문 ID 중복", [ADD("Order", {"order_id": "O003"}, order_qty="1")],
                 [E("S08", {"added": 0}, "*")], acceptable=[{"rule": "S08", "ref": T("Order", {"order_id": "O003", "order_qty": {"!=": "1"}})}]))
    L.append(inj("I-S08c", "ERR-DUPID", "BOM 라인 키(bom_id, line_no) 중복", [ADD("BOMLine", {"bom_id": "BOM-FG003-V1", "line_no": 3}, qty_per="70")],
                 [E("S08", {"added": 0}, "*")], acceptable=[{"rule": "S08", "ref": T("BOMLine", {"bom_id": "BOM-FG003-V1", "line_no": 3, "qty_per": "80"})}, {"rule": "B10"}]))
    # ---------- 참조 ----------
    L.append(inj("I-R01", "ERR-BADREF", "없는 제품 참조 (주문)", [S("Order", {"order_id": "O013"}, "product_id", "FG009")],
                 [E("R01", T("Order", {"order_id": "O013"}), "product_id")], acceptable=[{"rule": "V08"}, {"rule": "B08"}]))
    L.append(inj("I-R02a", "ERR-BADREF", "없는 자재 참조 (BOM 라인)", [S("BOMLine", {"bom_id": "BOM-FG002-V1", "line_no": 3}, "component_material_id", "M099")],
                 [E("R02", T("BOMLine", {"bom_id": "BOM-FG002-V1", "line_no": 3}), "component_material_id")], acceptable=[{"rule": "B08"}]))
    L.append(inj("I-R02b", "ERR-BADREF", "매핑되지 않은 업체 자재 코드 그대로 사용 (불완전한 외부 코드 매핑)",
                 [S("BOMLine", {"bom_id": "BOM-SF002-V1", "line_no": 1}, "component_material_id", vendor_m007)],
                 [E("R02", T("BOMLine", {"bom_id": "BOM-SF002-V1", "line_no": 1}), "component_material_id")], acceptable=[{"rule": "B08"}], boundary=True))
    L.append(inj("I-R02c", "ERR-BADREF", "자재 마스터 레코드 삭제 → 참조 3건이 고아가 됨", [RM("Material", {"material_id": "M003"})],
                 [E("R02", T("BOMLine", {"component_material_id": "M003"}), "component_material_id"),
                  E("R02", T("SupplierMaterial", {"material_id": "M003"}), "material_id"),
                  E("R02", T("Inventory", {"item_id": "M003"}), "item_id")], acceptable=[{"rule": "B08"}, {"rule": "B11"}]))
    L.append(inj("I-R03", "ERR-BADREF", "없는 공급사 참조", [S("SupplierMaterial", {"supplier_id": "S004", "material_id": "M008"}, "supplier_id", "S099")],
                 [E("R03", T("SupplierMaterial", {"supplier_id": "S099"}), "supplier_id")]))
    L.append(inj("I-R04", "ERR-BADREF", "없는 BOM 참조 (BOM 라인)", [S("BOMLine", {"bom_id": "BOM-FG003-V2", "line_no": 3}, "bom_id", "BOM-FG003-V9")],
                 [E("R04", T("BOMLine", {"bom_id": "BOM-FG003-V9"}), "bom_id")]))
    L.append(inj("I-R05a", "ERR-RESREL", "공정이 없는 자원 참조", [S("Operation", {"operation_id": "OP-FG003-20"}, "resource_id", "R09")],
                 [E("R05", T("Operation", {"operation_id": "OP-FG003-20"}), "resource_id")]))
    L.append(inj("I-R05b", "ERR-RESREL", "계획 라인이 없는 자원 참조", [S(PL, {"plan_id": "PLAN-OT", "line_no": 5}, "resource_id", "R9")],
                 [E("R05", T(PL, {"plan_id": "PLAN-OT", "line_no": 5}), "resource_id")], acceptable=[{"rule": "V09"}]))
    L.append(inj("I-R06", "ERR-BADREF", "없는 계획 참조", [S(PL, {"plan_id": "PLAN-REG", "line_no": 5}, "plan_id", "PLAN-XX")],
                 [E("R06", T(PL, {"plan_id": "PLAN-XX", "line_no": 5}), "plan_id")], acceptable=[{"rule": "V12"}]))
    L.append(inj("I-R07", "ERR-UNIT", "Unit 목록에 없는 단위", [S("Inventory", {"item_id": "M006"}, "unit", "pcs")],
                 [E("R07", T("Inventory", {"item_id": "M006"}), "unit")], acceptable=[{"rule": "B08"}, {"rule": "V03"}]))
    # ---------- BOM·관계 ----------
    L.append(inj("I-B01a", "ERR-BOMCYCLE", "반제품 SF002 구성품에 완제품 FG003 추가 → FG003→SF002→FG003 순환",
                 [ADD("BOMLine", None, bom_id="BOM-SF002-V1", line_no=4, component_type="PRODUCT", component_material_id=None,
                      component_product_id="FG003", qty_per="1", unit="EA", scrap_rate="0", line_type="ITEM", origin_class="SYNTHETIC")],
                 [E("B01", {"added": 0}, "component_product_id")],
                 acceptable=[{"rule": "B01", "ref": T("BOMLine", {"component_product_id": "SF002"}, True)}]))
    L.append(inj("I-B01b", "ERR-BOMCYCLE", "자기 참조 SF001→SF001",
                 [ADD("BOMLine", None, bom_id="BOM-SF001-V1", line_no=4, component_type="PRODUCT", component_material_id=None,
                      component_product_id="SF001", qty_per="1", unit="EA", scrap_rate="0", line_type="ITEM", origin_class="SYNTHETIC")],
                 [E("B01", {"added": 0}, "component_product_id")]))
    L.append(inj("I-B02a", "ERR-BOMVER", "FG002에 V1과 모든 조건이 겹치는 활성 V2 추가",
                 [ADD("BOM", {"bom_id": "BOM-FG002-V1"}, bom_id="BOM-FG002-V2", bom_version="V2")],
                 [E("B02", {"added": 0}, "*")], acceptable=[{"rule": "B02", "ref": T("BOM", {"bom_id": "BOM-FG002-V1"})}],
                 derived=[E("B06", T(PL, {"product_id": "FG002", "production_mode": "INHOUSE"}, True), "product_id"), E("B09", {"added": 0}, "*")]))
    L.append(inj("I-B02b", "ERR-BOMVER", "교체일 하루 겹침 (V1 종료일 = V2 시작일, 종료일 포함 규칙 경계)",
                 [S("BOM", {"bom_id": "BOM-FG001-V1"}, "valid_to", "2026-12-01")],
                 [E("B02", T("BOM", {"bom_id": "BOM-FG001-V1"}), "*")], acceptable=[{"rule": "B02", "ref": T("BOM", {"bom_id": "BOM-FG001-V2"})}], boundary=True))
    L.append(inj("I-B02c", "ERR-BOMVER", "수량 구간 겹침 (V1 상한 500→600, V2 하한 500)",
                 [S("BOM", {"bom_id": "BOM-FG003-V1"}, "max_qty", "600")],
                 [E("B02", T("BOM", {"bom_id": "BOM-FG003-V1"}), "*")], acceptable=[{"rule": "B02", "ref": T("BOM", {"bom_id": "BOM-FG003-V2"})}],
                 derived=[E("B06", T(PL, {"product_id": "FG003", "production_mode": "INHOUSE", "planned_qty": {">=": "500"}}, True), "product_id")]))
    L.append(inj("I-B03", "ERR-BOMVER", "미승인(DRAFT) 버전이 활성", [S("BOM", {"bom_id": "BOM-SF001-V1"}, "status", "DRAFT")],
                 [E("B03", T("BOM", {"bom_id": "BOM-SF001-V1"}), "status")],
                 derived=[E("B06", T(PL, {"product_id": "SF001", "production_mode": "INHOUSE"}, True), "product_id")]))
    L.append(inj("I-B04", "ERR-BOMVER", "같은 제품·버전 표기 중복 (비활성 사본)",
                 [ADD("BOM", {"bom_id": "BOM-FG002-V1"}, bom_id="BOM-FG002-V1B", is_active=False)],
                 [E("B04", {"added": 0}, "*")], acceptable=[{"rule": "B04", "ref": T("BOM", {"bom_id": "BOM-FG002-V1"})}],
                 derived=[E("B09", {"added": 0}, "*")]))
    L.append(inj("I-B05a", "ERR-BOMVER", "valid_to < valid_from", [S("BOM", {"bom_id": "BOM-SF002-V1"}, "valid_to", "2025-12-31")],
                 [E("B05", T("BOM", {"bom_id": "BOM-SF002-V1"}), "valid_to")],
                 derived=[E("B06", T(PL, {"product_id": "SF002", "production_mode": "INHOUSE"}, True), "product_id")]))
    L.append(inj("I-B05b", "ERR-BOMVER", "max_qty ≤ min_qty", [S("BOM", {"bom_id": "BOM-FG003-V2"}, "max_qty", "400")],
                 [E("B05", T("BOM", {"bom_id": "BOM-FG003-V2"}), "max_qty")],
                 derived=[E("B06", T(PL, {"product_id": "FG003", "production_mode": "INHOUSE", "planned_qty": {">=": "500"}}, True), "product_id")]))
    L.append(inj("I-B06", "ERR-BOMVER", "FG002 유일 버전 종료일을 11-20으로 → 11-23 이후 계획 라인에 적용 BOM 없음",
                 [S("BOM", {"bom_id": "BOM-FG002-V1"}, "valid_to", "2026-11-20")],
                 [E("B06", T(PL, {"product_id": "FG002", "production_mode": "INHOUSE", "period_start": {">=": "2026-11-23"}}, True), "product_id")]))
    L.append(inj("I-B07", "ERR-BADREF", "component_type PRODUCT인데 자재 ID만 있음", [S("BOMLine", {"bom_id": "BOM-FG001-V1", "line_no": 3}, "component_type", "PRODUCT")],
                 [E("B07", T("BOMLine", {"bom_id": "BOM-FG001-V1", "line_no": 3}), "component_type")], acceptable=[{"rule": "R01"}, {"rule": "B08"}]))
    L.append(inj("I-B08a", "ERR-UNIT", "kg 자재(M004)에 EA", [S("BOMLine", {"bom_id": "BOM-SF001-V1", "line_no": 3}, "unit", "EA")],
                 [E("B08", T("BOMLine", {"bom_id": "BOM-SF001-V1", "line_no": 3}), "unit")]))
    L.append(inj("I-B08b", "ERR-UNIT", "EA 제품 주문에 kg", [S("Order", {"order_id": "O014"}, "unit", "kg")],
                 [E("B08", T("Order", {"order_id": "O014"}), "unit")]))
    L.append(inj("I-B09", "ERR-BOMVER", "BOM의 라인 전부 삭제 (구성품 누락)", [RM("BOMLine", {"bom_id": "BOM-SF002-V1"}, True)],
                 [E("B09", T("BOM", {"bom_id": "BOM-SF002-V1"}), "*")], severity="WARNING"))
    L.append(inj("I-B10", "ERR-DUPID", "같은 BOM에 같은 구성품 라인 추가", [ADD("BOMLine", {"bom_id": "BOM-FG001-V2", "line_no": 3}, line_no=5)],
                 [E("B10", {"added": 0}, "*")], acceptable=[{"rule": "B10", "ref": T("BOMLine", {"bom_id": "BOM-FG001-V2", "line_no": 3})}], severity="WARNING"))
    L.append(inj("I-B11a", "ERR-DUPID", "자재 M001 우선 공급사 2개", [S("SupplierMaterial", {"supplier_id": "S002", "material_id": "M001"}, "is_preferred", True)],
                 [E("B11", T("SupplierMaterial", {"supplier_id": "S002", "material_id": "M001"}), "is_preferred")],
                 acceptable=[{"rule": "B11", "ref": T("SupplierMaterial", {"material_id": "M001"}, True)}]))
    L.append(inj("I-B11b", "ERR-DUPID", "자재 M007 우선 공급사 0개", [S("SupplierMaterial", {"supplier_id": "S003", "material_id": "M007"}, "is_preferred", False)],
                 [E("B11", T("SupplierMaterial", {"material_id": "M007"}, True), "is_preferred")]))
    L.append(inj("I-B12", "ERR-NUMFMT", "배분 비율 합 ≠ 1", [S("SalesHistory", {"record_uid": sh[1]["record_uid"]}, "allocation_share",
                                                         str(Decimal(sh[1]["allocation_share"]) + Decimal("0.1")))],
                 [E("B12", T("SalesHistory", {"record_uid": sh[1]["record_uid"]}), "allocation_share")],
                 acceptable=[{"rule": "B12", "ref": T("SalesHistory", {"derived_from_record_uid": sh[1]["derived_from_record_uid"]}, True)}]))
    L.append(inj("I-B13", "ERR-MISSING", "ALLOCATED 행의 원본 레코드 없음", [S("SalesHistory", {"record_uid": sh[4]["record_uid"]}, "derived_from_record_uid", None)],
                 [E("B13", T("SalesHistory", {"record_uid": sh[4]["record_uid"]}), "derived_from_record_uid")],
                 derived=[E("B12", T("SalesHistory", {"derived_from_record_uid": g4}, True), "allocation_share")]))
    L.append(inj("I-B14", "ERR-MISSING", "외주 불가 제품에 외주 단가", [S("Product", {"product_id": "FG001"}, "outsourcing_unit_cost", "5000")],
                 [E("B14", T("Product", {"product_id": "FG001"}), "outsourcing_unit_cost")]))
    # ---------- 업무 ----------
    L.append(inj("I-V01", "ERR-INVQTY", "음수 보유 재고", [S("Inventory", {"item_id": "M007"}, "on_hand_qty", "-10")],
                 [E("V01", T("Inventory", {"item_id": "M007"}), "on_hand_qty")], acceptable=[{"rule": "V02"}]))
    L.append(inj("I-V02", "ERR-INVQTY", "할당 80 > 보유 60 (E01-ERR-012와 같은 위치)", [S("Inventory", {"item_id": "FG002"}, "allocated_qty", "80")],
                 [E("V02", T("Inventory", {"item_id": "FG002"}), "allocated_qty")]))
    L.append(inj("I-V03", "ERR-INVQTY", "EA 재고 소수 수량", [S("Inventory", {"item_id": "M008"}, "on_hand_qty", "999.5")],
                 [E("V03", T("Inventory", {"item_id": "M008"}), "on_hand_qty")]))
    L.append(inj("I-V04", "ERR-INVQTY", "같은 품목·기준일 재고 중복", [ADD("Inventory", {"item_id": "M002"}, on_hand_qty="450")],
                 [E("V04", {"added": 0}, "*")], acceptable=[{"rule": "V04", "ref": T("Inventory", {"item_id": "M002", "on_hand_qty": "500"})}]))
    L.append(inj("I-V05", "ERR-DATE", "입고 예정 수량 있는데 예정일 없음", [S("Inventory", {"item_id": "M006"}, "on_order_qty", "50")],
                 [E("V05", T("Inventory", {"item_id": "M006"}), "expected_receipt_date")]))
    L.append(inj("I-V06", "ERR-DATE", "재고 기준일이 데이터셋 기준일 이후", [S("Inventory", {"item_id": "M010"}, "as_of_date", "2026-11-20")],
                 [E("V06", T("Inventory", {"item_id": "M010"}), "as_of_date")]))
    L.append(inj("I-V07", "ERR-DATE", "납기 < 주문일 (E01-ERR-009와 같은 주문)", [S("Order", {"order_id": "O012"}, "due_date", "2026-10-01")],
                 [E("V07", T("Order", {"order_id": "O012"}), "due_date")]))
    L.append(inj("I-V08", "ERR-RESREL", "FG002 공정 전부 삭제 → 주문·계획 제품에 공정 없음", [RM("Operation", {"product_id": "FG002"}, True)],
                 [E("V08", T("Order", {"product_id": "FG002", "status": "OPEN"}, True), "product_id"),
                  E("V08", T(PL, {"product_id": "FG002", "production_mode": "INHOUSE"}, True), "product_id")],
                 derived=[E("V09", T(PL, {"product_id": "FG002", "production_mode": "INHOUSE"}, True), "resource_id")]))
    L.append(inj("I-V09", "ERR-RESREL", "계획 라인 자원이 제품 공정에 없는 자원", [S(PL, {"plan_id": "PLAN-REG", "line_no": 1}, "resource_id", "R3")],
                 [E("V09", T(PL, {"plan_id": "PLAN-REG", "line_no": 1}), "resource_id")]))
    L.append(inj("I-V10", "ERR-RESREL", "외주 라인에 자원", [S(PL, {"plan_id": "PLAN-OUT", "line_no": 9}, "resource_id", "R1")],
                 [E("V10", T(PL, {"plan_id": "PLAN-OUT", "line_no": 9}), "resource_id")]))
    L.append(inj("I-V11", "ERR-RESREL", "외주 불가 제품(FG001)의 외주 라인",
                 [S(PL, {"plan_id": "PLAN-REG", "line_no": 2}, "production_mode", "OUTSOURCE"), S(PL, {"plan_id": "PLAN-REG", "line_no": 2}, "resource_id", None)],
                 [E("V11", T(PL, {"plan_id": "PLAN-REG", "line_no": 2}), "production_mode")], severity="WARNING"))
    L.append(inj("I-V12", "ERR-DATE", "계획 라인 기간이 계획 기간 밖", [S(PL, {"plan_id": "PLAN-OT", "line_no": 3}, "period_start", "2026-12-21")],
                 [E("V12", T(PL, {"plan_id": "PLAN-OT", "line_no": 3}), "period_start")], severity="WARNING"))
    return L


def pass_cases() -> list[dict]:
    PL = "ProductionPlanLine"
    return [
        inj("P-01", None, "할당 = 보유 (≤ 경계, 정상)", [S("Inventory", {"item_id": "FG003"}, "allocated_qty", "90")], [], boundary=True),
        inj("P-02", None, "FG003 계획 수량 정확히 500 → V2만 후보 (min 포함·max 미포함 경계, 정상)",
            [S(PL, {"plan_id": "PLAN-REG", "product_id": "FG003", "period_start": "2026-11-16"}, "planned_qty", "500")], [], boundary=True),
        inj("P-03", None, "손실률 0.99 (< 1, 정상)", [S("BOMLine", {"bom_id": "BOM-FG002-V1", "line_no": 2}, "scrap_rate", "0.99")], [], boundary=True),
        inj("P-04", None, "계획 수량 0 (≥ 0, 정상)", [S(PL, {"plan_id": "PLAN-REG", "line_no": 1}, "planned_qty", "0")], [], boundary=True),
        inj("P-05", None, "3단계 BOM: SF001 구성품에 SF002 추가 (순환 아님, 정상)",
            [ADD("BOMLine", None, bom_id="BOM-SF001-V1", line_no=4, component_type="PRODUCT", component_material_id=None, component_product_id="SF002",
                 qty_per="1", unit="EA", scrap_rate="0", line_type="ITEM", origin_class="SYNTHETIC")], [], boundary=True),
        inj("P-06", None, "kg 자재 재고를 g로 표기 (같은 차원 다른 단위, 정상)",
            [S("Inventory", {"item_id": "M001"}, "unit", "g"), S("Inventory", {"item_id": "M001"}, "on_hand_qty", "800000")], [], boundary=True),
        inj("P-07", None, "소요량 0.001 (> 0, 정상)", [S("BOMLine", {"bom_id": "BOM-FG003-V2", "line_no": 3}, "qty_per", "0.001")], [], boundary=True),
        inj("P-08", None, "납기 = 주문일 (≥ 경계, 정상)", [S("Order", {"order_id": "O001"}, "due_date", "2026-11-02")], [], boundary=True),
        inj("P-09", None, "소수 없는 큰 EA 재고 1000000 (V03 경계, 정상)",
            [S("Inventory", {"item_id": "M010"}, "on_hand_qty", "1000000")], [], boundary=True),
    ]


def compound(singles: dict) -> list[dict]:
    """복합 오류: 독립 오류 묶음, 상호작용 묶음, 같은 레코드 다중 오류."""
    def merge(cid, desc, ids, extra_ops=(), extra_expected=(), drop=(), note=None, extra_acceptable=(), extra_derived=()):
        ops, exp, acc, der = [], [], [], []
        for iid in ids:
            s = singles[iid]
            off = len(ops)
            shift = lambda r: {"added": r["added"] + off} if "added" in r else r
            ops += s["ops"]
            exp += [{**x, "ref": shift(x["ref"]), "from": iid} for x in s["expected"] if (iid, x["rule"]) not in drop]
            acc += [{**x, **({"ref": shift(x["ref"])} if "ref" in x else {})} for x in s["acceptable"]]
            der += [{**x, "ref": shift(x["ref"])} for x in s["derived"]]
        off = len(ops)
        ops += list(extra_ops)
        exp += [{**x, "ref": {"added": x["ref"]["added"] + off} if "added" in x["ref"] else x["ref"], "from": cid} for x in extra_expected]
        return {"id": cid, "error_code": "COMPOUND", "description": desc, "ops": ops, "expected": exp, "acceptable": acc + list(extra_acceptable),
                "derived": der + list(extra_derived), "severity": "ERROR", "boundary_case": False, "components": list(ids), "interaction_note": note}
    return [
        merge("C-1", "서로 다른 엔터티의 독립 오류 5개", ["I-S01a", "I-R02a", "I-V02", "I-B02c", "I-S04a"]),
        merge("C-2", "상호작용: 자재 삭제(고아 참조) + 자재 ID 중복 + BOM 라인 전부 삭제 뒤 순환 라인 추가",
              ["I-R02c", "I-S08a", "I-B09", "I-B01a"], drop={("I-B09", "B09")},
              note="I-B09로 SF002 라인을 지운 뒤 I-B01a가 SF002에 순환 라인을 추가하므로 SF002 BOM은 라인 1개 → B09(라인 없음)는 성립하지 않음 (정답에서 제외)",
              extra_acceptable=[{"rule": "B09"}]),
        merge("C-3", "같은 레코드에 여러 오류: 주문 O015(날짜·상태·제품) / 재고 M009(음수·단위·기준일) / BOM FG002-V1(상태 소문자 + 종료일 < 시작일)", [],
              extra_ops=[S("Order", {"order_id": "O015"}, "due_date", "2026-02-30"), S("Order", {"order_id": "O015"}, "status", "PENDING"),
                         S("Order", {"order_id": "O015"}, "product_id", "FG009"),
                         S("Inventory", {"item_id": "M009"}, "on_hand_qty", "-5"), S("Inventory", {"item_id": "M009"}, "unit", "pcs"),
                         S("Inventory", {"item_id": "M009"}, "as_of_date", "2026-11-30"),
                         S("BOM", {"bom_id": "BOM-FG002-V1"}, "status", "approved"), S("BOM", {"bom_id": "BOM-FG002-V1"}, "valid_to", "2025-01-01")],
              extra_expected=[E("S03", T("Order", {"order_id": "O015"}), "due_date"), E("S04", T("Order", {"order_id": "O015"}), "status"),
                              E("R01", T("Order", {"order_id": "O015"}), "product_id"),
                              E("V01", T("Inventory", {"item_id": "M009"}), "on_hand_qty"), E("R07", T("Inventory", {"item_id": "M009"}), "unit"),
                              E("V06", T("Inventory", {"item_id": "M009"}), "as_of_date"),
                              E("S04", T("BOM", {"bom_id": "BOM-FG002-V1"}), "status"), E("B05", T("BOM", {"bom_id": "BOM-FG002-V1"}), "valid_to")],
              note="pydantic은 필드 오류가 있으면 model_validator를 실행하지 않으므로 BOM FG002-V1의 B05(종료일 < 시작일)가 가려질 수 있음 — 정답에는 포함",
              extra_acceptable=[{"rule": "V08"}, {"rule": "V02"}, {"rule": "B03"}, {"rule": "B08"}, {"rule": "V03"}],
              extra_derived=[E("B06", T("ProductionPlanLine", {"product_id": "FG002", "production_mode": "INHOUSE"}, True), "product_id")]),
    ]


# ---------- 독립 확인 (검증기와 다른 코드) ----------

def diff(before: dict, after: dict) -> dict:
    out = {"added": [], "removed": [], "changed": []}
    for ent in D.ENTITY_ORDER:
        b = {r["record_uid"]: r for r in before[ent]}
        a = {r["record_uid"]: r for r in after[ent]}
        # record_uid 자체를 바꾼 주입(I-S05)은 삭제+추가로 보인다
        out["added"] += [(ent, u) for u in a if u not in b]
        out["removed"] += [(ent, u) for u in b if u not in a]
        for u in set(a) & set(b):
            for k in set(a[u]) | set(b[u]):
                if a[u].get(k) != b[u].get(k):
                    out["changed"].append((ent, u, k, b[u].get(k), a[u].get(k)))
    return out


def reach_cycle(ents) -> set[str]:
    """반제품 구성 그래프에서 자기 자신으로 돌아오는 제품 (단순 반복 확장)."""
    bom_prod = {b["bom_id"]: b["product_id"] for b in ents["BOM"]}
    edges = {}
    for l in ents["BOMLine"]:
        if l.get("component_type") == "PRODUCT" and l.get("component_product_id") and l["bom_id"] in bom_prod:
            edges.setdefault(bom_prod[l["bom_id"]], set()).add(l["component_product_id"])
    out = set()
    for p in edges:
        seen, frontier = set(), set(edges[p])
        while frontier:
            if p in frontier:
                out.add(p)
                break
            seen |= frontier
            frontier = {c for f in frontier for c in edges.get(f, ())} - seen
    return out


def condition_checks(iid: str, ents: dict) -> dict | None:
    """관계형 주입이 의도한 조건을 실제로 만들었는지 (검증기 코드와 별도 구현)."""
    bom = {b["bom_id"]: b for b in ents["BOM"]}
    if iid in ("I-B01a", "I-B01b"):
        return {"cycle_products": sorted(reach_cycle(ents)), "ok": bool(reach_cycle(ents))}
    if iid == "I-B02a":
        return {"both_active_same_window": bom["BOM-FG002-V2"]["valid_from"] == bom["BOM-FG002-V1"]["valid_from"], "ok": True}
    if iid == "I-B02b":
        return {"v1_to": bom["BOM-FG001-V1"]["valid_to"], "v2_from": bom["BOM-FG001-V2"]["valid_from"],
                "ok": bom["BOM-FG001-V1"]["valid_to"] >= bom["BOM-FG001-V2"]["valid_from"]}
    if iid == "I-B02c":
        return {"ok": Decimal(bom["BOM-FG003-V2"]["min_qty"]) < Decimal(bom["BOM-FG003-V1"]["max_qty"])}
    if iid == "I-B06":
        lines = [l for l in ents["ProductionPlanLine"] if l["product_id"] == "FG002" and l["period_start"] > bom["BOM-FG002-V1"]["valid_to"]]
        return {"lines_after_valid_to": len(lines), "ok": bool(lines)}
    if iid in ("I-B11a", "I-B11b"):
        m = "M001" if iid.endswith("a") else "M007"
        n = sum(1 for s in ents["SupplierMaterial"] if s["material_id"] == m and s["is_preferred"])
        return {"preferred_count": n, "ok": n != 1}
    if iid == "I-B12":
        g = {}
        for s in ents["SalesHistory"]:
            if s["derived_from_record_uid"]:
                g[s["derived_from_record_uid"]] = g.get(s["derived_from_record_uid"], Decimal(0)) + Decimal(s["allocation_share"])
        bad = [k for k, v in g.items() if abs(v - 1) > Decimal("0.0005")]
        return {"groups_not_one": len(bad), "ok": len(bad) == 1}
    if iid == "I-V08":
        return {"fg002_ops": sum(1 for o in ents["Operation"] if o["product_id"] == "FG002"), "ok": not any(o["product_id"] == "FG002" for o in ents["Operation"])}
    return None


def build_truth(item: dict, after: dict, before: dict, effects: list[dict]) -> dict:
    def res(ref):
        return D.resolve(after, before, ref, effects)
    return {
        "expected": [{"rule": x["rule"], "record_uids": res(x["ref"]), "field": x["field"], **({"from": x["from"]} if "from" in x else {})} for x in item["expected"]],
        "acceptable": [{"rule": x["rule"], "record_uids": res(x["ref"]) if "ref" in x else None} for x in item["acceptable"]],
        "derived": [{"rule": x["rule"], "record_uids": res(x["ref"]), "field": x.get("field")} for x in item["derived"]],
    }


def main() -> int:
    gt = D.load_gt()
    clean = gt["entities"]
    singles = injections(gt)
    by_id = {s["id"]: s for s in singles}
    items = [("clean", {"id": "clean", "ops": [], "expected": [], "acceptable": [], "derived": [], "severity": None, "description": "E01 정답셋 v2 그대로"})]
    items += [("single", s) for s in singles] + [("pass", p) for p in pass_cases()] + [("compound", c) for c in compound(by_id)]
    datasets, verification = [], []
    for kind, it in items:
        after, effects = D.apply_ops(clean, it["ops"], it["id"])
        d = diff(clean, after)
        # 상태 비교: 연산마다 실제 변경이 있었는지, 선언하지 않은 변경이 없는지
        declared_set = {(e["entity"], e["record_uid"], e["field"]) for e in effects if e["kind"] == "set"}
        noop = [e for e in effects if e["kind"] == "set" and e["old"] == e["new"]]
        uid_change = {(e["entity"], e["new"]) for e in effects if e["kind"] == "set" and e["field"] == "record_uid"}
        changed = {(c[0], c[1], c[2]) for c in d["changed"]}
        undeclared = sorted(changed - declared_set)
        adds_ok = {(e["entity"], e["record_uid"]) for e in effects if e["kind"] == "add"} | uid_change == set(d["added"])
        cond = condition_checks(it["id"], after)
        truth = build_truth(it, after, clean, effects)
        empty_targets = [x["rule"] for x in truth["expected"] if not x["record_uids"]]
        ok = not noop and not undeclared and adds_ok and not empty_targets and (cond is None or cond["ok"])
        verification.append({"dataset_id": it["id"], "kind": kind, "effects": len(effects), "noop_ops": len(noop), "undeclared_changes": undeclared,
                             "adds_match_diff": adds_ok, "expected_without_target": empty_targets, "condition_check": cond, "ok": ok})
        datasets.append({"dataset_id": it["id"], "kind": kind, "description": it["description"], "error_code": it.get("error_code"),
                         "severity": it["severity"], "boundary_case": it.get("boundary_case", False), "components": it.get("components"),
                         "interaction_note": it.get("interaction_note"), "ops": it["ops"],
                         "injection_record": [{k: e.get(k) for k in ("kind", "entity", "record_uid", "field", "old", "new")} for e in effects],
                         "truth": truth, "dataset_sha256": D.dataset_sha256(after),
                         "records": sum(len(v) for v in after.values())})
    spec = {"schema": "chungpamo.e05_eval_set", "version": "v1", "created": CREATED, "seed": SEED,
            "base": {"file": "data/canonical/ground_truth_v2.json", "sha256": D.GT_SHA256},
            "reference_date": gt["parameters"]["reference_date"], "site_id": gt["parameters"]["site_id"],
            "truth_rules": "expected = 반드시 보고돼야 하는 (규칙, 레코드, 필드). acceptable = 같은 원인으로 보고돼도 오탐이 아닌 규칙(레코드 생략 시 대상 레코드 아무거나). "
                           "derived = 연쇄로 생기는 보고 (탐지율·오탐에서 제외, 따로 집계). 정답은 검증기 출력과 무관하게 이 생성기에서만 정한다",
            "datasets": datasets}
    OUT.mkdir(parents=True, exist_ok=True)
    blob = (json.dumps(spec, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    (OUT / "eval_set_v1.json").write_bytes(blob)
    import hashlib
    manifest = {"eval_set_sha256": hashlib.sha256(blob).hexdigest(), "base_sha256": D.GT_SHA256,
                "counts": {k: sum(1 for d in datasets if d["kind"] == k) for k in ("clean", "single", "pass", "compound")},
                "expected_items": sum(len(d["truth"]["expected"]) for d in datasets),
                "datasets": [{k: d[k] for k in ("dataset_id", "kind", "dataset_sha256", "records")} for d in datasets]}
    (OUT / "manifest_v1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (OUT / "verification_v1.json").write_text(json.dumps(verification, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    bad = [v["dataset_id"] for v in verification if not v["ok"]]
    print(json.dumps({"eval_set_sha256": manifest["eval_set_sha256"], "counts": manifest["counts"], "expected_items": manifest["expected_items"],
                      "verification_failed": bad}, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
