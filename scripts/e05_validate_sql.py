"""E05 SQLite 검증기 (방식 A-2). 규칙 정의: configs/e05_validation_rules.json

모드
- "queries": 제약 없는 적재 테이블에 원본 값을 그대로 넣고, 규칙별 검증 질의(SQL만)로 위반 레코드를 찾는다. 한 번에 모든 위반을 보고.
- "constraints": PK·UNIQUE·FK(PRAGMA foreign_keys=ON 확인)·NOT NULL·CHECK·STRICT 타입을 둔 테이블에 행 단위로 적재하고,
  거부된 행의 오류 메시지를 규칙으로 분류한다. 행마다 첫 위반 1개만 알 수 있고, 여러 레코드에 걸친 규칙(순환·버전 중복 등)은 표현하지 않는다.
SQL로 표현하지 않은 부분: 없음(queries 모드). 값 해석은 SQLite 내장 함수만 사용 (Python 사용자 함수 등록 없음).
평가셋 정답은 읽지 않는다.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from e01_models import MODELS

ROOT = Path(__file__).resolve().parents[1]
RULES = {r["rule_id"]: r for r in json.loads((ROOT / "configs" / "e05_validation_rules.json").read_text(encoding="utf-8"))["rules"]}

# ---------- 공통: 필드 분류 (E01 모델에서 읽음 — 모델과 열 정의를 한 곳에 둔다) ----------

def field_kinds():
    import datetime as dt
    import typing
    from decimal import Decimal
    out = {}
    for ent, m in MODELS.items():
        cols = {}
        for n, f in m.model_fields.items():
            a = f.annotation
            args = typing.get_args(a)
            base = next((x for x in args if x is not type(None)), a) if args and type(None) in args else a
            if typing.get_origin(base) is typing.Literal:
                kind = ("enum", typing.get_args(base))
            elif base is Decimal:
                kind = ("decimal", None)
            elif base is int:
                kind = ("int", None)
            elif base is bool:
                kind = ("bool", None)
            elif base is dt.date:
                kind = ("date", None)
            else:
                kind = ("text", None)
            cons = {}
            for c in f.metadata:
                for k in ("gt", "ge", "lt", "le"):
                    if getattr(c, k, None) is not None:
                        cons[k] = getattr(c, k)
            cols[n] = {"kind": kind[0], "enum": kind[1], "required": f.is_required(), "cons": cons}
        out[ent] = cols
    return out


FK = field_kinds()
NUM_OK = "({c} NOT GLOB '*[^0-9.-]*' AND {c} GLOB '*[0-9]*' AND {c} NOT GLOB '?*-*' AND (length({c}) - length(replace({c}, '.', ''))) <= 1)"
INT_OK = "({c} NOT GLOB '*[^0-9-]*' AND {c} GLOB '*[0-9]*' AND {c} NOT GLOB '?*-*')"
UID_GLOB = "rec_" + "[0-9a-f]" * 16
DATE_OK = "(date({c}) IS NOT NULL AND date({c}) = {c})"   # date('2026-02-30')는 '2026-03-02'를 돌려주므로 왕복 비교


def staging(con, ents):
    for ent, cols in FK.items():
        names = ["record_uid", "origin_class"] + [c for c in cols if c not in ("record_uid", "origin_class")]
        con.execute(f'CREATE TABLE "{ent}" ({", ".join(chr(34) + n + chr(34) for n in names)})')
        rows = []
        for r in ents.get(ent, []):
            rows.append([r.get(n) if not isinstance(r.get(n), bool) else int(r.get(n)) for n in names])
        con.executemany(f'INSERT INTO "{ent}" VALUES ({",".join("?" * len(names))})', rows)


def q(c):
    return f'"{c}"'


def generated_queries():
    """엔터티·필드 정의에서 자동으로 만드는 구조 규칙 질의 (S01~S07)."""
    out = []
    for ent, cols in FK.items():
        for n, d in cols.items():
            c = q(n)
            if d["required"]:
                out.append(("S01", ent, n, f'SELECT record_uid, {c} FROM "{ent}" WHERE {c} IS NULL OR {c} = \'\''))
            else:
                out.append(("S07", ent, n, f'SELECT record_uid, {c} FROM "{ent}" WHERE {c} = \'\''))
            present = f"{c} IS NOT NULL AND {c} <> ''"
            if d["kind"] == "decimal":
                out.append(("S02", ent, n, f'SELECT record_uid, {c} FROM "{ent}" WHERE {present} AND NOT {NUM_OK.format(c=c)}'))
            elif d["kind"] == "int":
                out.append(("S02", ent, n, f'SELECT record_uid, {c} FROM "{ent}" WHERE {present} AND NOT {INT_OK.format(c=c)}'))
            elif d["kind"] == "bool":
                out.append(("S02", ent, n, f'SELECT record_uid, {c} FROM "{ent}" WHERE {c} IS NOT NULL AND {c} NOT IN (0, 1)'))
            elif d["kind"] == "date":
                out.append(("S03", ent, n, f'SELECT record_uid, {c} FROM "{ent}" WHERE {present} AND NOT {DATE_OK.format(c=c)}'))
            elif d["kind"] == "enum":
                vals = ", ".join("'" + v + "'" for v in d["enum"])
                out.append(("S04", ent, n, f'SELECT record_uid, {c} FROM "{ent}" WHERE {present} AND {c} NOT IN ({vals})'))
            if d["cons"] and d["kind"] in ("decimal", "int"):
                ok = (NUM_OK if d["kind"] == "decimal" else INT_OK).format(c=c)
                bad = " OR ".join(f"CAST({c} AS REAL) {'<=' if k == 'gt' else '<' if k == 'ge' else '>=' if k == 'lt' else '>'} {v}" for k, v in d["cons"].items())
                rule = "V01" if (ent, n) == ("Inventory", "on_hand_qty") else "S06"
                out.append((rule, ent, n, f'SELECT record_uid, {c} FROM "{ent}" WHERE {present} AND {ok} AND ({bad})'))
        out.append(("S05", ent, "record_uid", f'SELECT record_uid, record_uid FROM "{ent}" WHERE record_uid IS NOT NULL AND record_uid NOT GLOB \'{UID_GLOB}\''))
    return out


KEYS = {"Unit": [("unit_code",)], "Product": [("product_id",)], "Material": [("material_id",)], "Supplier": [("supplier_id",)],
        "SupplierMaterial": [("supplier_id", "material_id")], "BOM": [("bom_id",)], "BOMLine": [("bom_id", "line_no")], "Order": [("order_id",)],
        "SalesHistory": [("product_id", "period_start", "period_grain")], "Resource": [("resource_id",)],
        "Operation": [("operation_id",), ("product_id", "sequence_no")], "ProductionPlan": [("plan_id",)], "ProductionPlanLine": [("plan_id", "line_no")]}


def dup_query(ent, keys, rule="S08"):
    k = ", ".join(q(x) for x in keys)
    nn = " AND ".join(f"{q(x)} IS NOT NULL AND {q(x)} <> ''" for x in keys)
    concat = " || '|' || ".join("t." + q(x) for x in keys)
    return (rule, ent, "*", f'SELECT t.record_uid, {concat} FROM "{ent}" t JOIN '
                            f'(SELECT {k} FROM "{ent}" WHERE {nn} GROUP BY {k} HAVING COUNT(*) > 1) d USING ({k})')


def ref_query(rule, ent, field, parent, pkey, cond="1=1"):
    return (rule, ent, field, f'SELECT c.record_uid, c.{q(field)} FROM "{ent}" c LEFT JOIN "{parent}" p ON p.{q(pkey)} = c.{q(field)} '
                              f'WHERE c.{q(field)} IS NOT NULL AND c.{q(field)} <> \'\' AND ({cond}) AND p.record_uid IS NULL')


def rule_queries(params):
    ref_date = params["reference_date"]
    site = params.get("site_id")
    Q = generated_queries()
    for ent, keysets in KEYS.items():
        for keys in keysets:
            Q.append(dup_query(ent, keys))
    for ent in ("BOM", "Order", "Operation", "ProductionPlanLine", "SalesHistory"):
        Q.append(ref_query("R01", ent, "product_id", "Product", "product_id"))
    Q += [ref_query("R01", "BOMLine", "component_product_id", "Product", "product_id", "c.component_type = 'PRODUCT'"),
          ref_query("R01", "Inventory", "item_id", "Product", "product_id", "c.item_type = 'PRODUCT'"),
          ref_query("R02", "BOMLine", "component_material_id", "Material", "material_id", "c.component_type = 'MATERIAL'"),
          ref_query("R02", "SupplierMaterial", "material_id", "Material", "material_id"),
          ref_query("R02", "Inventory", "item_id", "Material", "material_id", "c.item_type = 'MATERIAL'"),
          ref_query("R03", "SupplierMaterial", "supplier_id", "Supplier", "supplier_id"),
          ref_query("R04", "BOMLine", "bom_id", "BOM", "bom_id"),
          ref_query("R05", "Operation", "resource_id", "Resource", "resource_id"),
          ref_query("R05", "ProductionPlanLine", "resource_id", "Resource", "resource_id"),
          ref_query("R06", "ProductionPlanLine", "plan_id", "ProductionPlan", "plan_id")]
    for ent, f in (("Unit", "base_unit_code"), ("Product", "base_unit"), ("Material", "base_unit"), ("BOMLine", "unit"), ("Order", "unit"),
                   ("Inventory", "unit"), ("ProductionPlanLine", "unit")):
        Q.append(ref_query("R07", ent, f, "Unit", "unit_code"))
    edges = ("SELECT b.product_id AS u, l.component_product_id AS v, l.record_uid AS uid FROM BOMLine l JOIN BOM b ON b.bom_id = l.bom_id "
             "WHERE l.component_type = 'PRODUCT' AND l.component_product_id IS NOT NULL")
    Q.append(("B01", "BOMLine", "component_product_id",
              f"WITH RECURSIVE e AS ({edges}), reach(src, dst) AS (SELECT DISTINCT u, v FROM e UNION SELECT r.src, e.v FROM reach r JOIN e ON e.u = r.dst) "
              "SELECT DISTINCT e.uid, e.u || '->' || e.v FROM e WHERE e.u = e.v OR EXISTS (SELECT 1 FROM reach r WHERE r.src = e.v AND r.dst = e.u)"))
    active = f"status = 'APPROVED' AND is_active = 1 AND {DATE_OK.format(c='valid_from')} AND {NUM_OK.format(c='min_qty')}"
    Q.append(("B02", "BOM", "*",
              f"WITH a AS (SELECT * FROM BOM WHERE {active} AND (valid_to IS NULL OR {DATE_OK.format(c='valid_to')}) AND (max_qty IS NULL OR {NUM_OK.format(c='max_qty')})) "
              "SELECT x.record_uid, x.bom_id FROM a x JOIN a y ON x.product_id = y.product_id AND x.record_uid <> y.record_uid "
              "WHERE x.valid_from <= COALESCE(y.valid_to, '9999-12-31') AND y.valid_from <= COALESCE(x.valid_to, '9999-12-31') "
              "AND CAST(x.min_qty AS REAL) < COALESCE(CAST(y.max_qty AS REAL), 1e30) AND CAST(y.min_qty AS REAL) < COALESCE(CAST(x.max_qty AS REAL), 1e30) "
              "AND (x.site_id IS NULL OR y.site_id IS NULL OR x.site_id = y.site_id) GROUP BY x.record_uid"))
    Q.append(("B03", "BOM", "status", "SELECT record_uid, status FROM BOM WHERE is_active = 1 AND status IS NOT NULL AND status <> '' AND status <> 'APPROVED'"))
    Q.append(dup_query("BOM", ("product_id", "bom_version"), "B04"))
    Q.append(("B05", "BOM", "valid_to", f"SELECT record_uid, valid_to FROM BOM WHERE {DATE_OK.format(c='valid_from')} AND {DATE_OK.format(c='valid_to')} AND valid_to < valid_from"))
    Q.append(("B05", "BOM", "max_qty", f"SELECT record_uid, max_qty FROM BOM WHERE {NUM_OK.format(c='min_qty')} AND {NUM_OK.format(c='max_qty')} "
                                       "AND CAST(max_qty AS REAL) <= CAST(min_qty AS REAL)"))
    site_cond = "b.site_id IS NULL" if site is None else f"(b.site_id IS NULL OR b.site_id = '{site}')"
    Q.append(("B06", "ProductionPlanLine", "product_id",
              f"SELECT l.record_uid, l.product_id FROM ProductionPlanLine l LEFT JOIN BOM b ON b.product_id = l.product_id AND b.status = 'APPROVED' AND b.is_active = 1 "
              f"AND {DATE_OK.format(c='b.valid_from')} AND (b.valid_to IS NULL OR {DATE_OK.format(c='b.valid_to')}) AND {NUM_OK.format(c='b.min_qty')} "
              f"AND (b.max_qty IS NULL OR {NUM_OK.format(c='b.max_qty')}) AND b.valid_from <= l.period_start AND l.period_start <= COALESCE(b.valid_to, '9999-12-31') "
              f"AND CAST(b.min_qty AS REAL) <= CAST(l.planned_qty AS REAL) AND CAST(l.planned_qty AS REAL) < COALESCE(CAST(b.max_qty AS REAL), 1e30) AND {site_cond} "
              f"WHERE l.production_mode = 'INHOUSE' AND {DATE_OK.format(c='l.period_start')} AND {NUM_OK.format(c='l.planned_qty')} "
              "GROUP BY l.record_uid HAVING COUNT(b.record_uid) <> 1"))
    Q.append(("B07", "BOMLine", "component_type",
              "SELECT record_uid, component_type FROM BOMLine WHERE component_type IN ('MATERIAL', 'PRODUCT') AND "
              "((component_type = 'MATERIAL') <> (component_material_id IS NOT NULL) OR (component_type = 'MATERIAL') = (component_product_id IS NOT NULL))"))
    item_unit = ("CASE WHEN {t}.component_type = 'MATERIAL' THEN (SELECT base_unit FROM Material WHERE material_id = {t}.component_material_id) "
                 "ELSE (SELECT base_unit FROM Product WHERE product_id = {t}.component_product_id) END")
    def dim(ent, base_expr):
        return ("B08", ent, "unit", f'SELECT t.record_uid, t.unit FROM "{ent}" t JOIN Unit u1 ON u1.unit_code = t.unit '
                                    f"JOIN Unit u2 ON u2.unit_code = ({base_expr}) WHERE u1.dimension <> u2.dimension")
    Q += [dim("BOMLine", item_unit.format(t="t")), dim("Order", "SELECT base_unit FROM Product WHERE product_id = t.product_id"),
          dim("Inventory", "CASE WHEN t.item_type = 'MATERIAL' THEN (SELECT base_unit FROM Material WHERE material_id = t.item_id) "
                           "ELSE (SELECT base_unit FROM Product WHERE product_id = t.item_id) END"),
          dim("ProductionPlanLine", "SELECT base_unit FROM Product WHERE product_id = t.product_id")]
    Q.append(("B09", "BOM", "*", "SELECT record_uid, bom_id FROM BOM b WHERE NOT EXISTS (SELECT 1 FROM BOMLine l WHERE l.bom_id = b.bom_id)"))
    Q.append(("B10", "BOMLine", "*", "SELECT l.record_uid, COALESCE(l.component_material_id, l.component_product_id) FROM BOMLine l JOIN "
                                     "(SELECT bom_id, COALESCE(component_material_id, component_product_id) c FROM BOMLine WHERE COALESCE(component_material_id, component_product_id) IS NOT NULL "
                                     "GROUP BY 1, 2 HAVING COUNT(*) > 1) d ON d.bom_id = l.bom_id AND d.c = COALESCE(l.component_material_id, l.component_product_id)"))
    Q.append(("B11", "SupplierMaterial", "is_preferred", "SELECT s.record_uid, s.is_preferred FROM SupplierMaterial s JOIN "
                                                         "(SELECT material_id FROM SupplierMaterial WHERE material_id IS NOT NULL GROUP BY material_id "
                                                         "HAVING SUM(CASE WHEN is_preferred = 1 THEN 1 ELSE 0 END) <> 1) m USING (material_id)"))
    Q.append(("B12", "SalesHistory", "allocation_share",
              f"SELECT s.record_uid, s.allocation_share FROM SalesHistory s JOIN (SELECT derived_from_record_uid g FROM SalesHistory "
              f"WHERE generation_method = 'ALLOCATED' AND derived_from_record_uid IS NOT NULL AND {NUM_OK.format(c='allocation_share')} "
              "GROUP BY derived_from_record_uid HAVING ABS(SUM(CAST(allocation_share AS REAL)) - 1) > 0.0005) d ON d.g = s.derived_from_record_uid "
              f"WHERE s.generation_method = 'ALLOCATED' AND {NUM_OK.format(c='s.allocation_share')}"))
    Q.append(("B13", "SalesHistory", "derived_from_record_uid", "SELECT record_uid, NULL FROM SalesHistory WHERE generation_method = 'ALLOCATED' AND derived_from_record_uid IS NULL"))
    Q.append(("B13", "SalesHistory", "allocation_share", "SELECT record_uid, NULL FROM SalesHistory WHERE generation_method = 'ALLOCATED' AND derived_from_record_uid IS NOT NULL AND allocation_share IS NULL"))
    Q.append(("B14", "Product", "outsourcing_unit_cost", "SELECT record_uid, outsourcing_unit_cost FROM Product WHERE outsourcing_allowed IN (0, 1) AND "
                                                         "(outsourcing_allowed = 1) <> (outsourcing_unit_cost IS NOT NULL)"))
    inv_num = lambda f: NUM_OK.format(c=f)
    Q.append(("V02", "Inventory", "allocated_qty", f"SELECT record_uid, allocated_qty FROM Inventory WHERE {inv_num('on_hand_qty')} AND {inv_num('allocated_qty')} "
                                                   "AND CAST(allocated_qty AS REAL) > CAST(on_hand_qty AS REAL)"))
    for f in ("on_hand_qty", "allocated_qty", "on_order_qty"):
        Q.append(("V03", "Inventory", f, f"SELECT record_uid, {f} FROM Inventory WHERE unit = 'EA' AND {inv_num(f)} AND CAST({f} AS REAL) <> CAST(CAST({f} AS REAL) AS INTEGER)"))
    Q.append(dup_query("Inventory", ("item_type", "item_id", "as_of_date"), "V04"))
    Q.append(("V05", "Inventory", "expected_receipt_date", f"SELECT record_uid, NULL FROM Inventory WHERE {inv_num('on_order_qty')} AND CAST(on_order_qty AS REAL) > 0 "
                                                           "AND expected_receipt_date IS NULL"))
    Q.append(("V06", "Inventory", "as_of_date", f"SELECT record_uid, as_of_date FROM Inventory WHERE {DATE_OK.format(c='as_of_date')} AND as_of_date > '{ref_date}'"))
    Q.append(("V07", "Order", "due_date", f"SELECT record_uid, due_date FROM \"Order\" WHERE {DATE_OK.format(c='order_date')} AND {DATE_OK.format(c='due_date')} AND due_date < order_date"))
    Q.append(("V08", "Order", "product_id", "SELECT record_uid, product_id FROM \"Order\" o WHERE status = 'OPEN' AND product_id IS NOT NULL AND product_id <> '' "
                                            "AND NOT EXISTS (SELECT 1 FROM Operation p WHERE p.product_id = o.product_id)"))
    Q.append(("V08", "ProductionPlanLine", "product_id", "SELECT record_uid, product_id FROM ProductionPlanLine l WHERE production_mode = 'INHOUSE' AND product_id IS NOT NULL "
                                                         "AND product_id <> '' AND NOT EXISTS (SELECT 1 FROM Operation p WHERE p.product_id = l.product_id)"))
    Q.append(("V09", "ProductionPlanLine", "resource_id", "SELECT record_uid, resource_id FROM ProductionPlanLine l WHERE production_mode = 'INHOUSE' AND resource_id IS NOT NULL "
                                                          "AND EXISTS (SELECT 1 FROM Operation p WHERE p.product_id = l.product_id) "
                                                          "AND NOT EXISTS (SELECT 1 FROM Operation p WHERE p.product_id = l.product_id AND p.resource_id = l.resource_id)"))
    Q.append(("V10", "ProductionPlanLine", "resource_id", "SELECT record_uid, resource_id FROM ProductionPlanLine WHERE production_mode IN ('INHOUSE', 'OUTSOURCE') "
                                                          "AND (production_mode = 'OUTSOURCE') <> (resource_id IS NULL)"))
    Q.append(("V11", "ProductionPlanLine", "production_mode", "SELECT l.record_uid, l.production_mode FROM ProductionPlanLine l JOIN Product p ON p.product_id = l.product_id "
                                                              "WHERE l.production_mode = 'OUTSOURCE' AND p.outsourcing_allowed = 0"))
    Q.append(("V12", "ProductionPlanLine", "period_start", f"SELECT l.record_uid, l.period_start FROM ProductionPlanLine l JOIN ProductionPlan p ON p.plan_id = l.plan_id "
                                                           f"WHERE {DATE_OK.format(c='l.period_start')} AND {DATE_OK.format(c='p.horizon_start')} AND {DATE_OK.format(c='p.horizon_end')} "
                                                           "AND (l.period_start < p.horizon_start OR l.period_start > p.horizon_end)"))
    return Q


CAPACITY_SQL = (
    "SELECT l.plan_id, o.resource_id, l.period_start, SUM(CAST(l.planned_qty AS REAL) * CAST(o.run_time_per_unit_h AS REAL) + COALESCE(CAST(o.setup_time_h AS REAL), 0)) req, "
    "CAST(r.regular_hours_per_day AS REAL) * 5 + CASE WHEN p.overtime_allowed = 1 THEN CAST(r.overtime_hours_per_day_max AS REAL) * 5 ELSE 0 END cap "
    "FROM ProductionPlanLine l JOIN ProductionPlan p ON p.plan_id = l.plan_id JOIN Operation o ON o.product_id = l.product_id JOIN Resource r ON r.resource_id = o.resource_id "
    f"WHERE l.production_mode = 'INHOUSE' AND {NUM_OK.format(c='l.planned_qty')} AND {NUM_OK.format(c='o.run_time_per_unit_h')} "
    "GROUP BY l.plan_id, o.resource_id, l.period_start ORDER BY 1, 2, 3")


def report(dataset_id, rule, ent, uid, field, actual, explanation, source):
    r = RULES[rule]
    return {"dataset_id": dataset_id, "rule_id": rule, "layer": r["layer"], "entity": ent, "record_uid": uid, "field_path": f"{ent}.{field}", "field": field,
            "severity": r["severity"], "detected": True, "actual_value": None if actual is None else str(actual), "expected_constraint": r["description"],
            "explanation": explanation, "evidence": {}, "source": source}


def run_queries(ents, params, dataset_id, layers=None):
    con = sqlite3.connect(":memory:")
    staging(con, ents)
    out, seen = [], set()
    for rule, ent, field, sql in rule_queries(params):
        if layers and RULES[rule]["layer"] not in layers:
            continue
        for uid, val in con.execute(sql):
            if (rule, uid, field) in seen:
                continue
            seen.add((rule, uid, field))
            out.append(report(dataset_id, rule, ent, uid, field, val, "SQL 검증 질의", "sql_query"))
    cap = []
    if not layers or "business" in layers:
        for plan, rid, week, req, capa in con.execute(CAPACITY_SQL):
            cap.append({"plan_id": plan, "resource_id": rid, "week_start": week, "required_h": round(req, 6), "available_h": capa, "excess_h": round(max(0.0, req - capa), 6)})
            if req - capa > 1e-9:
                r = report(dataset_id, "V13", "ProductionPlan", None, "excess_h", round(req - capa, 6), f"{plan} {rid} {week} 초과", "sql_query")
                out.append(r)
    con.close()
    return {"reports": out, "capacity": [{k: str(v) for k, v in c.items()} for c in cap]}


# ---------- constraints 모드 ----------

LOAD_ORDER = ["Unit", "Product", "Material", "Supplier", "Resource", "SupplierMaterial", "BOM", "BOMLine", "Order", "SalesHistory", "Inventory",
              "Operation", "ProductionPlan", "ProductionPlanLine"]
PK = {"Unit": "unit_code", "Product": "product_id", "Material": "material_id", "Supplier": "supplier_id", "SupplierMaterial": "supplier_id, material_id",
      "BOM": "bom_id", "BOMLine": "bom_id, line_no", "Order": "order_id", "SalesHistory": "product_id, period_start, period_grain",
      "Inventory": "item_type, item_id, as_of_date", "Resource": "resource_id", "Operation": "operation_id", "ProductionPlan": "plan_id",
      "ProductionPlanLine": "plan_id, line_no"}
FKS = {"Product": [("base_unit", "Unit", "unit_code")], "Material": [("base_unit", "Unit", "unit_code")],
       "SupplierMaterial": [("supplier_id", "Supplier", "supplier_id"), ("material_id", "Material", "material_id")],
       "BOM": [("product_id", "Product", "product_id")],
       "BOMLine": [("bom_id", "BOM", "bom_id"), ("component_material_id", "Material", "material_id"), ("component_product_id", "Product", "product_id"), ("unit", "Unit", "unit_code")],
       "Order": [("product_id", "Product", "product_id"), ("unit", "Unit", "unit_code")], "SalesHistory": [("product_id", "Product", "product_id")],
       "Inventory": [("unit", "Unit", "unit_code")], "Operation": [("product_id", "Product", "product_id"), ("resource_id", "Resource", "resource_id")],
       "ProductionPlanLine": [("plan_id", "ProductionPlan", "plan_id"), ("product_id", "Product", "product_id"), ("resource_id", "Resource", "resource_id"), ("unit", "Unit", "unit_code")]}
# (규칙, 보고 필드, 식) — 보고 필드는 Python 검증기와 같은 기준(위반 시 고쳐야 할 쪽 필드)으로 둔다. 제약 이름은 규칙__필드__번호
CHECKS = {"BOM": [("B03", "status", "NOT (is_active = 1 AND status <> 'APPROVED')"), ("B05", "valid_to", "valid_to IS NULL OR valid_to >= valid_from"),
                  ("B05", "max_qty", "max_qty IS NULL OR max_qty > min_qty")],
          "BOMLine": [("B07", "component_type", "(component_type = 'MATERIAL') = (component_material_id IS NOT NULL) AND (component_type = 'PRODUCT') = (component_product_id IS NOT NULL)")],
          "Order": [("V07", "due_date", "due_date >= order_date")],
          "Inventory": [("V02", "allocated_qty", "allocated_qty IS NULL OR allocated_qty <= on_hand_qty"),
                        ("V05", "expected_receipt_date", "NOT (on_order_qty > 0 AND expected_receipt_date IS NULL)"),
                        ("V06", "as_of_date", "as_of_date <= '{ref}'"), ("V03", "on_hand_qty", "unit <> 'EA' OR (on_hand_qty = CAST(on_hand_qty AS INTEGER))")],
          "Product": [("B14", "outsourcing_unit_cost", "(outsourcing_allowed = 1) = (outsourcing_unit_cost IS NOT NULL)")],
          "ProductionPlanLine": [("V10", "resource_id", "(production_mode = 'OUTSOURCE') = (resource_id IS NULL)")],
          "SalesHistory": [("B13", "derived_from_record_uid", "generation_method <> 'ALLOCATED' OR (derived_from_record_uid IS NOT NULL AND allocation_share IS NOT NULL)")]}


def constraint_ddl(params):
    stmts = []
    for ent in LOAD_ORDER:
        cols, n = FK[ent], 0
        defs = [f'record_uid TEXT NOT NULL CONSTRAINT S05__record_uid__0 CHECK (record_uid GLOB \'{UID_GLOB}\')', "origin_class TEXT NOT NULL"]
        for name, d in cols.items():
            if name in ("record_uid", "origin_class"):
                continue
            typ = {"decimal": "REAL", "int": "INTEGER", "bool": "INTEGER", "date": "TEXT", "enum": "TEXT", "text": "TEXT"}[d["kind"]]
            parts = [q(name), typ]
            if d["required"]:
                parts.append(f"CONSTRAINT S01__{name}__0 NOT NULL")
            if d["kind"] == "date":
                parts.append(f"CONSTRAINT S03__{name}__0 CHECK ({q(name)} IS NULL OR {DATE_OK.format(c=q(name))})")
            if d["kind"] == "enum":
                parts.append(f"CONSTRAINT S04__{name}__0 CHECK ({q(name)} IS NULL OR {q(name)} IN ({', '.join(chr(39) + v + chr(39) for v in d['enum'])}))")
            if d["kind"] == "bool":
                parts.append(f"CONSTRAINT S02__{name}__0 CHECK ({q(name)} IS NULL OR {q(name)} IN (0, 1))")
            for k, v in d["cons"].items():
                op = {"gt": ">", "ge": ">=", "lt": "<", "le": "<="}[k]
                rule = "V01" if (ent, name) == ("Inventory", "on_hand_qty") else "S06"
                parts.append(f"CONSTRAINT {rule}__{name}__{k} CHECK ({q(name)} IS NULL OR {q(name)} {op} {v})")
            defs.append(" ".join(parts))
        defs.append(f"CONSTRAINT PK_{ent} PRIMARY KEY ({PK[ent]})")
        for i, (rule, field, expr) in enumerate(CHECKS.get(ent, [])):
            defs.append(f"CONSTRAINT {rule}__{field}__c{i} CHECK ({expr.format(ref=params['reference_date'])})")
        for f, parent, pk in FKS.get(ent, []):
            defs.append(f"FOREIGN KEY ({q(f)}) REFERENCES {q(parent)}({q(pk)})")
        stmts.append(f'CREATE TABLE "{ent}" ({", ".join(defs)}) STRICT')
    return stmts


def classify(msg: str, ent: str) -> tuple[str | None, str]:
    m = re.search(r"CHECK constraint failed: (\w+)", msg)
    if m:
        rule, field, _ = m.group(1).split("__")
        return rule, field
    m = re.search(r"NOT NULL constraint failed: \w+\.(\w+)", msg)
    if m:
        return "S01", m.group(1)
    if "UNIQUE constraint failed" in msg:
        return ("V04" if ent == "Inventory" else "S08"), "*"
    if "FOREIGN KEY constraint failed" in msg:
        return "FK", "?"     # SQLite는 어느 외래키가 실패했는지 알려주지 않는다
    m = re.search(r"cannot store \w+ value in \w+ column \w+\.(\w+)", msg)
    if m:
        return "S02", m.group(1)    # STRICT 타입 위반
    return None, "?"


FK_RULE = {("Product", "base_unit"): "R07", ("Material", "base_unit"): "R07", ("SupplierMaterial", "supplier_id"): "R03", ("SupplierMaterial", "material_id"): "R02",
           ("BOM", "product_id"): "R01", ("BOMLine", "bom_id"): "R04", ("BOMLine", "component_material_id"): "R02", ("BOMLine", "component_product_id"): "R01",
           ("BOMLine", "unit"): "R07", ("Order", "product_id"): "R01", ("Order", "unit"): "R07", ("SalesHistory", "product_id"): "R01", ("Inventory", "unit"): "R07",
           ("Operation", "product_id"): "R01", ("Operation", "resource_id"): "R05", ("ProductionPlanLine", "plan_id"): "R06",
           ("ProductionPlanLine", "product_id"): "R01", ("ProductionPlanLine", "resource_id"): "R05", ("ProductionPlanLine", "unit"): "R07"}


def run_constraints(ents, params, dataset_id):
    con = sqlite3.connect(":memory:", isolation_level=None)
    con.execute("PRAGMA foreign_keys = ON")
    fk_on = con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    for s in constraint_ddl(params):
        con.execute(s)
    out, rejected, unclassified = [], 0, 0
    for ent in LOAD_ORDER:
        names = ["record_uid", "origin_class"] + [c for c in FK[ent] if c not in ("record_uid", "origin_class")]
        for r in ents.get(ent, []):
            vals = [r.get(n) if not isinstance(r.get(n), bool) else int(r.get(n)) for n in names]
            try:
                con.execute(f'INSERT INTO "{ent}" VALUES ({",".join("?" * len(names))})', vals)
            except sqlite3.DatabaseError as e:
                rejected += 1
                rule, field = classify(str(e), ent)
                if rule == "FK":
                    # 어느 FK인지 메시지에 없으므로 부모 테이블을 직접 조회해 찾는다 (SQL 질의, 적재 실패 원인 추적용)
                    cands = [f for f, parent, pk in FKS.get(ent, []) if r.get(f) is not None and
                             con.execute(f'SELECT 1 FROM "{parent}" WHERE {q(pk)} = ?', (r.get(f),)).fetchone() is None]
                    for f in cands:
                        out.append(report(dataset_id, FK_RULE[(ent, f)], ent, r.get("record_uid"), f, r.get(f), f"적재 거부: {e} (부모 조회로 열 특정)", "sql_constraint"))
                    if not cands:
                        unclassified += 1
                elif rule and rule in RULES:
                    out.append(report(dataset_id, rule, ent, r.get("record_uid"), field, None, f"적재 거부: {e}", "sql_constraint"))
                else:
                    unclassified += 1
                    out.append({"dataset_id": dataset_id, "rule_id": "UNCLASSIFIED", "layer": "schema", "entity": ent, "record_uid": r.get("record_uid"),
                                "field_path": f"{ent}.?", "field": "?", "severity": "ERROR", "detected": True, "actual_value": None, "expected_constraint": None,
                                "explanation": f"적재 거부 (규칙 분류 불가): {e}", "evidence": {}, "source": "sql_constraint"})
    con.close()
    return {"reports": out, "capacity": [], "fk_enabled": fk_on, "rejected_rows": rejected, "unclassified_rejections": unclassified}


def all_sql_text(params) -> str:
    L = ["-- E05 SQLite 검증 질의 (scripts/e05_validate_sql.py가 생성). 규칙 ID는 configs/e05_validation_rules.json", ""]
    for rule, ent, field, sql in rule_queries(params):
        L += [f"-- {rule} {ent}.{field}", sql + ";", ""]
    L += ["-- V13 생산능력 (자원·주별 필요시간)", CAPACITY_SQL + ";", "", "-- constraints 모드 DDL"] + [s + ";" for s in constraint_ddl(params)]
    return "\n".join(L) + "\n"
