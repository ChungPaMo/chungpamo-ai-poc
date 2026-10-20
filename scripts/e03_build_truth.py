"""E03 1단계: 문서 샘플 정답 명세 생성 (문서 파일은 만들지 않음).

    .\\.venv\\Scripts\\python.exe scripts\\e03_build_truth.py

E01 canonical v2(data/canonical/ground_truth_v2.json)를 읽기만 하고, 문서 형식별로 렌더링할 내용의 정답
(텍스트 블록·순서, 표·행·열·셀, 병합, 숫자·단위·날짜, 계획 위치, canonical 연결)을
data/canonical/e03_document_truth_v1.json 에 쓴다. 파서 출력은 사용하지 않는다.

문서 생성기(다음 단계, 패키지 승인 후)는 이 명세를 원천으로 렌더링하고, 생성 시 실제 위치(PDF bbox, PPTX shape id 등)를
`actual_location`으로 덧붙인다. 그 전까지 위치는 `planned_location`(논리 위치)만 있다.
"""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "data" / "canonical" / "ground_truth_v2.json"
GT_SHA256 = "262dbe75dbfaf8c0c32003144d62e0b2057c61187dce4b548a457cf8819fc48e"
OUT = ROOT / "data" / "canonical" / "e03_document_truth_v1.json"


def num(x) -> str:
    """문서 표기용 숫자: 천 단위 쉼표, 불필요한 0 제거."""
    d = Decimal(str(x)).normalize()
    s = format(d, "f")
    whole, _, frac = s.partition(".")
    return f"{int(whole):,}" + (f".{frac}" if frac else "")


def plain(x) -> str:
    return format(Decimal(str(x)).normalize(), "f")


class Doc:
    def __init__(self, set_id: str, title: str) -> None:
        self.set_id = set_id
        self.title = title
        self.blocks, self.tables, self.values = [], [], []

    def block(self, btype: str, text: str, link=None) -> str:
        bid = f"{self.set_id}-b{len(self.blocks) + 1:02d}"
        self.blocks.append({"block_id": bid, "type": btype, "order": len(self.blocks), "text": text, "links": link or []})
        return bid

    def table(self, tid: str, caption: str, header: list[list], merges: list[dict], rows: list[list], header_rows: int,
              cell_refs: dict, continuation=None) -> None:
        n_cols = len(header[0])
        cells = []
        merged_cover = set()
        for m in merges:
            for r in range(m["row"], m["row"] + m["rowspan"]):
                for c in range(m["col"], m["col"] + m["colspan"]):
                    if (r, c) != (m["row"], m["col"]):
                        merged_cover.add((r, c))
        grid = header + rows
        for r, row in enumerate(grid, start=1):
            assert len(row) == n_cols, (tid, r, row)
            for c, text in enumerate(row, start=1):
                if (r, c) in merged_cover:
                    continue
                m = next((m for m in merges if (m["row"], m["col"]) == (r, c)), None)
                cell = {"row": r, "col": c, "rowspan": m["rowspan"] if m else 1, "colspan": m["colspan"] if m else 1,
                        "text": text, "is_header": r <= header_rows}
                if (r, c) in cell_refs:
                    cell["canonical_ref"] = cell_refs[(r, c)]["ref"]
                    self.values.append({"field": cell_refs[(r, c)]["field"], "raw": text, "value": cell_refs[(r, c)]["value"],
                                        "unit": cell_refs[(r, c)].get("unit"), "source": {"table_id": tid, "row": r, "col": c},
                                        "canonical_ref": cell_refs[(r, c)]["ref"],
                                        "derived_rule": cell_refs[(r, c)].get("derived_rule")})
                cells.append(cell)
        self.tables.append({"table_id": tid, "caption": caption, "n_rows": len(grid), "n_cols": n_cols, "header_rows": header_rows,
                            "merged_ranges": merges, "cells": cells, "continuation": continuation})

    def to_json(self) -> dict:
        return {"content_set": self.set_id, "title": self.title, "blocks": self.blocks, "tables": self.tables,
                "extracted_values": self.values}


def ref(entity: str, rec: dict, field: str) -> dict:
    return {"entity": entity, "record_uid": rec["record_uid"], "field": field}


def build(gt: dict) -> dict:
    E, X = gt["entities"], gt["expected"]
    prod = {p["product_id"]: p for p in E["Product"]}
    mat = {m["material_id"]: m for m in E["Material"]}
    unit = {u["unit_code"]: u for u in E["Unit"]}
    name = lambda i: (mat.get(i) or prod.get(i))["material_name" if i in mat else "product_name"]

    # ---------------- CS1: FG001 BOM 사양서 (V1 → V2 변경) ----------------
    cs1 = Doc("CS1", "FG001 가정용 히터 A — BOM 사양서 (BOM Specification)")
    bv1 = next(b for b in E["BOM"] if b["bom_id"] == "BOM-FG001-V1")
    bv2 = next(b for b in E["BOM"] if b["bom_id"] == "BOM-FG001-V2")
    cs1.block("heading", cs1.title)
    cs1.block("paragraph", f"문서번호 Doc No.: SPEC-FG001 / 개정 Rev. {bv2['bom_version']} / 적용일 Effective: {bv2['valid_from']}",
              [{"canonical_ref": ref("BOM", bv2, "bom_version")}, {"canonical_ref": ref("BOM", bv2, "valid_from")}])
    m1v1 = next(l for l in E["BOMLine"] if l["bom_id"] == "BOM-FG001-V1" and l["component_material_id"] == "M001")
    m1v2 = next(l for l in E["BOMLine"] if l["bom_id"] == "BOM-FG001-V2" and l["component_material_id"] == "M001")
    cs1.block("paragraph",
              f"표 1은 {bv1['bom_version']} 구성({bv1['valid_from']}~{bv1['valid_to']}), 표 2는 {bv2['bom_version']} 구성({bv2['valid_from']}~)이다. "
              f"{bv2['bom_version']}에서 강판(M001) 소요량이 {num(m1v1['qty_per'])} {m1v1['unit']}에서 {num(m1v2['qty_per'])} {m1v2['unit']}으로 바뀌었다 "
              f"(The steel sheet quantity changed from {plain(m1v1['qty_per'])} {m1v1['unit']} to {plain(m1v2['qty_per'])} {m1v2['unit']}).",
              [{"table_id": "CS1-T1", "row": 4, "canonical_ref": ref("BOMLine", m1v1, "qty_per")},
               {"table_id": "CS1-T2", "row": 4, "canonical_ref": ref("BOMLine", m1v2, "qty_per")}])
    header = [["순번 No.", "구성품 Component", "", "소요량 Qty per unit", "", "손실률(%)"],
              ["", "코드 Code", "품목명 Name", "수량 Qty", "단위 Unit", ""]]
    merges = [{"row": 1, "col": 1, "rowspan": 2, "colspan": 1}, {"row": 1, "col": 2, "rowspan": 1, "colspan": 2},
              {"row": 1, "col": 4, "rowspan": 1, "colspan": 2}, {"row": 1, "col": 6, "rowspan": 2, "colspan": 1}]
    for tid, bom in (("CS1-T1", bv1), ("CS1-T2", bv2)):
        lines = sorted((l for l in E["BOMLine"] if l["bom_id"] == bom["bom_id"]), key=lambda l: l["line_no"])
        rows, refs = [], {}
        for i, l in enumerate(lines):
            comp = l["component_material_id"] or l["component_product_id"]
            r = 3 + i
            rows.append([str(l["line_no"]), comp, name(comp), num(l["qty_per"]), l["unit"], plain(Decimal(l["scrap_rate"]) * 100)])
            refs[(r, 2)] = {"field": "component_id", "value": comp, "ref": ref("BOMLine", l, "component_material_id" if l["component_material_id"] else "component_product_id")}
            refs[(r, 4)] = {"field": "qty_per", "value": plain(l["qty_per"]), "unit": l["unit"], "ref": ref("BOMLine", l, "qty_per")}
        cs1.table(tid, f"표 {tid[-1]}. FG001 BOM {bom['bom_version']} ({bom['valid_from']}~{bom['valid_to'] or ''})", header, merges,
                  rows, 2, refs)
    cs1.block("footnote", "※ 반제품 SF001(히터 코어 모듈)은 별도 BOM(BOM-SF001-V1)으로 관리한다. Semi-finished SF001 has its own BOM.")

    # ---------------- CS2: 주문·재고 현황 보고서 ----------------
    cs2 = Doc("CS2", "주문·재고 현황 보고서 (Order & Inventory Report) — 기준일 " + gt["parameters"]["reference_date"])
    cs2.block("heading", cs2.title)
    open_n = sum(1 for o in E["Order"] if o["status"] == "OPEN")
    cs2.block("paragraph", f"전체 주문 {len(E['Order'])}건 중 진행(OPEN) {open_n}건, 완료 1건, 취소 1건이다. 표 1의 주문은 납기순이 아니라 주문번호순이다.")
    header = [["주문번호 Order No.", "제품 Product", "", "수량 Qty", "납기 Due date", "상태 Status"],
              ["", "코드 Code", "제품명 Name", "", "", ""]]
    merges = [{"row": 1, "col": 1, "rowspan": 2, "colspan": 1}, {"row": 1, "col": 2, "rowspan": 1, "colspan": 2},
              {"row": 1, "col": 4, "rowspan": 2, "colspan": 1}, {"row": 1, "col": 5, "rowspan": 2, "colspan": 1},
              {"row": 1, "col": 6, "rowspan": 2, "colspan": 1}]
    rows, refs = [], {}
    st = {"OPEN": "진행", "CLOSED": "완료", "CANCELLED": "취소"}
    for i, o in enumerate(sorted(E["Order"], key=lambda o: o["order_id"])):
        r = 3 + i
        rows.append([o["order_id"], o["product_id"], prod[o["product_id"]]["product_name"], f"{num(o['order_qty'])} {o['unit']}",
                     o["due_date"], st[o["status"]]])
        refs[(r, 1)] = {"field": "order_id", "value": o["order_id"], "ref": ref("Order", o, "order_id")}
        refs[(r, 4)] = {"field": "order_qty", "value": plain(o["order_qty"]), "unit": o["unit"], "ref": ref("Order", o, "order_qty")}
        refs[(r, 5)] = {"field": "due_date", "value": o["due_date"], "ref": ref("Order", o, "due_date")}
    cs2.table("CS2-T1", "표 1. 주문 목록 (Order list)", header, merges, rows, 2, refs,
              continuation={"split_policy": "PDF·PPTX에서 12행(데이터)마다 다음 페이지·슬라이드로 넘기고 헤더 2행을 반복", "repeated_header": True})
    cs2.block("paragraph", "표 2의 재고금액은 보유 수량(기준 단위 환산) × 자재 단가로 계산했다. 제품은 단가가 없어 '-'로 표기한다.")
    header = [["구분 Type", "품목 Item", "", "현재고 On hand", "", "단가(원) Unit cost", "재고금액(원) Value"],
              ["", "코드 Code", "품목명 Name", "수량 Qty", "단위 Unit", "", ""]]
    merges = [{"row": 1, "col": 1, "rowspan": 2, "colspan": 1}, {"row": 1, "col": 2, "rowspan": 1, "colspan": 2},
              {"row": 1, "col": 4, "rowspan": 1, "colspan": 2}, {"row": 1, "col": 6, "rowspan": 2, "colspan": 1},
              {"row": 1, "col": 7, "rowspan": 2, "colspan": 1}]
    rows, refs = [], {}
    for i, inv in enumerate(E["Inventory"]):
        r = 3 + i
        item = inv["item_id"]
        if inv["item_type"] == "MATERIAL":
            m = mat[item]
            base_qty = Decimal(inv["on_hand_qty"]) * Decimal(unit[inv["unit"]]["to_base_factor"]) / Decimal(unit[m["base_unit"]]["to_base_factor"])
            value = base_qty * Decimal(m["unit_cost"])
            cost_s, value_s = num(m["unit_cost"]), num(value)
            refs[(r, 7)] = {"field": "inventory_value_krw", "value": plain(value), "unit": "KRW", "ref": ref("Inventory", inv, "on_hand_qty"),
                            "derived_rule": f"on_hand_qty({inv['unit']}→{m['base_unit']}) × Material.unit_cost — E03 문서용 파생값 (canonical에 없는 값)"}
            refs[(r, 6)] = {"field": "unit_cost", "value": plain(m["unit_cost"]), "unit": f"KRW/{m['base_unit']}", "ref": ref("Material", m, "unit_cost")}
        else:
            cost_s = value_s = "-"
        rows.append(["자재" if inv["item_type"] == "MATERIAL" else "제품", item, name(item), num(inv["on_hand_qty"]), inv["unit"], cost_s, value_s])
        refs[(r, 4)] = {"field": "on_hand_qty", "value": plain(inv["on_hand_qty"]), "unit": inv["unit"], "ref": ref("Inventory", inv, "on_hand_qty")}
    cs2.table("CS2-T2", "표 2. 재고 현황 (Inventory)", header, merges, rows, 2, refs)
    cs2.block("footer", "충파모 과제 7 PoC 합성 데이터 — Synthetic data, not real company records.")

    # ---------------- CS3: 생산계획안 비교 ----------------
    cs3 = Doc("CS3", "생산계획안 비교 (Production Plan Comparison) — " + gt["parameters"]["horizon_start"] + " ~ " + gt["parameters"]["horizon_end"])
    cs3.block("slide_title", cs3.title)
    weeks = sorted({l["period_start"] for l in E["ProductionPlanLine"]})
    header = [["제품 Product", "주차별 계획 수량 Weekly planned qty (EA)", "", "", ""], [""] + weeks]
    merges = [{"row": 1, "col": 1, "rowspan": 2, "colspan": 1}, {"row": 1, "col": 2, "rowspan": 1, "colspan": 4}]
    rows, refs = [], {}
    lines = [l for l in E["ProductionPlanLine"] if l["plan_id"] == "PLAN-REG"]
    for i, p in enumerate(sorted({l["product_id"] for l in lines})):
        r = 3 + i
        row = [p]
        for j, w in enumerate(weeks):
            ln = next((l for l in lines if l["product_id"] == p and l["period_start"] == w), None)
            row.append(num(ln["planned_qty"]) if ln else "0")
            if ln:
                refs[(r, 2 + j)] = {"field": "planned_qty", "value": plain(ln["planned_qty"]), "unit": "EA", "ref": ref("ProductionPlanLine", ln, "planned_qty")}
        rows.append(row)
    cs3.table("CS3-T1", "정규생산안(PLAN-REG) 주차별 계획", header, merges, rows, 2, refs,
              continuation={"split_policy": "PPTX에서 완제품 3행은 슬라이드 2, 반제품 2행은 슬라이드 3 (헤더 반복)", "repeated_header": True})
    pe = X["plan_evaluation"]
    header = [["계획안 Plan", "비용(원) Cost (KRW)", "", "", "", "능력 초과(h)"], ["", "자재비", "정규 생산비", "잔업비", "외주비", ""]]
    merges = [{"row": 1, "col": 1, "rowspan": 2, "colspan": 1}, {"row": 1, "col": 2, "rowspan": 1, "colspan": 4},
              {"row": 1, "col": 6, "rowspan": 2, "colspan": 1}]
    rows, refs = [], {}
    for i, pid in enumerate(sorted(pe)):
        c = pe[pid]["costs_krw"]
        r = 3 + i
        rows.append([pid, num(c["material"]), num(c["regular_production"]), num(c["overtime"]), num(c["outsourcing"]),
                     num(pe[pid]["capacity_excess_total_h"])])
        for j, k in enumerate(("material", "regular_production", "overtime", "outsourcing")):
            refs[(r, 2 + j)] = {"field": f"cost_{k}", "value": plain(c[k]), "unit": "KRW",
                                "ref": {"expected_path": f"expected.plan_evaluation.{pid}.costs_krw.{k}"}}
    cs3.table("CS3-T2", "계획안별 비용·능력 초과 (v2 정답셋 기대값)", header, merges, rows, 2, refs)
    cs3.block("slide_body", "잔업안은 같은 수량을 정규 + 잔업 시간으로 생산한다. 외주안은 FG003 일부를 가상 외주처(합성 가정)에 맡긴다.")
    cs3.block("speaker_notes", "발표자 노트: 정답셋 v2 기준, 재고 유지비·지연 페널티는 미산정. Notes: v2 ground truth.")
    return {"CS1": cs1.to_json(), "CS2": cs2.to_json(), "CS3": cs3.to_json()}


# 형식별 문서 렌더링 계획 (planned_location = 논리 위치. 실제 좌표는 생성 시 기록)
DOCUMENTS = [
    {"doc_id": "D-01", "format": "docx", "content_set": "CS1", "file": "data/documents/D-01_bom_spec.docx",
     "method": "생성 (python-docx)", "layout": {"header": "CS1-b02 (문서번호·개정)", "footer": "페이지 번호", "body_order": ["CS1-b01", "CS1-b03", "CS1-T1", "CS1-T2", "CS1-b04"]},
     "location_scheme": "part(body/header/footer) + body_index + table_index/row/col"},
    {"doc_id": "D-02", "format": "docx", "content_set": "CS2", "file": "data/documents/D-02_order_inventory.docx",
     "method": "생성 (python-docx)", "layout": {"footer": "CS2-b04", "body_order": ["CS2-b01", "CS2-b02", "CS2-T1", "CS2-b03", "CS2-T2"]},
     "location_scheme": "part + body_index + table_index/row/col"},
    {"doc_id": "P-01", "format": "pdf_text", "content_set": "CS1", "file": "data/documents/P-01_bom_spec.pdf",
     "method": "생성 (reportlab)", "layout": {"pages": 1, "header_on_each_page": "CS1-b02"}, "location_scheme": "page + bbox(pt, origin top-left, 생성 시 기록)"},
    {"doc_id": "P-02", "format": "pdf_text", "content_set": "CS2", "file": "data/documents/P-02_order_inventory.pdf",
     "method": "생성 (reportlab)", "layout": {"pages": "3 (CS2-T1이 1→2쪽으로 넘어감, 헤더 반복)"}, "location_scheme": "page + bbox"},
    {"doc_id": "S-01", "format": "pdf_scan", "content_set": "CS1", "file": "data/documents/S-01_bom_spec_scan.pdf",
     "method": "생성 (Pillow로 텍스트·표를 이미지에 그려 PDF로 저장, 텍스트 레이어 없음)", "layout": {"pages": 1, "dpi": "팀 합의 필요 (제안 200)"},
     "location_scheme": "page + bbox(px→pt 환산, 그릴 때 기록)"},
    {"doc_id": "S-02", "format": "pdf_scan", "content_set": "CS2", "file": "data/documents/S-02_order_inventory_scan.pdf",
     "method": "생성 (Pillow)", "layout": {"pages": 3, "noise": "기울기·잡음 없음(1차). 기울기 추가본은 후속"}, "location_scheme": "page + bbox"},
    {"doc_id": "T-01", "format": "pptx", "content_set": "CS3", "file": "data/documents/T-01_plan_comparison.pptx",
     "method": "생성 (python-pptx)", "layout": {"slides": ["1: CS3-b01 제목", "2: CS3-T1 완제품 3행 + 헤더", "3: CS3-T1 반제품 2행 + 헤더 반복",
                                                        "4: CS3-T2 + CS3-b02(텍스트 상자, 그룹 도형 안)", "노트: CS3-b03 (슬라이드 4)"]},
     "location_scheme": "slide_index + shape_name(생성 시 고정 이름) + shape_id(생성 시 기록) + row/col + part(slide/notes)"},
    {"doc_id": "T-02", "format": "pptx", "content_set": "CS1", "file": "data/documents/T-02_bom_spec.pptx",
     "method": "생성 (python-pptx)", "layout": {"slides": ["1: 제목·문서번호", "2: CS1-T1", "3: CS1-T2 + CS1-b03 (텍스트 상자)"]},
     "location_scheme": "slide_index + shape_name + shape_id + row/col"},
    {"doc_id": "H-01", "format": "hwpx", "content_set": "CS1", "file": "data/documents/H-01_bom_spec.hwpx",
     "method": "생성 시도 (python-hwpx 또는 zipfile+XML 직접 작성). **한글 프로그램에서 열리는지 확인 전에는 검증 완료로 처리하지 않음**",
     "layout": {"section": "section0", "body_order": ["CS1-b01", "CS1-b02", "CS1-b03", "CS1-T1", "CS1-T2", "CS1-b04"]},
     "location_scheme": "section_file + paragraph index(생성 시 기록) + table_index/row/col"},
    {"doc_id": "W-01", "format": "hwp", "content_set": "CS1", "file": "data/documents/W-01_bom_spec.hwp",
     "method": "외부 확보 필요 — 한글 프로그램 보유자가 D-01 또는 H-01을 열어 HWP로 저장(변환) 후 독립 검수 (E01 HWP 정답 원천 예외)",
     "layout": {"note": "변환 과정에서 바뀐 부분은 검수 정답 JSON을 기준으로 함"}, "location_scheme": "section + paragraph + control_index + row/col (사용 도구 기준)"},
]
EVAL_ITEMS = {
    "docx": ["텍스트 블록·순서", "머리말·꼬리말·각주", "표 셀·병합(2행 헤더)", "숫자·단위(천 단위 쉼표, g/kg)·날짜", "원본 위치(part·body_index·표 행열)", "본문-표 연결"],
    "pdf_text": ["텍스트 블록·순서", "표 검출 재현율·정밀도", "표 셀·병합", "페이지 넘김 표 연결·반복 헤더", "숫자·단위·날짜", "원본 위치(page·bbox IoU)", "머리말의 문서번호·개정"],
    "pdf_scan": ["스캔 판정(텍스트 레이어 없음)", "직접 추출 시 빈 출력(EXT-EMPTY) 판정", "OCR/API 비교는 E04"],
    "pptx": ["슬라이드·도형 순서", "표 도형 셀·병합", "슬라이드를 넘는 표 연결", "그룹 도형 안 텍스트", "발표자 노트", "원본 위치(slide·shape)"],
    "hwpx": ["열림 여부(한글 프로그램 확인 필요)", "문단 순서", "표 셀·병합", "숫자·단위·날짜", "원본 위치(section·paragraph)"],
    "hwp": ["열림 여부", "문단·표 추출", "병합", "원본 위치 — 외부 확보 후"],
}


def main() -> int:
    raw = GT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != GT_SHA256:
        raise SystemExit("ground_truth_v2.json 해시 불일치 → 중단")
    gt = json.loads(raw.decode("utf-8"))
    sets = build(gt)
    docs = []
    for d in DOCUMENTS:
        docs.append({**d, "status": "NOT_GENERATED", "evaluation_items": EVAL_ITEMS[d["format"]],
                     "verification": "샘플 생성·확보 전 — 모든 지표 미측정"})
    out = {
        "schema": "chungpamo.e03_document_truth", "version": "v1",
        "source": {"file": "data/canonical/ground_truth_v2.json", "sha256": GT_SHA256, "note": "canonical v2를 읽기만 함 (수정 없음)"},
        "generator": "scripts/e03_build_truth.py",
        "representation": "docs/intermediate_representation.md 의 blocks / tables / extracted_values 구조. 위치는 계획(논리) 위치만, 실제 좌표는 생성 시 기록",
        "new_values_rules": [
            "CS2-T2 재고금액 = on_hand_qty(기준 단위 환산) × Material.unit_cost (문서용 파생값, canonical에 없음)",
            "CS1 문서번호 'SPEC-FG001'은 표시용 식별자 (규칙: SPEC-{product_id}), 개정 표기는 BOM 버전(V2)",
            "그 밖의 모든 수치·날짜는 canonical v2 엔터티 또는 expected 값을 그대로 표기",
        ],
        "content_sets": sets,
        "documents": docs,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    n_cells = sum(len(t["cells"]) for s in sets.values() for t in s["tables"])
    n_vals = sum(len(s["extracted_values"]) for s in sets.values())
    print({"documents": len(docs), "content_sets": len(sets), "tables": sum(len(s["tables"]) for s in sets.values()),
           "cells": n_cells, "values_with_canonical_ref": n_vals, "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
