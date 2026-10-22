"""E10 평가셋 v1 생성 — 업체 A 형식 입력 행과 독립 정답 (매핑 실행 전에 고정).

    .\\.venv\\Scripts\\python.exe scripts\\e10_build_eval_set.py

- 입력: 업체 A(configs/e02_vendor_mapping.json) 헤더·코드 형식의 합성 행. E01 정답셋 v2와 분리된 별도 파일(data/canonical/e10/).
- 정답: 시나리오 정의(사내 ID·값)와 E01 정답셋에서만 만든다. scripts/e10_mock_erp.py(매핑 코드)를 import하지 않는다.
- 업체 코드는 E02 설정의 코드표를 역으로 써서 만든다 (입력 생성용). 출력: eval_set_v1.json, manifest_v1.json (sha256).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import e05_dataset as D

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "canonical" / "e10"
CREATED = "2026-10-21"
V = json.loads((ROOT / "configs" / "e02_vendor_mapping.json").read_text(encoding="utf-8"))["vendors"]["A"]
REV = {kind: {v: k for k, v in table.items()} for kind, table in V["codes"].items()}
ORDER_H = ["order_no", "product_code", "qty", "uom", "order_date", "due_date", "priority", "status"]
BOM_H = ["bom_code", "product_code", "bom_version", "status", "active", "valid_from", "valid_to", "min_qty", "max_qty", "site", "base_qty",
         "line_no", "component_type", "component_code", "qty_per", "uom", "scrap_rate"]


def sha_rows(file, rows):
    return hashlib.sha256(json.dumps({"file": file, "rows": rows}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def order_row(n, product_code="0001001", qty="50", uom="EA", order_date="2026-11-10", due_date="2026-11-25", priority="NORMAL", status="OPEN", name=None):
    cells = {"order_no": f"SO26{n:04d}", "qty": qty, "uom": uom, "order_date": order_date, "due_date": due_date, "priority": priority, "status": status}
    if name is None:
        cells["product_code"] = product_code
    else:
        cells["product_name"] = name           # 코드 대신 품명 (업체 A 주문 파일에는 원래 없는 헤더)
    return cells


def order_truth(n, product_id, qty="50", unit="EA", order_date="2026-11-10", due_date="2026-11-25", priority="NORMAL", status="OPEN"):
    return {"order_id": f"O{n:03d}", "product_id": product_id, "order_qty": qty, "unit": unit, "order_date": order_date, "due_date": due_date,
            "priority": priority, "status": status}


def bom_rows(gt, bom_id, lines, override=None):
    """GT의 BOM 헤더 값을 업체 A 형식으로 되돌린 행 + 지정 라인."""
    b = next(x for x in gt["entities"]["BOM"] if x["bom_id"] == bom_id) if bom_id else {}
    head = {**{k: b.get(k) for k in ("product_id", "bom_version", "status", "is_active", "valid_from", "valid_to", "min_qty", "max_qty", "site_id", "base_qty")},
            **(override or {})}
    rows = []
    for ln in lines:
        rows.append({"bom_code": f"{head['product_id']}-{head['bom_version']}", "product_code": REV["product"][head["product_id"]], "bom_version": head["bom_version"],
                     "status": head["status"], "active": "Y" if head["is_active"] else "N", "valid_from": head["valid_from"], "valid_to": head["valid_to"] or "",
                     "min_qty": head["min_qty"], "max_qty": head["max_qty"] or "", "site": head["site_id"] or "", "base_qty": head["base_qty"],
                     "line_no": str(ln["line_no"]), "component_type": "MAT" if ln["component_type"] == "MATERIAL" else "PRD",
                     "component_code": ln["code"], "qty_per": ln["qty_per"], "uom": ln["unit"], "scrap_rate": ln.get("scrap_rate") or "0"})
    return rows, head


def gt_line(gt, bom_id, line_no):
    ln = next(x for x in gt["entities"]["BOMLine"] if x["bom_id"] == bom_id and x["line_no"] == line_no)
    mat = ln["component_type"] == "MATERIAL"
    code = REV["material"][ln["component_material_id"]] if mat else REV["product"][ln["component_product_id"]]
    return {"line_no": line_no, "component_type": ln["component_type"], "code": code, "qty_per": ln["qty_per"], "unit": ln["unit"], "scrap_rate": ln["scrap_rate"]}


def batch(bid, file, rows, doc="2026-10-21", mode="STAGE", source_file=None, sha=None):
    rows_n = [{"row": i + 2, "cells": r} for i, r in enumerate(rows)]           # 헤더가 1행, 데이터는 2행부터 (E02 행 번호 규칙)
    src = source_file or f"e10/vendor_a/{bid.lower()}_{file}"
    return {"batch_id": bid, "vendor": "A", "file": file, "source_file": src, "source_sha256": sha or sha_rows(src, rows_n), "document_version": doc,
            "mode": mode, "rows": rows_n}


def build():
    gt = D.load_gt()
    S = []
    # ---- M01 정확한 제품코드
    m01 = batch("B-M01", "orders.csv", [order_row(21)], source_file="e10/vendor_a/orders_2026-10-21.csv")
    S.append({"id": "M01", "title": "정확한 제품코드", "steps": [{"stage": m01}],
              "truth": {"decision": "AUTO_ACCEPT_ELIGIBLE", "field_truth": {"B-M01:2": {"SalesOrder": order_truth(21, "FG001")}}}})
    # ---- M02 유사 제품명 (띄어쓰기 없음)
    S.append({"id": "M02", "title": "유사 제품명", "steps": [{"stage": batch("B-M02", "orders.csv", [order_row(22, name="가정용히터A")])}, {"policy": "B-M02"}],
              "truth": {"decision": "REVIEW_REQUIRED", "field_truth": {"B-M02:2": {"SalesOrder": order_truth(22, "FG001")}},
                        "must_exist": [["SalesOrder", {"order_id": "O022"}, {"product_id": "FG001"}]]}})
    # ---- M03 동일 명칭의 서로 다른 제품 (A/B 구분 없음)
    S.append({"id": "M03", "title": "동일 명칭의 서로 다른 제품", "steps": [{"stage": batch("B-M03", "orders.csv", [order_row(23, name="가정용 히터")])}, {"policy": "B-M03"}],
              "truth": {"decision": "BLOCKED", "field_truth": {"B-M03:2": {"SalesOrder": {**order_truth(23, None)}}},
                        "must_not_exist": [["SalesOrder", {"order_id": "O023"}]], "note": "FG001·FG002 모두 가능 — 정답 제품 없음, 자동 확정 금지"}})
    # ---- M04 잘못된 제품코드
    S.append({"id": "M04", "title": "잘못된 제품코드", "steps": [{"stage": batch("B-M04", "orders.csv", [order_row(24, product_code="0009999")])}, {"policy": "B-M04"}],
              "truth": {"decision": "BLOCKED", "field_truth": {"B-M04:2": {"SalesOrder": order_truth(24, None)}}, "must_not_exist": [["SalesOrder", {"order_id": "O024"}]]}})
    # ---- M05 단위 불일치: BOM-FG002-V1에 kg 자재 M004를 EA로 추가
    rows, _ = bom_rows(gt, "BOM-FG002-V1", [{"line_no": 9, "component_type": "MATERIAL", "code": REV["material"]["M004"], "qty_per": "2", "unit": "EA"}])
    S.append({"id": "M05", "title": "단위 불일치", "steps": [{"stage": batch("B-M05", "bom.csv", rows)}, {"policy": "B-M05"}],
              "truth": {"decision": "BLOCKED", "must_not_exist": [["BOMLine", {"bom_id": "BOM-FG002-V1", "line_no": 9}]],
                        "must_be_unchanged": [["BOMHeader", {"bom_id": "BOM-FG002-V1"}]], "expected_rules": ["B08"]}})
    # ---- M06 수량 오류
    S.append({"id": "M06", "title": "수량 오류", "steps": [{"stage": batch("B-M06", "orders.csv", [order_row(25, qty="-5"), order_row(26, qty="1O50")])}, {"policy": "B-M06"}],
              "truth": {"decision": "BLOCKED", "must_not_exist": [["SalesOrder", {"order_id": "O025"}], ["SalesOrder", {"order_id": "O026"}]], "expected_rules": ["S06", "S02"]}})
    # ---- M07 중복 주문 (같은 행 두 번)
    S.append({"id": "M07", "title": "중복 주문", "steps": [{"stage": batch("B-M07", "orders.csv", [order_row(27, qty="30"), order_row(27, qty="30")])}, {"policy": "B-M07"}],
              "truth": {"decision": "REVIEW_REQUIRED", "duplicates": [{"kind": "IN_BATCH_DUPLICATE", "key": {"order_id": "O027"}}],
                        "must_exist": [["SalesOrder", {"order_id": "O027"}, {"order_qty": "30"}]], "max_count": [["SalesOrder", {"order_id": "O027"}, 1]]}})
    # ---- M08 구버전 BOM: 2026-01-05 문서(종료일 없음)의 BOM-FG001-V1
    rows, _ = bom_rows(gt, "BOM-FG001-V1", [gt_line(gt, "BOM-FG001-V1", 1)], override={"valid_to": None})
    S.append({"id": "M08", "title": "구버전 BOM", "steps": [{"stage": batch("B-M08", "bom.csv", rows, doc="2026-01-05")}, {"policy": "B-M08"}],
              "truth": {"decision": "BLOCKED", "must_be_unchanged": [["BOMHeader", {"bom_id": "BOM-FG001-V1"}]], "expected_rules": ["M-15", "B02"]}})
    # ---- M09 유효기간 충돌: FG002 V2가 V1과 기간·수량 겹침 (E01-ERR-011 유형)
    rows, _ = bom_rows(gt, "BOM-FG002-V1", [{"line_no": 1, "component_type": "MATERIAL", "code": REV["material"]["M001"], "qty_per": "1", "unit": "kg"}],
                       override={"bom_version": "V2"})
    S.append({"id": "M09", "title": "유효기간 충돌", "steps": [{"stage": batch("B-M09", "bom.csv", rows)}, {"policy": "B-M09"}],
              "truth": {"decision": "BLOCKED", "must_not_exist": [["BOMHeader", {"bom_id": "BOM-FG002-V2"}], ["BOMLine", {"bom_id": "BOM-FG002-V2", "line_no": 1}]],
                        "expected_rules": ["B02"]}})
    # ---- M10 참조 대상 누락: 코드표에 없는 자재 000199
    rows, _ = bom_rows(gt, "BOM-FG003-V1", [{"line_no": 9, "component_type": "MATERIAL", "code": "000199", "qty_per": "1", "unit": "kg"}])
    S.append({"id": "M10", "title": "참조 대상 누락", "steps": [{"stage": batch("B-M10", "bom.csv", rows)}, {"policy": "B-M10"}],
              "truth": {"decision": "BLOCKED", "must_not_exist": [["BOMLine", {"bom_id": "BOM-FG003-V1", "line_no": 9}]], "expected_rules": ["R02"]}})
    # ---- M11 재반입 (M01과 같은 원본·같은 sha, 새 batch_id)
    m11 = {**json.loads(json.dumps(m01)), "batch_id": "B-M11"}
    S.append({"id": "M11", "title": "재반입 시 중복", "steps": [{"stage": m11}],
              "truth": {"decision": "NO_NEW_RECORD", "duplicates": [{"kind": "REIMPORT_SAME_SOURCE", "key": {"order_id": "O021"}}], "max_count": [["SalesOrder", {"order_id": "O021"}, 1]]}})
    # ---- M12 승인되지 않은 데이터 반영 시도 + X01 승인 요청 중복
    S.append({"id": "M12", "title": "승인되지 않은 데이터 반영 시도 (+X01 승인 요청 중복)",
              "steps": [{"stage": batch("B-M12", "orders.csv", [order_row(28, name="가정용 히터 B")])}, {"raw_insert_with_pending": "B-M12"},
                        {"approve": "B-M12", "reviewer": "REVIEWER_A"}, {"approve": "B-M12", "reviewer": "REVIEWER_B", "expect": "ALREADY_DECIDED"},
                        {"db_update_decided": "B-M12"}],
              "truth": {"decision": "NO_COMMIT_BEFORE_APPROVAL", "raw_insert_blocked": True, "second_approval_refused": True, "db_update_blocked": True,
                        "field_truth": {"B-M12:2": {"SalesOrder": order_truth(28, "FG002")}},
                        "must_exist": [["SalesOrder", {"order_id": "O028"}, {"product_id": "FG002"}]], "history_count": [["SalesOrder", {"order_id": "O028"}, 1]]}})
    # ---- M13 유효하지만 잘못된 코드 (한 행 안에서 코드와 품명이 충돌) — 1차 기능 확인 실행 뒤 추가한 사례 (매퍼는 바꾸지 않음)
    r13 = order_row(32, product_code=REV["product"]["FG002"])
    r13["product_name"] = "가정용 히터 A"
    S.append({"id": "M13", "title": "유효하지만 잘못된 코드 (코드·품명 충돌)", "added_after_first_run": True,
              "steps": [{"stage": batch("B-M13", "orders.csv", [r13])}, {"policy": "B-M13"}],
              "truth": {"decision": "REVIEW_REQUIRED", "note": "업체 문서의 품명은 FG001, 코드는 FG002 — 어느 쪽이 맞는지 데이터만으로 확정 불가. 자동 확정 금지, 품명 기준 정답 FG001",
                        "field_truth": {"B-M13:2": {"SalesOrder": order_truth(32, "FG001")}},
                        "must_not_have": [["SalesOrder", {"order_id": "O032"}, {"product_id": "FG002"}]]}})
    # ---- X02 승인 후 원본 변경: 같은 파일 다음 판(수량 50 → 60)
    x02 = batch("B-X02", "orders.csv", [order_row(21, qty="60")], source_file="e10/vendor_a/orders_2026-10-21.csv")
    S.append({"id": "X02", "title": "승인 후 원본 변경",
              "steps": [{"stage": x02}, {"approve": "B-X02", "reviewer": "REVIEWER_A", "current_source_sha": "changed-again", "expect": "STALE_SOURCE"},
                        {"approve": "B-X02", "reviewer": "REVIEWER_A", "current_source_sha": x02["source_sha256"]}],
              "truth": {"decision": "REVIEW_REQUIRED", "operation": "UPDATE", "stale_refused": True,
                        "must_exist": [["SalesOrder", {"order_id": "O021"}, {"order_qty": "60"}]], "history_count": [["SalesOrder", {"order_id": "O021"}, 2]]}})
    # ---- X03 잘못된 reviewer, X04 트랜잭션 중간 실패, X05 롤백 후 상태·재승인
    S.append({"id": "X03-X05", "title": "잘못된 reviewer / 트랜잭션 중간 실패 / 롤백 후 상태",
              "steps": [{"stage": batch("B-X03", "orders.csv", [order_row(29, name="산업용 송풍기 C")])},
                        {"approve": "B-X03", "reviewer": "REVIEWER_X", "expect": "BAD_REVIEWER"}, {"approve": "B-X03", "reviewer": "REVIEWER_OLD", "expect": "BAD_REVIEWER"},
                        {"db_set_reviewer": "B-X03", "reviewer": "REVIEWER_X"},
                        {"approve": "B-X03", "reviewer": "REVIEWER_A", "fail_after_write": True, "expect": "ROLLED_BACK"}, {"check_rolled_back": "B-X03", "key": {"order_id": "O029"}},
                        {"approve": "B-X03", "reviewer": "REVIEWER_A"}],
              "truth": {"bad_reviewer_refused": 2, "db_fk_blocked": True, "rollback_clean": True,
                        "field_truth": {"B-X03:2": {"SalesOrder": order_truth(29, "FG003")}},
                        "must_exist": [["SalesOrder", {"order_id": "O029"}, {"product_id": "FG003"}]], "history_count": [["SalesOrder", {"order_id": "O029"}, 1]]}})
    # ---- X06 같은 ImportBatch 재실행
    S.append({"id": "X06", "title": "동일 ImportBatch 재실행", "steps": [{"stage": json.loads(json.dumps(m01))}],
              "truth": {"decision": "NO_NEW_RECORD", "batch_reused": True, "duplicates": [{"kind": "BATCH_RERUN", "key": {"batch_id": "B-M01"}}],
                        "max_count": [["SalesOrder", {"order_id": "O021"}, 1]]}})
    # ---- X07 서로 다른 후보의 같은 ERP 키 충돌
    S.append({"id": "X07", "title": "같은 ERP 키 충돌", "steps": [{"stage": batch("B-X07", "orders.csv", [order_row(30, qty="10"), order_row(30, qty="20")])}, {"policy": "B-X07"}],
              "truth": {"decision": "BLOCKED", "duplicates": [{"kind": "KEY_CONFLICT", "key": {"order_id": "O030"}}], "must_not_exist": [["SalesOrder", {"order_id": "O030"}]],
                        "expected_rules": ["M-20"]}})
    # ---- 드라이런 (반영 없음)
    S.append({"id": "DRY", "title": "Dry-run 변경 전후 비교", "steps": [{"stage": batch("B-DRY", "orders.csv", [order_row(31)], mode="DRY_RUN")}],
              "truth": {"decision": "NO_COMMIT", "dry_run_diff_ops": ["INSERT"], "must_not_exist": [["SalesOrder", {"order_id": "O031"}]]}})
    return {"schema": "chungpamo.e10_eval_set", "version": "v1", "created": CREATED, "base": {"file": "data/canonical/ground_truth_v2.json", "sha256": D.GT_SHA256},
            "vendor": "A", "reviewer_policies": {"ideal": "검토 필요 staging은 정답 값과 같을 때만 승인, 승인 불가(ERROR)는 반려, 모호(M-21)는 보류",
                                                  "rubber_stamp": "승인 가능한(ERROR 0) 검토 필요 staging을 모두 승인 — 확인 없이 승인하는 최악의 경우"},
            "note": "정답은 시나리오 정의와 E01 정답셋에서만 만들었다. 매핑 코드를 실행·참조하지 않았다", "scenarios": S}


def build_conflicts():
    """M13 개선 검증용 독립 충돌 사례 (2026-10-22). eval_set_v1과 별도 파일 — 기존 평가셋은 다시 쓰지 않는다."""
    gt = D.load_gt()
    S = []
    c01 = order_row(40, product_code=REV["product"]["FG003"])
    c01["product_name"] = "가정용 히터 B"
    S.append({"id": "C01", "title": "코드(FG003)·품명(FG002) 충돌", "steps": [{"stage": batch("B-C01", "orders.csv", [c01])}, {"policy": "B-C01"}],
              "truth": {"decision": "CONFLICT", "expected_rules": ["M-24"], "must_not_exist": [["SalesOrder", {"order_id": "O040"}]], "no_auto_approval": "B-C01"}})
    c02 = order_row(41)
    c02["product_name"] = "가정용 히터 A"
    S.append({"id": "C02", "title": "코드·품명 일치 (FG001)", "steps": [{"stage": batch("B-C02", "orders.csv", [c02])}, {"policy": "B-C02"}],
              "truth": {"decision": "REVIEW_REQUIRED", "field_truth": {"B-C02:2": {"SalesOrder": order_truth(41, "FG001")}},
                        "must_exist": [["SalesOrder", {"order_id": "O041"}, {"product_id": "FG001"}]], "forbidden_rules": ["M-24"]}})
    c03 = order_row(42, product_code=REV["product"]["FG002"])
    c03["product_name"] = "  가정용히터 b "
    S.append({"id": "C03", "title": "표기만 다른 품명 + 코드 일치 (FG002)", "steps": [{"stage": batch("B-C03", "orders.csv", [c03])}, {"policy": "B-C03"}],
              "truth": {"decision": "REVIEW_REQUIRED", "field_truth": {"B-C03:2": {"SalesOrder": order_truth(42, "FG002")}},
                        "must_exist": [["SalesOrder", {"order_id": "O042"}, {"product_id": "FG002"}]], "forbidden_rules": ["M-24"]}})
    rows, _ = bom_rows(gt, "BOM-FG001-V2", [{"line_no": 1, "component_type": "MATERIAL", "code": REV["material"]["M001"], "qty_per": "1", "unit": "kg"}],
                       override={"bom_version": "V9", "status": "DRAFT", "is_active": False})
    S.append({"id": "C04", "title": "비활성(DRAFT) BOM에 라인 추가", "steps": [{"stage": batch("B-C04", "bom.csv", rows)}],
              "truth": {"decision": "REVIEW_REQUIRED", "expected_rules": ["M-25"], "no_auto_approval": "B-C04"}})
    S.append({"id": "C05", "title": "코드만 있는 정상 신규 주문 (자동 승인 기본값 확인)", "steps": [{"stage": batch("B-C05", "orders.csv", [order_row(44)])}, {"policy": "B-C05"}],
              "truth": {"decision": "REVIEW_REQUIRED_BY_DEFAULT", "field_truth": {"B-C05:2": {"SalesOrder": order_truth(44, "FG001")}},
                        "must_exist": [["SalesOrder", {"order_id": "O044"}, {"product_id": "FG001"}]], "no_auto_approval_when_policy": "none"}})
    return {"schema": "chungpamo.e10_conflict_set", "version": "v1", "created": "2026-10-22", "base": {"file": "data/canonical/ground_truth_v2.json", "sha256": D.GT_SHA256},
            "vendor": "A", "note": "M13 개선(v2 매퍼) 검증용 독립 사례. 정답은 시나리오 정의와 E01 정답셋에서만 만들었다", "scenarios": S}


def main():
    import sys
    if "--conflict-set" in sys.argv:
        spec = build_conflicts()
        p = OUT / "conflict_set_v1.json"
        p.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        (OUT / "conflict_manifest_v1.json").write_text(json.dumps({"eval_set_sha256": sha, "scenarios": [s["id"] for s in spec["scenarios"]],
                                                                   "input_rows": sum(len(st["stage"]["rows"]) for s in spec["scenarios"] for st in s["steps"] if "stage" in st)},
                                                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print({"conflict_set_sha256": sha, "scenarios": len(spec["scenarios"])})
        return
    spec = build()
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "eval_set_v1.json"
    p.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    (OUT / "manifest_v1.json").write_text(json.dumps({"eval_set_sha256": sha, "scenarios": [s["id"] for s in spec["scenarios"]],
                                                      "input_rows": sum(len(st["stage"]["rows"]) for s in spec["scenarios"] for st in s["steps"] if "stage" in st)},
                                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print({"eval_set_sha256": sha, "scenarios": len(spec["scenarios"])})


if __name__ == "__main__":
    main()
