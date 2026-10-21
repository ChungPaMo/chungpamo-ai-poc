"""E05 Python/Pydantic 검증기 (방식 A-1). 규칙 정의: configs/e05_validation_rules.json

- schema: E01 pydantic 모델(scripts/e01_models.py, 수정 없이 재사용)의 필드 오류 + 빈 문자열 사전 검사
- referential·relational·business: 원본 레코드(dict)를 관대하게 해석하는 독립 함수 (모델 검증에 실패한 레코드도 검사)
- 모드: "full"(위 전부) / "pydantic_only"(pydantic 필드 오류 + model_validator 오류만 — 내부 비교용)
보고 형식: dataset_id, rule_id, layer, entity, record_uid, field_path, severity, detected, actual_value, expected_constraint, explanation, evidence
평가셋 정답(eval_set의 truth)은 읽지 않는다.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError

from e01_models import MODELS

ROOT = Path(__file__).resolve().parents[1]
RULES = {r["rule_id"]: r for r in json.loads((ROOT / "configs" / "e05_validation_rules.json").read_text(encoding="utf-8"))["rules"]}
KEYS = {"Unit": [("unit_code",)], "Product": [("product_id",)], "Material": [("material_id",)], "Supplier": [("supplier_id",)],
        "SupplierMaterial": [("supplier_id", "material_id")], "BOM": [("bom_id",)], "BOMLine": [("bom_id", "line_no")], "Order": [("order_id",)],
        "SalesHistory": [("product_id", "period_start", "period_grain")], "Resource": [("resource_id",)],
        "Operation": [("operation_id",), ("product_id", "sequence_no")], "ProductionPlan": [("plan_id",)], "ProductionPlanLine": [("plan_id", "line_no")]}
UNIT_FIELDS = {"Unit": ["base_unit_code"], "Product": ["base_unit"], "Material": ["base_unit"], "BOMLine": ["unit"], "Order": ["unit"],
               "Inventory": ["unit"], "ProductionPlanLine": ["unit"]}
TYPE_MAP = {"decimal_parsing": "S02", "decimal_type": "S02", "int_parsing": "S02", "int_type": "S02", "int_from_float": "S02", "float_parsing": "S02",
            "bool_parsing": "S02", "bool_type": "S02", "date_parsing": "S03", "date_from_datetime_parsing": "S03", "date_from_datetime_inexact": "S03",
            "date_type": "S03", "literal_error": "S04", "string_pattern_mismatch": "S05", "greater_than": "S06", "greater_than_equal": "S06",
            "less_than": "S06", "less_than_equal": "S06", "missing": "S01", "string_type": "S01"}
MODEL_VALIDATOR_MAP = [("outsourcing_unit_cost", "B14", "outsourcing_unit_cost"), ("valid_to < valid_from", "B05", "valid_to"),
                       ("max_qty <= min_qty", "B05", "max_qty"), ("APPROVED", "B03", "status"), ("component_type", "B07", "component_type"),
                       ("due_date < order_date", "V07", "due_date"), ("ALLOCATED", "B13", None), ("allocated_qty > on_hand_qty", "V02", "allocated_qty"),
                       ("입고 예정", "V05", "expected_receipt_date"), ("외주 라인", "V10", "resource_id")]
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def dec(v):
    if v is None or isinstance(v, bool) or v == "":
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def date(v):
    if not isinstance(v, str) or not ISO.match(v):
        return None
    try:
        return dt.date.fromisoformat(v)
    except ValueError:
        return None


class Reporter:
    def __init__(self, dataset_id):
        self.dataset_id, self.items, self.seen = dataset_id, [], set()

    def add(self, rule, entity, rec, field, actual, explanation, evidence=None, source="function"):
        key = (rule, rec.get("record_uid"), field)
        if key in self.seen:
            return
        self.seen.add(key)
        r = RULES[rule]
        self.items.append({"dataset_id": self.dataset_id, "rule_id": rule, "layer": r["layer"], "entity": entity, "record_uid": rec.get("record_uid"),
                           "field_path": f"{entity}.{field}", "field": field, "severity": r["severity"], "detected": True,
                           "actual_value": None if actual is None else str(actual), "expected_constraint": r["description"],
                           "explanation": explanation, "evidence": evidence or {}, "source": source})


# ---------------- schema ----------------

def schema_layer(ents, rep: Reporter, include_model_validators: bool):
    for ent, rows in ents.items():
        model = MODELS[ent]
        required = {n for n, f in model.model_fields.items() if f.is_required()}
        for rec in rows:
            blanks = set()
            for k, v in rec.items():
                if v == "":
                    blanks.add(k)
                    if k in required:
                        rep.add("S01", ent, rec, k, v, "필수 필드가 빈 문자열", source="precheck")
                    else:
                        rep.add("S07", ent, rec, k, v, "선택 필드에 빈 문자열 (null이어야 함)", source="precheck")
            clean = {k: (None if (v == "" and k not in required) else v) for k, v in rec.items()}
            try:
                model.model_validate(clean)
            except ValidationError as e:
                for err in e.errors():
                    loc = err["loc"][0] if err["loc"] else None
                    if loc in blanks:
                        continue
                    if err["type"] == "value_error":
                        if not include_model_validators:
                            continue
                        msg = err["msg"]
                        for needle, rule, field in MODEL_VALIDATOR_MAP:
                            if needle in msg:
                                f = field or ("derived_from_record_uid" if rec.get("derived_from_record_uid") is None else "allocation_share")
                                rep.add(rule, ent, rec, f, rec.get(f), f"pydantic model_validator: {msg}", source="pydantic_model_validator")
                                break
                        continue
                    rule = TYPE_MAP.get(err["type"])
                    if rule is None:
                        continue
                    if err["type"] == "string_type" and err.get("input") is not None:
                        rule = "S02"
                    if err.get("input") is None and loc in required:
                        rule = "S01"
                    if rule == "S06" and ent == "Inventory" and loc == "on_hand_qty":
                        rule = "V01"
                    rep.add(rule, ent, rec, loc, err.get("input"), f"pydantic {err['type']}: {err['msg']}", source="pydantic")


def dup_keys(ents, rep: Reporter):
    for ent, keysets in KEYS.items():
        for keys in keysets:
            groups = defaultdict(list)
            for rec in ents[ent]:
                k = tuple(rec.get(x) for x in keys)
                if all(v not in (None, "") for v in k):
                    groups[k].append(rec)
            for k, recs in groups.items():
                if len(recs) > 1:
                    for rec in recs:
                        rep.add("S08", ent, rec, "*", "|".join(map(str, k)), f"키 {keys} 중복 {len(recs)}건", {"same_key": [r["record_uid"] for r in recs]})


# ---------------- referential ----------------

def referential(ents, rep: Reporter):
    ids = lambda ent, f: {r.get(f) for r in ents[ent]}
    prod, mat, sup, bom, res, plan = (ids("Product", "product_id"), ids("Material", "material_id"), ids("Supplier", "supplier_id"),
                                      ids("BOM", "bom_id"), ids("Resource", "resource_id"), ids("ProductionPlan", "plan_id"))
    units = ids("Unit", "unit_code")

    def chk(rule, ent, field, pool, where=lambda r: True):
        for rec in ents[ent]:
            v = rec.get(field)
            if v not in (None, "") and where(rec) and v not in pool:
                rep.add(rule, ent, rec, field, v, f"{field} 값이 참조 대상에 없음")
    for ent in ("BOM", "Order", "Operation", "ProductionPlanLine", "SalesHistory"):
        chk("R01", ent, "product_id", prod)
    chk("R01", "BOMLine", "component_product_id", prod, lambda r: r.get("component_type") == "PRODUCT")
    chk("R01", "Inventory", "item_id", prod, lambda r: r.get("item_type") == "PRODUCT")
    chk("R02", "BOMLine", "component_material_id", mat, lambda r: r.get("component_type") == "MATERIAL")
    chk("R02", "SupplierMaterial", "material_id", mat)
    chk("R02", "Inventory", "item_id", mat, lambda r: r.get("item_type") == "MATERIAL")
    chk("R03", "SupplierMaterial", "supplier_id", sup)
    chk("R04", "BOMLine", "bom_id", bom)
    chk("R05", "Operation", "resource_id", res)
    chk("R05", "ProductionPlanLine", "resource_id", res)
    chk("R06", "ProductionPlanLine", "plan_id", plan)
    for ent, fields in UNIT_FIELDS.items():
        for f in fields:
            chk("R07", ent, f, units)


# ---------------- relational ----------------

def relational(ents, rep: Reporter, params):
    bom_prod = {b.get("bom_id"): b.get("product_id") for b in ents["BOM"]}
    # B01 순환: 간선 u→v가 순환 위에 있으려면 v에서 u로 갈 수 있어야 함
    edges = defaultdict(set)
    for l in ents["BOMLine"]:
        if l.get("component_type") == "PRODUCT" and l.get("component_product_id") and l.get("bom_id") in bom_prod:
            edges[bom_prod[l["bom_id"]]].add(l["component_product_id"])

    def reach(src):
        seen, stack = set(), [src]
        while stack:
            n = stack.pop()
            for c in edges.get(n, ()):
                if c not in seen:
                    seen.add(c)
                    stack.append(c)
        return seen
    closure = {p: reach(p) for p in list(edges)}
    for l in ents["BOMLine"]:
        if l.get("component_type") == "PRODUCT" and l.get("bom_id") in bom_prod:
            u, v = bom_prod[l["bom_id"]], l.get("component_product_id")
            if v and (u == v or u in closure.get(v, set())):
                rep.add("B01", "BOMLine", l, "component_product_id", f"{u}->{v}", "구성품에서 다시 상위 제품으로 돌아오는 순환")
    # B02 활성 버전 유효 조건 중복 (schema §5 판정식)
    INF_D, INF_Q = dt.date.max, Decimal("1e30")
    act = [b for b in ents["BOM"] if b.get("status") == "APPROVED" and b.get("is_active") is True and date(b.get("valid_from"))
           and dec(b.get("min_qty")) is not None]
    for i, x in enumerate(act):
        for y in act[i + 1:]:
            if x.get("product_id") != y.get("product_id"):
                continue
            xt, yt = date(x.get("valid_to")) or INF_D, date(y.get("valid_to")) or INF_D
            xm, ym = dec(x.get("max_qty")) if x.get("max_qty") is not None else INF_Q, dec(y.get("max_qty")) if y.get("max_qty") is not None else INF_Q
            if xm is None or ym is None:
                continue
            period = date(x["valid_from"]) <= yt and date(y["valid_from"]) <= xt
            qty = dec(x["min_qty"]) < ym and dec(y["min_qty"]) < xm
            site = x.get("site_id") is None or y.get("site_id") is None or x.get("site_id") == y.get("site_id")
            if period and qty and site:
                for a, b in ((x, y), (y, x)):
                    rep.add("B02", "BOM", a, "*", a.get("bom_id"), f"활성 버전 {b.get('bom_id')}와 기간·수량·사이트 조건이 동시에 겹침", {"other": b.get("record_uid")})
    for b in ents["BOM"]:
        if b.get("is_active") is True and b.get("status") not in (None, "") and b.get("status") != "APPROVED":
            rep.add("B03", "BOM", b, "status", b.get("status"), "활성 버전인데 APPROVED가 아님")
        vf, vt = date(b.get("valid_from")), date(b.get("valid_to"))
        if vf and vt and vt < vf:
            rep.add("B05", "BOM", b, "valid_to", b.get("valid_to"), "valid_to < valid_from")
        mn, mx = dec(b.get("min_qty")), dec(b.get("max_qty"))
        if mn is not None and mx is not None and mx <= mn:
            rep.add("B05", "BOM", b, "max_qty", b.get("max_qty"), "max_qty <= min_qty")
    groups = defaultdict(list)
    for b in ents["BOM"]:
        if b.get("product_id") and b.get("bom_version"):
            groups[(b["product_id"], b["bom_version"])].append(b)
    for recs in groups.values():
        if len(recs) > 1:
            for b in recs:
                rep.add("B04", "BOM", b, "*", b.get("bom_version"), "같은 제품·버전 표기 중복", {"same": [r["record_uid"] for r in recs]})
    # B06 계획 라인 BOM 선택 (제품, period_start, planned_qty, 사이트)
    site = params.get("site_id")
    for l in ents["ProductionPlanLine"]:
        if l.get("production_mode") != "INHOUSE":
            continue
        d, q = date(l.get("period_start")), dec(l.get("planned_qty"))
        if d is None or q is None:
            continue
        cands = []
        for b in ents["BOM"]:
            if b.get("product_id") != l.get("product_id") or b.get("status") != "APPROVED" or b.get("is_active") is not True:
                continue
            vf, vt = date(b.get("valid_from")), date(b.get("valid_to"))
            mn = dec(b.get("min_qty"))
            mx = dec(b.get("max_qty")) if b.get("max_qty") is not None else Decimal("1e30")
            if vf is None or mn is None or mx is None or (b.get("valid_to") is not None and vt is None):
                continue
            if vf <= d <= (vt or dt.date.max) and mn <= q < mx and (b.get("site_id") is None or b.get("site_id") == site):
                cands.append(b.get("bom_id"))
        if len(cands) != 1:
            rep.add("B06", "ProductionPlanLine", l, "product_id", l.get("product_id"),
                    "적용 가능한 활성 BOM 없음 (선택 불가)" if not cands else f"적용 BOM 모호: {cands}", {"candidates": cands})
    # B07 구성품 열 일치
    for l in ents["BOMLine"]:
        t = l.get("component_type")
        if t in ("MATERIAL", "PRODUCT"):
            is_mat = t == "MATERIAL"
            if is_mat != (l.get("component_material_id") is not None) or is_mat == (l.get("component_product_id") is not None):
                rep.add("B07", "BOMLine", l, "component_type", t, "component_type과 구성품 ID 열이 맞지 않음")
    # B08 단위 차원
    unit_dim = {u.get("unit_code"): u.get("dimension") for u in ents["Unit"]}
    base = {**{p.get("product_id"): p.get("base_unit") for p in ents["Product"]}, **{("M", m.get("material_id")): m.get("base_unit") for m in ents["Material"]}}

    def dim_check(ent, rec, item_unit):
        u = rec.get("unit")
        if u in unit_dim and item_unit in unit_dim and unit_dim[u] != unit_dim[item_unit]:
            rep.add("B08", ent, rec, "unit", u, f"수량 단위 차원({unit_dim[u]})이 품목 기준 단위 {item_unit}({unit_dim[item_unit]})와 다름")
    for l in ents["BOMLine"]:
        item = base.get(("M", l.get("component_material_id"))) if l.get("component_type") == "MATERIAL" else base.get(l.get("component_product_id"))
        dim_check("BOMLine", l, item)
    for o in ents["Order"]:
        dim_check("Order", o, base.get(o.get("product_id")))
    for i in ents["Inventory"]:
        dim_check("Inventory", i, base.get(("M", i.get("item_id"))) if i.get("item_type") == "MATERIAL" else base.get(i.get("item_id")))
    for l in ents["ProductionPlanLine"]:
        dim_check("ProductionPlanLine", l, base.get(l.get("product_id")))
    # B09 라인 없는 BOM, B10 같은 구성품 중복
    has_line = {l.get("bom_id") for l in ents["BOMLine"]}
    for b in ents["BOM"]:
        if b.get("bom_id") not in has_line:
            rep.add("B09", "BOM", b, "*", b.get("bom_id"), "BOM 라인이 없음")
    comp = defaultdict(list)
    for l in ents["BOMLine"]:
        c = l.get("component_material_id") or l.get("component_product_id")
        if c:
            comp[(l.get("bom_id"), c)].append(l)
    for recs in comp.values():
        if len(recs) > 1:
            for l in recs:
                rep.add("B10", "BOMLine", l, "*", l.get("component_material_id") or l.get("component_product_id"), "같은 BOM에 같은 구성품 중복")
    # B11 우선 공급사 수
    by_mat = defaultdict(list)
    for s in ents["SupplierMaterial"]:
        if s.get("material_id"):
            by_mat[s["material_id"]].append(s)
    for m, recs in by_mat.items():
        n = sum(1 for s in recs if s.get("is_preferred") is True)
        if n != 1:
            for s in recs:
                rep.add("B11", "SupplierMaterial", s, "is_preferred", s.get("is_preferred"), f"자재 {m}의 우선 공급사 {n}개 (1개여야 함)")
    # B12·B13 배분
    sums = defaultdict(lambda: [Decimal(0), []])
    for s in ents["SalesHistory"]:
        if s.get("generation_method") == "ALLOCATED":
            if s.get("derived_from_record_uid") is None or s.get("allocation_share") is None:
                rep.add("B13", "SalesHistory", s, "derived_from_record_uid" if s.get("derived_from_record_uid") is None else "allocation_share", None,
                        "ALLOCATED 행에 원본 레코드 또는 배분 비율 없음")
            sh = dec(s.get("allocation_share"))
            if s.get("derived_from_record_uid") and sh is not None:
                g = sums[s["derived_from_record_uid"]]
                g[0] += sh
                g[1].append(s)
    for src, (tot, recs) in sums.items():
        if abs(tot - 1) > Decimal("0.0005"):
            for s in recs:
                rep.add("B12", "SalesHistory", s, "allocation_share", s.get("allocation_share"), f"원본 {src}의 배분 비율 합 {tot} ≠ 1")
    for p in ents["Product"]:
        if isinstance(p.get("outsourcing_allowed"), bool) and p["outsourcing_allowed"] != (p.get("outsourcing_unit_cost") is not None):
            rep.add("B14", "Product", p, "outsourcing_unit_cost", p.get("outsourcing_unit_cost"), "외주 단가는 외주 허용 제품에만")


# ---------------- business ----------------

def business(ents, rep: Reporter, params):
    ref = date(params["reference_date"])
    for i in ents["Inventory"]:
        oh, al, oo = dec(i.get("on_hand_qty")), dec(i.get("allocated_qty")), dec(i.get("on_order_qty"))
        if oh is not None and oh < 0:
            rep.add("V01", "Inventory", i, "on_hand_qty", i.get("on_hand_qty"), "보유 재고 음수")
        if oh is not None and al is not None and al > oh:
            rep.add("V02", "Inventory", i, "allocated_qty", i.get("allocated_qty"), f"할당 {al} > 보유 {oh}")
        if i.get("unit") == "EA":
            for f, v in (("on_hand_qty", oh), ("allocated_qty", al), ("on_order_qty", oo)):
                if v is not None and v != v.to_integral_value():
                    rep.add("V03", "Inventory", i, f, i.get(f), "EA 단위 소수 수량")
        if oo is not None and oo > 0 and i.get("expected_receipt_date") is None:
            rep.add("V05", "Inventory", i, "expected_receipt_date", None, "입고 예정 수량이 있는데 예정일 없음")
        a = date(i.get("as_of_date"))
        if a and ref and a > ref:
            rep.add("V06", "Inventory", i, "as_of_date", i.get("as_of_date"), f"재고 기준일 > 기준일 {params['reference_date']}")
    groups = defaultdict(list)
    for i in ents["Inventory"]:
        k = (i.get("item_type"), i.get("item_id"), i.get("as_of_date"))
        if all(k):
            groups[k].append(i)
    for recs in groups.values():
        if len(recs) > 1:
            for i in recs:
                rep.add("V04", "Inventory", i, "*", "|".join(map(str, (i.get("item_type"), i.get("item_id"), i.get("as_of_date")))), "같은 품목·기준일 재고 중복")
    for o in ents["Order"]:
        od, du = date(o.get("order_date")), date(o.get("due_date"))
        if od and du and du < od:
            rep.add("V07", "Order", o, "due_date", o.get("due_date"), f"납기 {du} < 주문일 {od}")
    ops_by_prod = defaultdict(set)
    for op in ents["Operation"]:
        ops_by_prod[op.get("product_id")].add(op.get("resource_id"))
    for o in ents["Order"]:
        if o.get("status") == "OPEN" and o.get("product_id") and o["product_id"] not in ops_by_prod:
            rep.add("V08", "Order", o, "product_id", o["product_id"], "주문 제품에 공정 없음")
    plans = {p.get("plan_id"): p for p in ents["ProductionPlan"]}
    prods = {p.get("product_id"): p for p in ents["Product"]}
    for l in ents["ProductionPlanLine"]:
        mode, rid, pid = l.get("production_mode"), l.get("resource_id"), l.get("product_id")
        if mode == "INHOUSE":
            if pid and pid not in ops_by_prod:
                rep.add("V08", "ProductionPlanLine", l, "product_id", pid, "계획 제품에 공정 없음")
            elif rid and pid in ops_by_prod and rid not in ops_by_prod[pid]:
                rep.add("V09", "ProductionPlanLine", l, "resource_id", rid, f"제품 {pid} 공정의 자원 {sorted(ops_by_prod[pid])}에 없음")
        if mode in ("INHOUSE", "OUTSOURCE") and (mode == "OUTSOURCE") != (rid is None):
            rep.add("V10", "ProductionPlanLine", l, "resource_id", rid, "외주 라인만 자원이 비어 있어야 함")
        if mode == "OUTSOURCE" and pid in prods and prods[pid].get("outsourcing_allowed") is False:
            rep.add("V11", "ProductionPlanLine", l, "production_mode", mode, f"외주 불가 제품 {pid}의 외주 라인")
        p, d = plans.get(l.get("plan_id")), date(l.get("period_start"))
        if p and d and date(p.get("horizon_start")) and date(p.get("horizon_end")) and not (date(p["horizon_start"]) <= d <= date(p["horizon_end"])):
            rep.add("V12", "ProductionPlanLine", l, "period_start", l.get("period_start"), "계획 기간 밖")


def capacity(ents) -> list[dict]:
    """V13: 계획·자원·주별 필요시간과 초과시간 (decision_logic §6.1 5절 ②③). 데이터 오류 아님(INFO)."""
    ops = defaultdict(list)
    for op in ents["Operation"]:
        ops[op.get("product_id")].append(op)
    res = {r.get("resource_id"): r for r in ents["Resource"]}
    plans = {p.get("plan_id"): p for p in ents["ProductionPlan"]}
    req = defaultdict(Decimal)
    for l in ents["ProductionPlanLine"]:
        q = dec(l.get("planned_qty"))
        if l.get("production_mode") != "INHOUSE" or q is None or l.get("plan_id") not in plans:
            continue
        for op in ops.get(l.get("product_id"), []):
            rt, st = dec(op.get("run_time_per_unit_h")), dec(op.get("setup_time_h")) or Decimal(0)
            if rt is None or op.get("resource_id") not in res:
                continue
            req[(l["plan_id"], op["resource_id"], l.get("period_start"))] += q * rt + st
    out = []
    for (plan, rid, week), h in sorted(req.items()):
        r = res[rid]
        cap = dec(r.get("regular_hours_per_day")) * 5 + (dec(r.get("overtime_hours_per_day_max")) * 5 if plans[plan].get("overtime_allowed") else 0)
        out.append({"plan_id": plan, "resource_id": rid, "week_start": week, "required_h": h, "available_h": cap, "excess_h": max(Decimal(0), h - cap)})
    return out


LAYERS = {"referential": referential, "relational": relational, "business": business}


def validate(ents: dict, params: dict, dataset_id: str, mode: str = "full", rules: set | None = None) -> dict:
    rep = Reporter(dataset_id)
    schema_layer(ents, rep, include_model_validators=(mode == "pydantic_only"))
    if mode == "full":
        dup_keys(ents, rep)
        referential(ents, rep)
        relational(ents, rep, params)
        business(ents, rep, params)
    cap = capacity(ents) if mode == "full" else []
    for c in cap:
        if c["excess_h"] > 0:
            rep.items.append({"dataset_id": dataset_id, "rule_id": "V13", "layer": "business", "entity": "ProductionPlan", "record_uid": None,
                              "field_path": "capacity", "field": "excess_h", "severity": "INFO", "detected": True, "actual_value": str(c["excess_h"]),
                              "expected_constraint": RULES["V13"]["description"], "explanation": f"{c['plan_id']} {c['resource_id']} {c['week_start']} 초과",
                              "evidence": {k: str(v) for k, v in c.items()}, "source": "function"})
    items = rep.items if rules is None else [r for r in rep.items if r["rule_id"] in rules]
    return {"reports": items, "capacity": [{k: str(v) for k, v in c.items()} for c in cap]}
