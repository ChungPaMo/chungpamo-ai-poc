"""E01 정답(기대값) 계산 — 구현 A.

    .\\.venv\\Scripts\\python.exe scripts\\e01_expected.py [--out-root DIR]

ground_truth_v1.json의 entities·parameters를 읽어 decision_logic.md의 계산(§1~§5, §2.1 다단계 전개,
"E01 구현 규칙")과 CQ 기대 결과를 계산하고 같은 파일의 `expected`에 기록한다.
검증은 e01_verify.py가 별도 구현(B)으로 다시 계산해 대조한다. 이 모듈의 함수를 검증에서 import하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import sys
from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from e01_common import D, Paths, fmt, read_json, write_json

ZERO = Decimal(0)


class Model:
    """canonical 엔터티 색인."""

    def __init__(self, gt: dict) -> None:
        self.p = gt["parameters"]
        E = gt["entities"]
        self.E = E
        self.units = {u["unit_code"]: u for u in E["Unit"]}
        self.products = {x["product_id"]: x for x in E["Product"]}
        self.materials = {x["material_id"]: x for x in E["Material"]}
        self.boms = {x["bom_id"]: x for x in E["BOM"]}
        self.lines = defaultdict(list)
        for ln in sorted(E["BOMLine"], key=lambda l: (l["bom_id"], l["line_no"])):
            self.lines[ln["bom_id"]].append(ln)
        self.inv = {(i["item_type"], i["item_id"]): i for i in E["Inventory"]}
        self.resources = {r["resource_id"]: r for r in E["Resource"]}
        self.ops = defaultdict(list)
        for op in sorted(E["Operation"], key=lambda o: (o["product_id"], o["sequence_no"])):
            self.ops[op["product_id"]].append(op)
        self.sm = E["SupplierMaterial"]
        self.ref = dt.date.fromisoformat(self.p["reference_date"])
        self.h_start = dt.date.fromisoformat(self.p["horizon_start"])
        self.h_end = dt.date.fromisoformat(self.p["horizon_end"])

    # ---- 단위 ----
    def base_unit(self, item_type: str, item_id: str) -> str:
        return (self.materials[item_id] if item_type == "MATERIAL" else self.products[item_id])["base_unit"]

    def to_base(self, qty: Decimal, unit: str, item_type: str, item_id: str) -> Decimal:
        u, b = self.units[unit], self.units[self.base_unit(item_type, item_id)]
        if u["dimension"] != b["dimension"]:
            raise ValueError(f"ERR-UNIT: {item_id} {unit} vs {b['unit_code']}")
        return qty * D(u["to_base_factor"]) / D(b["to_base_factor"])

    # ---- 재고 ----
    def available(self, item_type: str, item_id: str, within_horizon: bool = True) -> Decimal:
        rec = self.inv.get((item_type, item_id))
        if rec is None:
            return ZERO
        oh = self.to_base(D(rec["on_hand_qty"]), rec["unit"], item_type, item_id)
        al = self.to_base(D(rec["allocated_qty"]), rec["unit"], item_type, item_id)
        so = self.to_base(D(rec["on_order_qty"]), rec["unit"], item_type, item_id)
        if so and within_horizon:
            rd = dt.date.fromisoformat(rec["expected_receipt_date"])
            if not (rd <= self.h_end):
                so = ZERO
        return oh - al + (so if within_horizon else ZERO)

    def safety(self, item_type: str, item_id: str) -> Decimal:
        rec = self.materials[item_id] if item_type == "MATERIAL" else self.products[item_id]
        return D(rec["safety_stock_qty"])

    # ---- BOM 선택 (schema §3.6) ----
    def bom_candidates(self, product: str, day: dt.date, qty: Decimal, site: str | None = None) -> list[str]:
        out = []
        for b in self.boms.values():
            if b["product_id"] != product or b["status"] != "APPROVED" or not b["is_active"]:
                continue
            if dt.date.fromisoformat(b["valid_from"]) > day:
                continue
            if b["valid_to"] is not None and day > dt.date.fromisoformat(b["valid_to"]):
                continue
            if qty < D(b["min_qty"]) or (b["max_qty"] is not None and qty >= D(b["max_qty"])):
                continue
            if b["site_id"] is not None and b["site_id"] != site:
                continue
            out.append(b["bom_id"])
        return sorted(out)

    def select_bom(self, product: str, day: dt.date, qty: Decimal) -> str:
        c = self.bom_candidates(product, day, qty, self.p["site_id"])
        if len(c) != 1:
            raise ValueError(f"ERR-BOMVER: {product} {day} {qty} → {c}")
        return c[0]

    def per_unit(self, bom_id: str, ln: dict) -> tuple[str, str, Decimal]:
        """(item_type, item_id, 부모 1 기준단위당 구성품 기준단위 소요량) — 손실률 포함."""
        if ln["component_type"] == "MATERIAL":
            t, i = "MATERIAL", ln["component_material_id"]
        else:
            t, i = "PRODUCT", ln["component_product_id"]
        q = self.to_base(D(ln["qty_per"]), ln["unit"], t, i) * (1 + D(ln["scrap_rate"])) / D(self.boms[bom_id]["base_qty"])
        return t, i, q

    def llc(self) -> dict[str, int]:
        """저수준 코드: 승인·활성 BOM 전체 구조에서 품목이 나타나는 가장 깊은 수준."""
        level = {p: 0 for p in self.products}
        changed = True
        guard = 0
        while changed:
            changed = False
            guard += 1
            if guard > 50:
                raise ValueError("ERR-BOMCYCLE: LLC 수렴 실패")
            for b in self.boms.values():
                if b["status"] != "APPROVED" or not b["is_active"]:
                    continue
                for ln in self.lines[b["bom_id"]]:
                    c = ln["component_product_id"]
                    if c and level[c] < level[b["product_id"]] + 1:
                        level[c] = level[b["product_id"]] + 1
                        changed = True
        return level

    def open_orders(self) -> list[dict]:
        return [o for o in self.E["Order"] if o["status"] == "OPEN"
                and self.h_start <= dt.date.fromisoformat(o["due_date"]) <= self.h_end]


def workday_add(day: dt.date, n: int) -> dt.date:
    d = day
    while n > 0:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def workdays_between(start_exclusive: dt.date, end_inclusive: dt.date) -> int:
    n, d = 0, start_exclusive
    while d < end_inclusive:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


# ---------------------------------------------------------------------------
# §1·§2·§3 계획 기간 순소요 (LLC 순 1회 차감)
# ---------------------------------------------------------------------------
def horizon_requirements(m: Model) -> dict:
    llc = m.llc()
    independent = defaultdict(lambda: ZERO)
    for o in m.open_orders():
        independent[o["product_id"]] += m.to_base(D(o["order_qty"]), o["unit"], "PRODUCT", o["product_id"])
    dependent = defaultdict(lambda: ZERO)
    material_gross = defaultdict(lambda: ZERO)
    req, explosion = {}, []
    inc_ss = m.p["include_safety_stock"]
    for level in sorted(set(llc.values())):
        for p in sorted(x for x in llc if llc[x] == level):
            gross = independent[p] + dependent[p]
            avail = m.available("PRODUCT", p)
            ss = m.safety("PRODUCT", p) if inc_ss else ZERO
            net = max(ZERO, gross + ss - avail)
            bom = m.select_bom(p, m.h_start, net) if net > 0 else None
            req[p] = {"llc": level, "independent_demand": independent[p], "dependent_demand": dependent[p],
                      "gross": gross, "available": avail, "safety_stock": ss, "net_requirement": net, "bom_id": bom}
            if bom is None:
                continue
            for ln in m.lines[bom]:
                t, i, per = m.per_unit(bom, ln)
                qty = net * per
                explosion.append({"parent": p, "bom_id": bom, "line_no": ln["line_no"], "component_type": t,
                                  "component_id": i, "parent_net": net, "per_parent_base": per, "component_qty_base": qty})
                if t == "PRODUCT":
                    dependent[i] += qty
                else:
                    material_gross[i] += qty
    shortage = {}
    inc_mss = m.p["include_material_safety_stock"]
    for mid in sorted(m.materials):
        g = material_gross.get(mid, ZERO)
        avail = m.available("MATERIAL", mid)
        ss = m.safety("MATERIAL", mid) if inc_mss else ZERO
        shortage[mid] = {"gross": g, "available": avail, "safety_stock": ss, "shortage": max(ZERO, g + ss - avail),
                         "unit": m.materials[mid]["base_unit"]}
    return {"requirements": req, "explosion": explosion, "material_gross": dict(material_gross), "shortage": shortage}


def horizon_capacity(m: Model, hr: dict) -> dict:
    days = workdays_between(m.ref, m.h_end) - workdays_between(m.ref, m.h_start - dt.timedelta(days=1))
    load = defaultdict(lambda: ZERO)
    for p, r in hr["requirements"].items():
        if r["net_requirement"] <= 0:
            continue
        for op in m.ops[p]:
            load[op["resource_id"]] += r["net_requirement"] * D(op["run_time_per_unit_h"]) + D(op["setup_time_h"])
    out = {}
    for rid, res in sorted(m.resources.items()):
        cap = D(res["regular_hours_per_day"]) * days
        out[rid] = {"required_h": load[rid], "regular_capacity_h": cap, "excess_h": max(ZERO, load[rid] - cap), "workdays": days}
    return out


# ---------------------------------------------------------------------------
# §4 주문별 납기 판정 (E01 구현 규칙)
# ---------------------------------------------------------------------------
def order_feasibility(m: Model, hr: dict, lt_override: dict[str, int] | None = None) -> list[dict]:
    pref_lt = {s["material_id"]: s["lead_time_days"] for s in m.sm if s["is_preferred"]}
    if lt_override:
        pref_lt.update(lt_override)
    short = {mid for mid, s in hr["shortage"].items() if s["shortage"] > 0}
    bom_of = {p: r["bom_id"] for p, r in hr["requirements"].items()}
    stock = {p: m.available("PRODUCT", p, within_horizon=False) for p in m.products}
    cum = defaultdict(lambda: ZERO)
    results = []
    for o in sorted(m.open_orders(), key=lambda x: (x["due_date"], x["order_id"])):
        p, due = o["product_id"], dt.date.fromisoformat(o["due_date"])
        qty = m.to_base(D(o["order_qty"]), o["unit"], "PRODUCT", p)
        take = min(stock[p], qty)
        stock[p] -= take
        q = qty - take
        hours = defaultdict(lambda: ZERO)
        mats, lt_total, sf_prod_total = set(), 0, {}
        if q > 0:
            bom = bom_of[p] or m.select_bom(p, m.h_start, q)
            lt_total = m.products[p]["manuf_lead_time_days"]
            for op in m.ops[p]:
                hours[op["resource_id"]] += q * D(op["run_time_per_unit_h"]) + D(op["setup_time_h"])
            sf_lt = 0
            for ln in m.lines[bom]:
                t, i, per = m.per_unit(bom, ln)
                if t == "MATERIAL":
                    mats.add(i)
                    continue
                need = q * per
                take_sf = min(stock[i], need)
                stock[i] -= take_sf
                sf_prod = need - take_sf
                sf_prod_total[i] = sf_prod
                if sf_prod > 0:
                    sf_lt = max(sf_lt, m.products[i]["manuf_lead_time_days"])
                    for op in m.ops[i]:
                        hours[op["resource_id"]] += sf_prod * D(op["run_time_per_unit_h"]) + D(op["setup_time_h"])
                    sf_bom = bom_of[i] or m.select_bom(i, m.h_start, sf_prod)
                    for sln in m.lines[sf_bom]:
                        st, si, _ = m.per_unit(sf_bom, sln)
                        if st == "MATERIAL":
                            mats.add(si)
            lt_total += sf_lt
        cap_fail = []
        workdays = workdays_between(m.ref, due)
        for rid, h in sorted(hours.items()):
            cum[rid] += h
            cap = D(m.resources[rid]["regular_hours_per_day"]) * workdays
            if cum[rid] > cap:
                cap_fail.append(rid)
        if q > 0:
            short_lts = [pref_lt[x] for x in mats if x in short]
            ready = m.ref + dt.timedelta(days=max(short_lts)) if short_lts else m.ref
            days_needed = max((math.ceil(h / D(m.resources[r]["regular_hours_per_day"])) for r, h in hours.items()), default=0)
            n = max(lt_total, days_needed)
            completion = workday_add(ready, n)
            without_material = workday_add(m.ref, n)
        else:
            ready, n, completion, without_material = m.ref, 0, m.ref, m.ref
        reasons = []
        if completion > due and without_material <= due:
            reasons.append("MATERIAL_LEADTIME")
        if cap_fail:
            reasons.append("CAPACITY_EXCEEDED")
        if completion > due:
            reasons.append("DUE_DATE_MISSED")
        results.append({"order_id": o["order_id"], "product_id": p, "due_date": o["due_date"], "order_qty": qty,
                        "from_stock": take, "production_qty": q, "semi_finished_production": sf_prod_total,
                        "material_ready_date": ready.isoformat(), "production_days": n,
                        "expected_completion_date": completion.isoformat(), "slack_days": (due - completion).days,
                        "capacity_exceeded_resources": cap_fail, "reasons": reasons, "feasible": not reasons})
    return results


# ---------------------------------------------------------------------------
# §5 계획안 비교 (E01 구현 규칙)
# ---------------------------------------------------------------------------
def plan_evaluation(m: Model) -> dict:
    """v2 계획안 평가 (decision_logic §6.1 '5절 계획안 평가 v2')."""
    weeks = [m.h_start + dt.timedelta(days=7 * w) for w in range(4)]
    outsourcers = m.p["outsourcers"]
    open_orders = m.open_orders()
    out = {}
    for plan in m.E["ProductionPlan"]:
        pid, ot_allowed = plan["plan_id"], plan["overtime_allowed"]
        lines = [l for l in m.E["ProductionPlanLine"] if l["plan_id"] == pid and D(l["planned_qty"]) > 0]
        req = defaultdict(lambda: ZERO)
        consumption = defaultdict(lambda: ZERO)
        outsourced = defaultdict(lambda: ZERO)
        outsource_cost = ZERO
        for l in lines:
            qty, p, ws = D(l["planned_qty"]), l["product_id"], l["period_start"]
            if l["production_mode"] == "OUTSOURCE":
                outsource_cost += qty * D(m.products[p]["outsourcing_unit_cost"])
                outsourced[(p, ws)] += qty
                continue
            for op in m.ops[p]:
                req[(op["resource_id"], ws)] += qty * D(op["run_time_per_unit_h"]) + D(op["setup_time_h"])
            bom = m.select_bom(p, dt.date.fromisoformat(ws), qty)
            for ln in m.lines[bom]:
                t, i, per = m.per_unit(bom, ln)
                if t == "MATERIAL":
                    consumption[i] += qty * per
        capacity, ratio = [], {}
        worked_reg = worked_ot = reg_cost = ot_cost = excess_total = ZERO
        for rid, res in sorted(m.resources.items()):
            for wd in weeks:
                w = wd.isoformat()
                rc = D(res["regular_hours_per_day"]) * 5
                oc = D(res["overtime_hours_per_day_max"]) * 5 if ot_allowed else ZERO
                need = req[(rid, w)]
                wr = min(need, rc)
                wo = min(max(ZERO, need - rc), oc)
                ex = max(ZERO, need - rc - oc)
                ratio[(rid, w)] = Fraction(1) if need <= rc + oc else Fraction(rc + oc) / Fraction(need)
                worked_reg += wr
                worked_ot += wo
                excess_total += ex
                reg_cost += wr * D(res["cost_per_hour"])
                ot_cost += wo * D(res["overtime_cost_per_hour"])
                capacity.append({"resource_id": rid, "week_start": w, "required_h": need, "regular_capacity_h": rc,
                                 "overtime_capacity_h": oc, "worked_regular_h": wr, "worked_overtime_h": wo, "excess_h": ex})
        completed_lines = []
        supply = defaultdict(list)  # 완제품 공급 이벤트 (일자, 수량)
        for p in m.products:
            if m.products[p]["product_type"] == "FINISHED":
                supply[p].append((m.ref, m.available("PRODUCT", p, within_horizon=False)))
        for l in lines:
            p, ws, qty = l["product_id"], l["period_start"], D(l["planned_qty"])
            if l["production_mode"] == "OUTSOURCE":
                if m.products[p]["product_type"] == "FINISHED":
                    lt = next(o["lead_time_days"] for o in outsourcers.values() if o["product_id"] == p)
                    supply[p].append((dt.date.fromisoformat(ws) + dt.timedelta(days=lt), qty))
                continue
            r = min(ratio[(op["resource_id"], ws)] for op in m.ops[p])
            done = Decimal(math.floor(Fraction(qty) * r))
            completed_lines.append({"line_no": l["line_no"], "product_id": p, "week_start": ws, "planned_qty": qty,
                                    "completed_qty": done, "unproduced_qty": qty - done})
            if m.products[p]["product_type"] == "FINISHED":
                supply[p].append((dt.date.fromisoformat(ws) + dt.timedelta(days=4), done))
        late, cum = [], defaultdict(lambda: ZERO)
        for o in sorted(open_orders, key=lambda x: (x["due_date"], x["order_id"])):
            p, due = o["product_id"], dt.date.fromisoformat(o["due_date"])
            cum[p] += D(o["order_qty"])
            avail = sum((q for d_, q in supply[p] if d_ <= due), ZERO)
            if avail < cum[p]:
                late.append({"order_id": o["order_id"], "due_date": o["due_date"], "shortfall_qty": min(D(o["order_qty"]), cum[p] - avail)})
        mat_cost = sum((q * D(m.materials[i]["unit_cost"]) for i, q in consumption.items()), ZERO)
        shortages = {}
        for mid in sorted(m.materials):
            need = consumption.get(mid, ZERO) + (m.safety("MATERIAL", mid) if m.p["include_material_safety_stock"] else ZERO)
            s = max(ZERO, need - m.available("MATERIAL", mid))
            if s > 0:
                shortages[mid] = s
        out[pid] = {
            "overtime_allowed": ot_allowed,
            "costs_krw": {"material": mat_cost, "regular_production": reg_cost, "overtime": ot_cost,
                          "outsourcing": outsource_cost, "inventory_holding": "미산정", "late_penalty": "미산정",
                          "sum_of_computed_items_reference": mat_cost + reg_cost + ot_cost + outsource_cost},
            "inhouse_required_h": sum(req.values(), ZERO),
            "worked_regular_h": worked_reg, "worked_overtime_h": worked_ot,
            "capacity_excess_total_h": excess_total,
            "outsourced_qty": {f"{p}|{w}": q for (p, w), q in sorted(outsourced.items())},
            "capacity": capacity,
            "completed_lines": completed_lines,
            "unproduced_qty_total": sum((c["unproduced_qty"] for c in completed_lines), ZERO),
            "material_consumption": dict(sorted(consumption.items())),
            "material_shortage": shortages,
            "material_shortage_total_by_unit": _sum_by_unit(m, shortages),
            "late_orders": late,
            "orders_data_invalid": [],
        }
    return out


def _sum_by_unit(m: Model, d: dict) -> dict:
    s = defaultdict(lambda: ZERO)
    for mid, q in d.items():
        s[m.materials[mid]["base_unit"]] += q
    return dict(sorted(s.items()))


# ---------------------------------------------------------------------------
# CQ 기대 결과
# ---------------------------------------------------------------------------
def ancestors_finished(m: Model, item_type: str, item_id: str) -> list[str]:
    """승인·활성 BOM 어느 버전에서든 품목을 직·간접으로 쓰는 완제품."""
    found, frontier = set(), {(item_type, item_id)}
    seen = set()
    while frontier:
        nxt = set()
        for t, i in frontier:
            for b in m.boms.values():
                if b["status"] != "APPROVED" or not b["is_active"]:
                    continue
                for ln in m.lines[b["bom_id"]]:
                    if (t == "MATERIAL" and ln["component_material_id"] == i) or (t == "PRODUCT" and ln["component_product_id"] == i):
                        parent = b["product_id"]
                        if parent not in seen:
                            seen.add(parent)
                            nxt.add(("PRODUCT", parent))
        frontier = nxt
    return sorted(x for x in seen if m.products[x]["product_type"] == "FINISHED")


def cq_results(m: Model, hr: dict, feas: list[dict], plans: dict, paths: Paths) -> dict:
    cq = m.p["cq"]
    R = {}
    R["CQ-01"] = {pid: [c for c in v["capacity"] if c["excess_h"] > 0] for pid, v in plans.items()}
    R["CQ-02"] = {p: [{"sequence_no": op["sequence_no"], "operation_id": op["operation_id"], "resource_id": op["resource_id"]}
                      for op in m.ops[p]] for p in sorted(m.ops)}
    rid = cq["CQ-03"]["resource_id"]
    direct = sorted({op["product_id"] for ops in m.ops.values() for op in ops if op["resource_id"] == rid})
    affected = set(direct)
    for p in direct:
        affected |= set(ancestors_finished(m, "PRODUCT", p))
    R["CQ-03"] = {"resource_id": rid, "products_direct": direct, "products_affected": sorted(affected),
                  "open_orders": sorted(o["order_id"] for o in m.open_orders() if o["product_id"] in affected)}
    cases = []
    for c in cq["CQ-04"]["cases"]:
        cand = m.bom_candidates(c["product_id"], dt.date.fromisoformat(c["date"]), D(c["qty"]), m.p["site_id"])
        status = "SELECTED" if len(cand) == 1 else ("NONE" if not cand else "AMBIGUOUS")
        lines = []
        if status == "SELECTED":
            lines = [{"line_no": ln["line_no"], "component_id": ln["component_material_id"] or ln["component_product_id"],
                      "qty_per": D(ln["qty_per"]), "unit": ln["unit"]} for ln in m.lines[cand[0]]]
        cases.append({**c, "candidates": cand, "status": status, "lines": lines})
    R["CQ-04"] = cases
    R["CQ-05"] = {mid: ancestors_finished(m, "MATERIAL", mid) for mid in cq["CQ-05"]["material_ids"]}
    R["CQ-06"] = {k: hr["material_gross"][k] for k in sorted(hr["material_gross"])}
    R["CQ-07"] = {p: r["net_requirement"] for p, r in sorted(hr["requirements"].items())}
    R["CQ-08"] = {k: v["shortage"] for k, v in hr["shortage"].items() if v["shortage"] > 0}
    R["CQ-09"] = {mid: sorted(({"supplier_id": s["supplier_id"], "lead_time_days": s["lead_time_days"],
                                "min_order_qty": D(s["min_order_qty"]) if s["min_order_qty"] else None, "is_preferred": s["is_preferred"]}
                               for s in m.sm if s["material_id"] == mid), key=lambda x: x["supplier_id"])
                  for mid in cq["CQ-09"]["material_ids"]}
    n = cq["CQ-10"]["min_lead_time_days"]
    long_mats = sorted(s["material_id"] for s in m.sm if s["is_preferred"] and s["lead_time_days"] >= n)
    by_prod = defaultdict(list)
    for mid in long_mats:
        for p in ancestors_finished(m, "MATERIAL", mid):
            by_prod[p].append(mid)
    R["CQ-10"] = {"min_lead_time_days": n, "materials": long_mats, "products": dict(sorted(by_prod.items()))}
    c11 = cq["CQ-11"]
    base_lt = next(s["lead_time_days"] for s in m.sm if s["is_preferred"] and s["material_id"] == c11["material_id"])
    delayed = order_feasibility(m, hr, {c11["material_id"]: base_lt + c11["delay_days"]})
    base = {r["order_id"]: r for r in feas}
    R["CQ-11"] = {**c11, "newly_infeasible_orders": [
        {"order_id": r["order_id"], "reasons": r["reasons"], "expected_completion_date": r["expected_completion_date"]}
        for r in delayed if not r["feasible"] and base[r["order_id"]]["feasible"]]}
    sums = defaultdict(lambda: ZERO)
    for o in m.open_orders():
        sums[o["product_id"]] += D(o["order_qty"])
    R["CQ-12"] = dict(sorted(sums.items()))
    R["CQ-13"] = feas
    R["CQ-14"] = {pid: {"costs_krw": v["costs_krw"], "worked_overtime_h": v["worked_overtime_h"],
                        "capacity_excess_total_h": v["capacity_excess_total_h"], "outsourced_qty_total": sum(v["outsourced_qty"].values(), ZERO),
                        "unproduced_qty_total": v["unproduced_qty_total"],
                        "material_shortage_total_by_unit": v["material_shortage_total_by_unit"],
                        "late_orders": [x["order_id"] for x in v["late_orders"]], "orders_data_invalid": v["orders_data_invalid"]}
                  for pid, v in plans.items()}
    R["CQ-15"] = {"dataset": "clean", "duplicate_business_ids": []}
    R["CQ-16"] = {"dataset": "clean", "dangling_references": []}
    R["CQ-17"] = {"dataset": "clean", "horizon_selection": {
        p: {"date": m.h_start.isoformat(), "qty": r["net_requirement"],
            "candidates": m.bom_candidates(p, m.h_start, r["net_requirement"], m.p["site_id"])}
        for p, r in sorted(hr["requirements"].items()) if r["net_requirement"] > 0}, "overlapping_active_pairs": []}
    R["CQ-18"] = {"dataset": "clean", "cycles": []}
    # CQ-19: 값의 원본 위치 (BOM-FG001-V2 line 2 = M001 1000 g)
    target_uid = next(l["record_uid"] for l in m.E["BOMLine"] if l["bom_id"] == "BOM-FG001-V2" and l["line_no"] == 2)
    with open(paths.row_map, encoding="utf-8", newline="") as f:
        locs = [r for r in csv.DictReader(f) if r["canonical_record_uid"] == target_uid]
    R["CQ-19"] = {"canonical": {"entity": "BOMLine", "bom_id": "BOM-FG001-V2", "line_no": 2, "record_uid": target_uid,
                                "qty_per": "1000", "unit": "g"},
                  "locations": [{"vendor": r["vendor"], "file": r["file"], "sheet": r["sheet"], "row_number": int(r["row_number"]),
                                 "column": {"A": "qty_per", "B": "소요량"}[r["vendor"]],
                                 "displayed_value": {"A": "1", "B": "1,000"}[r["vendor"]],
                                 "displayed_unit": {"A": "kg", "B": "g"}[r["vendor"]]} for r in locs]}
    with open(paths.id_map, encoding="utf-8", newline="") as f:
        ids = list(csv.DictReader(f))
    pairs = defaultdict(dict)
    for r in ids:
        if r["entity"] == "Product":
            pairs[r["canonical_id"]][r["vendor"]] = r["vendor_code"]
    R["CQ-20"] = {p: {"vendor_a_code": v.get("A"), "vendor_b_code": v.get("B"), "rule": "vendor_id_map_v1.csv"}
                  for p, v in sorted(pairs.items())}
    return R


def to_jsonable(x):
    if isinstance(x, Decimal):
        return fmt(x)
    if isinstance(x, dict):
        return {str(k): to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [to_jsonable(v) for v in x]
    if isinstance(x, dt.date):
        return x.isoformat()
    return x


def compute(paths: Paths) -> dict:
    gt = read_json(paths.ground_truth)
    m = Model(gt)
    hr = horizon_requirements(m)
    feas = order_feasibility(m, hr)
    plans = plan_evaluation(m)
    expected = {
        "implementation": "scripts/e01_expected.py (구현 A)",
        "production_requirements": hr["requirements"],
        "bom_explosion": hr["explosion"],
        "material_gross_requirements": hr["material_gross"],
        "material_shortage": hr["shortage"],
        "horizon_resource_load": horizon_capacity(m, hr),
        "order_feasibility": feas,
        "plan_evaluation": plans,
        "cq": cq_results(m, hr, feas, plans, paths),
        "unverifiable_cq": {},
    }
    gt["expected"] = to_jsonable(expected)
    write_json(paths.ground_truth, gt)
    return gt["expected"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=Path, default=None)
    args = ap.parse_args(argv)
    exp = compute(Paths(args.out_root))
    print({p: v["net_requirement"] for p, v in exp["production_requirements"].items()})
    print({k: v["shortage"] for k, v in exp["material_shortage"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
