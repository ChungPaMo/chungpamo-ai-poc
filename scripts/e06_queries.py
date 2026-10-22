"""E06 관계 조회 Q1~Q5 — Python 자료구조 / SQLite / RDFLib SPARQL 비교.

질의 정의: docs/evaluation_protocol.md §5.2 (Q1~Q5) → ontology_competency_questions.md §2에서 CQ-04·05·06·08·10으로 흡수.
기대 정답: data/canonical/ground_truth_v2.json expected.cq (E01 scripts/e01_expected.py가 독립 계산). 매개변수: parameters.cq.

관계 탐색과 수량 계산을 분리한다.
- 각 방식의 '사실 제공자(provider)'가 자기 질의 언어로 관계·사실을 조회한다 (BOM 후보 선택, 라인, 재고, 주문, 구조 간선, 상위 완제품 탐색).
- Q3(CQ-06)·Q4(CQ-08)의 순소요 전개(LLC 순서, 1회 차감, 단위 환산, 손실률)는 공통 Python 함수 mrp()가 계산한다
  (decision_logic §1~§3, §2.1). SQL·SPARQL만으로 전개한 것이 아니다.
SPARQL 상위 탐색: 속성 경로는 중간 단계의 BOM 상태(APPROVED·활성)를 걸러낼 수 없으므로,
  'filtered' = CONSTRUCT로 승인·활성 BOM의 사용 간선(cp:usedBy)을 만든 뒤 경로 질의, 'naive' = 원본 그래프에 경로만 적용 (비교용).
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections import defaultdict
from decimal import Decimal

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

import e05_dataset as D
import e05_validate_sql as SQ
from e06_build_rdf import CP, ID, build_graph

ZERO = Decimal(0)
PREFIX = f"PREFIX cp: <{CP}>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"


def dd(v):
    return Decimal(str(v))


# ------------------------------------------------------------------ Python 자료구조
class PyProvider:
    name = "python"

    def __init__(self, ents, params):
        self.E, self.p = ents, params
        self.units = {u["unit_code"]: u for u in ents["Unit"]}
        self.products = {x["product_id"]: x for x in ents["Product"]}
        self.materials = {x["material_id"]: x for x in ents["Material"]}
        self.boms = {x["bom_id"]: x for x in ents["BOM"]}
        self.lines = defaultdict(list)
        for ln in sorted(ents["BOMLine"], key=lambda l: (l["bom_id"], l["line_no"])):
            self.lines[ln["bom_id"]].append(ln)
        self.inv = {(i["item_type"], i["item_id"]): i for i in ents["Inventory"]}

    def unit(self, code):
        u = self.units[code]
        return u["dimension"], dd(u["to_base_factor"])

    def item(self, t, i):
        r = (self.materials if t == "MATERIAL" else self.products)[i]
        return r["base_unit"], dd(r["safety_stock_qty"])

    def item_ids(self):
        return sorted(self.products), sorted(self.materials)

    def inventory(self, t, i):
        r = self.inv.get((t, i))
        return None if r is None else {k: r.get(k) for k in ("on_hand_qty", "allocated_qty", "on_order_qty", "expected_receipt_date", "unit")}

    def open_orders(self, h0, h1):
        return [(o["product_id"], dd(o["order_qty"]), o["unit"]) for o in self.E["Order"]
                if o["status"] == "OPEN" and h0 <= o["due_date"] <= h1]

    def bom_candidates(self, product, day, qty):
        out = []
        for b in self.boms.values():
            if b["product_id"] != product or b["status"] != "APPROVED" or not b["is_active"] or b["valid_from"] > day:
                continue
            if b["valid_to"] is not None and day > b["valid_to"]:
                continue
            if qty < dd(b["min_qty"]) or (b["max_qty"] is not None and qty >= dd(b["max_qty"])) or b["site_id"] is not None:
                continue
            out.append(b["bom_id"])
        return sorted(out)

    def bom_lines(self, bom_id):
        b = self.boms[bom_id]
        return dd(b["base_qty"]), [(ln["line_no"], ln["component_type"], ln["component_material_id"] or ln["component_product_id"], dd(ln["qty_per"]),
                                    ln["unit"], dd(ln["scrap_rate"] or 0)) for ln in self.lines[bom_id]]

    def structure_edges(self):
        return sorted({(b["product_id"], ln["component_product_id"]) for b in self.boms.values() if b["status"] == "APPROVED" and b["is_active"]
                       for ln in self.lines[b["bom_id"]] if ln["component_product_id"]})

    def ancestors_finished(self, t, i):
        found, frontier = set(), {(t, i)}
        while frontier:
            nxt = set()
            for ft, fi in frontier:
                for b in self.boms.values():
                    if b["status"] != "APPROVED" or not b["is_active"]:
                        continue
                    for ln in self.lines[b["bom_id"]]:
                        if (ft == "MATERIAL" and ln["component_material_id"] == fi) or (ft == "PRODUCT" and ln["component_product_id"] == fi):
                            if b["product_id"] not in found:
                                found.add(b["product_id"])
                                nxt.add(("PRODUCT", b["product_id"]))
            frontier = nxt
        return sorted(x for x in found if self.products[x]["product_type"] == "FINISHED")

    def long_lead_materials(self, n):
        return sorted(s["material_id"] for s in self.E["SupplierMaterial"] if s["is_preferred"] and s["lead_time_days"] >= n)


# ------------------------------------------------------------------ SQLite
SQL = {
    "unit": 'SELECT dimension, to_base_factor FROM "Unit" WHERE unit_code = ?',
    "item_m": 'SELECT base_unit, safety_stock_qty FROM "Material" WHERE material_id = ?',
    "item_p": 'SELECT base_unit, safety_stock_qty FROM "Product" WHERE product_id = ?',
    "ids": 'SELECT product_id FROM "Product" ORDER BY 1',
    "ids_m": 'SELECT material_id FROM "Material" ORDER BY 1',
    "inventory": 'SELECT on_hand_qty, allocated_qty, on_order_qty, expected_receipt_date, unit FROM "Inventory" WHERE item_type = ? AND item_id = ?',
    "orders": 'SELECT product_id, order_qty, unit FROM "Order" WHERE status = \'OPEN\' AND due_date BETWEEN ? AND ?',
    "candidates": '''SELECT bom_id FROM "BOM" WHERE product_id = ? AND status = 'APPROVED' AND is_active = 1 AND valid_from <= :d
                     AND (valid_to IS NULL OR :d <= valid_to) AND CAST(min_qty AS REAL) <= :q AND (max_qty IS NULL OR :q < CAST(max_qty AS REAL))
                     AND site_id IS NULL ORDER BY bom_id''',
    "base_qty": 'SELECT base_qty FROM "BOM" WHERE bom_id = ?',
    "lines": '''SELECT line_no, component_type, COALESCE(component_material_id, component_product_id), qty_per, unit, COALESCE(scrap_rate, '0')
                FROM "BOMLine" WHERE bom_id = ? ORDER BY CAST(line_no AS INTEGER)''',
    "edges": '''SELECT DISTINCT b.product_id, l.component_product_id FROM "BOM" b JOIN "BOMLine" l ON l.bom_id = b.bom_id
                WHERE b.status = 'APPROVED' AND b.is_active = 1 AND l.component_product_id IS NOT NULL ORDER BY 1, 2''',
    "ancestors": '''WITH RECURSIVE up(pid) AS (
                      SELECT b.product_id FROM "BOMLine" l JOIN "BOM" b ON b.bom_id = l.bom_id
                      WHERE b.status = 'APPROVED' AND b.is_active = 1
                        AND ((:t = 'MATERIAL' AND l.component_material_id = :i) OR (:t = 'PRODUCT' AND l.component_product_id = :i))
                      UNION
                      SELECT b.product_id FROM up JOIN "BOMLine" l ON l.component_product_id = up.pid JOIN "BOM" b ON b.bom_id = l.bom_id
                      WHERE b.status = 'APPROVED' AND b.is_active = 1)
                    SELECT DISTINCT up.pid FROM up JOIN "Product" p ON p.product_id = up.pid WHERE p.product_type = 'FINISHED' ORDER BY 1''',
    "long_lead": '''SELECT material_id FROM "SupplierMaterial" WHERE is_preferred = 1 AND CAST(lead_time_days AS INTEGER) >= ? ORDER BY 1''',
}


class SqlProvider:
    name = "sqlite"

    def __init__(self, ents, params):
        self.con = sqlite3.connect(":memory:")
        SQ.staging(self.con, ents)
        self.p = params

    def one(self, k, *a):
        return self.con.execute(SQL[k], a).fetchone()

    def unit(self, code):
        d, f = self.one("unit", code)
        return d, dd(f)

    def item(self, t, i):
        b, s = self.one("item_m" if t == "MATERIAL" else "item_p", i)
        return b, dd(s)

    def item_ids(self):
        return [r[0] for r in self.con.execute(SQL["ids"])], [r[0] for r in self.con.execute(SQL["ids_m"])]

    def inventory(self, t, i):
        r = self.one("inventory", t, i)
        return None if r is None else dict(zip(("on_hand_qty", "allocated_qty", "on_order_qty", "expected_receipt_date", "unit"), r))

    def open_orders(self, h0, h1):
        return [(p, dd(q), u) for p, q, u in self.con.execute(SQL["orders"], (h0, h1))]

    def bom_candidates(self, product, day, qty):
        return [r[0] for r in self.con.execute(SQL["candidates"].replace("?", ":p"), {"p": product, "d": day, "q": float(qty)})]

    def bom_lines(self, bom_id):
        return dd(self.one("base_qty", bom_id)[0]), [(int(n), t, c, dd(q), u, dd(s)) for n, t, c, q, u, s in self.con.execute(SQL["lines"], (bom_id,))]

    def structure_edges(self):
        return [tuple(r) for r in self.con.execute(SQL["edges"])]

    def ancestors_finished(self, t, i):
        return [r[0] for r in self.con.execute(SQL["ancestors"], {"t": t, "i": i})]

    def long_lead_materials(self, n):
        return [r[0] for r in self.con.execute(SQL["long_lead"], (n,))]


# ------------------------------------------------------------------ RDFLib SPARQL
SPARQL = {
    "unit": "SELECT ?d ?f WHERE { ?u cp:hasKey ?k ; cp:Unit_dimension ?d ; cp:Unit_to_base_factor ?f }",
    "item_m": "SELECT ?b ?s WHERE { ?r cp:hasKey ?k ; cp:Material_base_unit ?b ; cp:Material_safety_stock_qty ?s }",
    "item_p": "SELECT ?b ?s WHERE { ?r cp:hasKey ?k ; cp:Product_base_unit ?b ; cp:Product_safety_stock_qty ?s }",
    "ids": "SELECT ?id WHERE { ?r a cp:ProductRecord ; cp:Product_product_id ?id } ORDER BY ?id",
    "ids_m": "SELECT ?id WHERE { ?r a cp:MaterialRecord ; cp:Material_material_id ?id } ORDER BY ?id",
    "inventory": """SELECT ?oh ?al ?oo ?rd ?u WHERE { ?r cp:Inventory_item_id ?k ; cp:Inventory_item_type ?t ; cp:Inventory_on_hand_qty ?oh ; cp:Inventory_unit ?u .
                    OPTIONAL { ?r cp:Inventory_allocated_qty ?al } OPTIONAL { ?r cp:Inventory_on_order_qty ?oo } OPTIONAL { ?r cp:Inventory_expected_receipt_date ?rd } }""",
    "orders": """SELECT ?p ?q ?u WHERE { ?o cp:Order_status "OPEN" ; cp:Order_due_date ?d ; cp:Order_product_id ?p ; cp:Order_order_qty ?q ; cp:Order_unit ?u .
                 FILTER(?d >= ?h0 && ?d <= ?h1) }""",
    "candidates": """SELECT ?id WHERE { ?b cp:BOM_product_id ?p ; cp:BOM_status "APPROVED" ; cp:BOM_is_active true ; cp:BOM_valid_from ?vf ; cp:BOM_min_qty ?mn ; cp:BOM_bom_id ?id .
                     OPTIONAL { ?b cp:BOM_valid_to ?vt } OPTIONAL { ?b cp:BOM_max_qty ?mx } OPTIONAL { ?b cp:BOM_site_id ?st }
                     FILTER(?vf <= ?d && (!BOUND(?vt) || ?d <= ?vt) && ?mn <= ?q && (!BOUND(?mx) || ?q < ?mx) && !BOUND(?st)) } ORDER BY ?id""",
    "base_qty": "SELECT ?q WHERE { ?b cp:hasKey ?k ; cp:BOM_base_qty ?q }",
    "lines": """SELECT ?n ?t ?c ?q ?u ?s WHERE { ?l cp:BOMLine_bom_id ?k ; cp:BOMLine_line_no ?n ; cp:BOMLine_component_type ?t ; cp:BOMLine_qty_per ?q ; cp:BOMLine_unit ?u .
                { ?l cp:BOMLine_component_material_id ?c } UNION { ?l cp:BOMLine_component_product_id ?c } OPTIONAL { ?l cp:BOMLine_scrap_rate ?s } } ORDER BY ?n""",
    "edges": """SELECT DISTINCT ?p ?c WHERE { ?b cp:BOM_status "APPROVED" ; cp:BOM_is_active true ; cp:BOM_product_id ?p ; cp:hasKey ?bk .
                ?l cp:BOMLine_bom_id ?bk ; cp:BOMLine_component_product_id ?c } ORDER BY ?p ?c""",
    "used_by": """CONSTRUCT { ?child cp:usedBy ?parent . ?parent cp:productType ?pt } WHERE {
                    ?b cp:BOM_status "APPROVED" ; cp:BOM_is_active true ; cp:BOM_product_id ?parent ; cp:hasKey ?bk .
                    ?l cp:BOMLine_bom_id ?bk . { ?l cp:BOMLine_component_material_id ?child } UNION { ?l cp:BOMLine_component_product_id ?child }
                    OPTIONAL { ?pr cp:hasKey ?parent ; cp:Product_product_type ?pt } }""",
    "ancestors": """SELECT DISTINCT ?fg WHERE { ?start cp:usedBy+ ?fg . ?fg cp:productType "FINISHED" } ORDER BY ?fg""",
    "ancestors_naive": """SELECT DISTINCT ?fg WHERE {
                    ?start (^cp:BOMLine_component_material_id|^cp:BOMLine_component_product_id)/cp:BOMLine_bom_id/^cp:hasKey/cp:BOM_product_id ?p1 .
                    ?p1 (^cp:BOMLine_component_product_id/cp:BOMLine_bom_id/^cp:hasKey/cp:BOM_product_id)* ?fg .
                    ?fgr cp:hasKey ?fg ; cp:Product_product_type "FINISHED" } ORDER BY ?fg""",
    "long_lead": """SELECT ?m WHERE { ?s cp:SupplierMaterial_is_preferred true ; cp:SupplierMaterial_lead_time_days ?lt ; cp:SupplierMaterial_material_id ?mk ;
                    cp:SupplierMaterial_material_id ?mk . ?mr cp:hasKey ?mk ; cp:Material_material_id ?m . FILTER(?lt >= ?n) } ORDER BY ?m""",
}


def key(kind, v):
    return URIRef(ID + kind + "/" + v)


class SparqlProvider:
    name = "sparql"

    def __init__(self, ents, params, graph: Graph | None = None, naive: bool = False):
        self.g = graph if graph is not None else build_graph(ents, "q")
        self.p, self.naive, self._used = params, naive, None
        self.prepared = {k: PREFIX + v for k, v in SPARQL.items()}

    def q(self, name, **b):
        return list(self.g.query(self.prepared[name], initBindings=b))

    def unit(self, code):
        (d, f), = self.q("unit", k=key("Unit", code))
        return str(d), dd(f)

    def item(self, t, i):
        (b, s), = self.q("item_m" if t == "MATERIAL" else "item_p", k=key("Material" if t == "MATERIAL" else "Product", i))
        return str(b).rsplit("/", 1)[1], dd(s)

    def item_ids(self):
        return [str(r[0]) for r in self.q("ids")], [str(r[0]) for r in self.q("ids_m")]

    def inventory(self, t, i):
        rows = self.q("inventory", k=key("Material" if t == "MATERIAL" else "Product", i), t=Literal(t))
        if not rows:
            return None
        oh, al, oo, rd, u = rows[0]
        return {"on_hand_qty": str(oh), "allocated_qty": None if al is None else str(al), "on_order_qty": None if oo is None else str(oo),
                "expected_receipt_date": None if rd is None else str(rd), "unit": str(u).rsplit("/", 1)[1]}

    def open_orders(self, h0, h1):
        return [(str(p).rsplit("/", 1)[1], dd(q), str(u).rsplit("/", 1)[1])
                for p, q, u in self.q("orders", h0=Literal(h0, datatype=XSD.date), h1=Literal(h1, datatype=XSD.date))]

    def bom_candidates(self, product, day, qty):
        return [str(r[0]) for r in self.q("candidates", p=key("Product", product), d=Literal(day, datatype=XSD.date), q=Literal(str(qty), datatype=XSD.decimal))]

    def bom_lines(self, bom_id):
        (bq,), = self.q("base_qty", k=key("BOM", bom_id))
        return dd(bq), [(int(n), str(t), str(c).rsplit("/", 1)[1], dd(q), str(u).rsplit("/", 1)[1], dd(s) if s is not None else ZERO)
                        for n, t, c, q, u, s in self.q("lines", k=key("BOM", bom_id))]

    def structure_edges(self):
        return [(str(p).rsplit("/", 1)[1], str(c).rsplit("/", 1)[1]) for p, c in self.q("edges")]

    def used_by(self):
        if self._used is None:
            self._used = Graph()
            for t in self.g.query(self.prepared["used_by"]):
                self._used.add(t)
        return self._used

    def ancestors_finished(self, t, i):
        start = key("Material" if t == "MATERIAL" else "Product", i)
        if self.naive:
            rows = self.q("ancestors_naive", start=start)
        else:
            rows = list(self.used_by().query(self.prepared["ancestors"], initBindings={"start": start}))
        return [str(r[0]).rsplit("/", 1)[1] for r in rows]

    def long_lead_materials(self, n):
        return [str(r[0]) for r in self.q("long_lead", n=Literal(n))]


# ------------------------------------------------------------------ 공통 계산 (decision_logic §1~§3)
def mrp(P, params) -> dict:
    h0, h1 = params["horizon_start"], params["horizon_end"]
    units = {}

    def to_base(qty, unit, t, i):
        base, _ = P.item(t, i)
        for u in (unit, base):
            if u not in units:
                units[u] = P.unit(u)
        if units[unit][0] != units[base][0]:
            raise ValueError(f"ERR-UNIT {i}")
        return qty * units[unit][1] / units[base][1]

    def available(t, i):
        r = P.inventory(t, i)
        if r is None:
            return ZERO
        oh, al, so = (to_base(dd(r[k] or 0), r["unit"], t, i) for k in ("on_hand_qty", "allocated_qty", "on_order_qty"))
        if so and not (r["expected_receipt_date"] <= h1):
            so = ZERO
        return oh - al + so

    products, materials = P.item_ids()
    level = {p: 0 for p in products}
    edges = P.structure_edges()
    for _ in range(60):
        changed = False
        for parent, child in edges:
            if level[child] < level[parent] + 1:
                level[child], changed = level[parent] + 1, True
        if not changed:
            break
    else:
        raise ValueError("ERR-BOMCYCLE")
    indep, dep, gross_m = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    for p, q, u in P.open_orders(h0, h1):
        indep[p] += to_base(q, u, "PRODUCT", p)
    for lv in sorted(set(level.values())):
        for p in sorted(x for x in level if level[x] == lv):
            ss = P.item("PRODUCT", p)[1] if params["include_safety_stock"] else ZERO
            net = max(ZERO, indep[p] + dep[p] + ss - available("PRODUCT", p))
            if net <= 0:
                continue
            cands = P.bom_candidates(p, h0, net)
            if len(cands) != 1:
                raise ValueError(f"ERR-BOMVER {p} {cands}")
            base_qty, lines = P.bom_lines(cands[0])
            for _, ctype, cid, qty_per, unit, scrap in lines:
                t = "MATERIAL" if ctype == "MATERIAL" else "PRODUCT"
                qty = net * to_base(qty_per, unit, t, cid) * (1 + scrap) / base_qty
                (gross_m if t == "MATERIAL" else dep)[cid] += qty
    shortage = {}
    for m in materials:
        ss = P.item("MATERIAL", m)[1] if params["include_material_safety_stock"] else ZERO
        s = max(ZERO, gross_m.get(m, ZERO) + ss - available("MATERIAL", m))
        if s > 0:
            shortage[m] = s
    return {"gross": dict(gross_m), "shortage": shortage}


def run_all(P, params) -> dict:
    cq = params["cq"]
    q1 = []
    for c in cq["CQ-04"]["cases"]:
        cand = P.bom_candidates(c["product_id"], c["date"], dd(c["qty"]))
        status = "SELECTED" if len(cand) == 1 else ("NONE" if not cand else "AMBIGUOUS")
        lines = [(n, cid, q, u) for n, _, cid, q, u, _ in P.bom_lines(cand[0])[1]] if status == "SELECTED" else []
        q1.append({"candidates": cand, "status": status, "lines": lines})
    q2 = {m: P.ancestors_finished("MATERIAL", m) for m in cq["CQ-05"]["material_ids"]}
    r = mrp(P, params)
    n = cq["CQ-10"]["min_lead_time_days"]
    long_m = P.long_lead_materials(n)
    by_prod = defaultdict(list)
    for m in long_m:
        for p in P.ancestors_finished("MATERIAL", m):
            by_prod[p].append(m)
    return {"Q1": q1, "Q2": q2, "Q3": r["gross"], "Q4": r["shortage"], "Q5": {"materials": long_m, "products": dict(sorted(by_prod.items()))}}


def items(qid, ans) -> set:
    """비교 단위(항목) 집합. 수량은 Decimal 정규화."""
    n = lambda x: Decimal(str(x)).normalize()
    if qid == "Q1":
        out = set()
        for i, c in enumerate(ans):
            out.add((i, "status", c["status"], tuple(c["candidates"])))
            out |= {(i, "line", int(l[0]), l[1], n(l[2]), l[3]) for l in c["lines"]}
        return out
    if qid == "Q2":
        return {(m, p) for m, ps in ans.items() for p in ps}
    if qid in ("Q3", "Q4"):
        return {(m, n(v)) for m, v in ans.items()}
    return {("material", m) for m in ans["materials"]} | {(p, m) for p, ms in ans["products"].items() for m in ms}


def expected(gt) -> dict:
    e = gt["expected"]["cq"]
    q1 = [{"candidates": c["candidates"], "status": c["status"], "lines": [(l["line_no"], l["component_id"], l["qty_per"], l["unit"]) for l in c["lines"]]}
          for c in e["CQ-04"]]
    return {"Q1": q1, "Q2": e["CQ-05"], "Q3": e["CQ-06"], "Q4": e["CQ-08"], "Q5": {"materials": e["CQ-10"]["materials"], "products": e["CQ-10"]["products"]}}


def score(got, exp) -> dict:
    out = {}
    for q in ("Q1", "Q2", "Q3", "Q4", "Q5"):
        a, b = items(q, got[q]), items(q, exp[q])
        out[q] = {"expected_items": len(b), "correct": len(a & b), "missing": sorted(map(str, b - a)), "wrong": sorted(map(str, a - b)), "exact": a == b}
    return out


def chain_entities(depth: int) -> dict:
    """관계 단계 증가 측정용 합성 BOM 사슬: P0(완제품) → P1 → … → P{depth-1} → 자재 MX. 정답: MX의 상위 완제품 = {P0}."""
    uid = lambda *p: D.new_uid("chain", str(depth), *p)
    E = {e: [] for e in D.ENTITY_ORDER}
    E["Unit"].append({"record_uid": uid("u"), "origin_class": "SYNTHETIC", "unit_code": "EA", "dimension": "COUNT", "base_unit_code": "EA", "to_base_factor": "1"})
    E["Material"].append({"record_uid": uid("m"), "origin_class": "SYNTHETIC", "material_id": "MX", "material_name": "합성 자재", "base_unit": "EA",
                          "unit_cost": "1", "safety_stock_qty": "0"})
    for i in range(depth):
        E["Product"].append({"record_uid": uid("p", str(i)), "origin_class": "SYNTHETIC", "product_id": f"P{i}", "product_name": f"합성 {i}",
                             "product_type": "FINISHED" if i == 0 else "SEMI_FINISHED", "base_unit": "EA", "safety_stock_qty": "0",
                             "manuf_lead_time_days": 0, "outsourcing_allowed": False, "outsourcing_unit_cost": None})
        E["BOM"].append({"record_uid": uid("b", str(i)), "origin_class": "SYNTHETIC", "bom_id": f"B{i}", "product_id": f"P{i}", "bom_version": "V1",
                         "status": "APPROVED", "is_active": True, "valid_from": "2026-01-01", "valid_to": None, "min_qty": "0", "max_qty": None,
                         "site_id": None, "base_qty": "1"})
        last = i == depth - 1
        E["BOMLine"].append({"record_uid": uid("l", str(i)), "origin_class": "SYNTHETIC", "bom_id": f"B{i}", "line_no": 1,
                             "component_type": "MATERIAL" if last else "PRODUCT", "component_material_id": "MX" if last else None,
                             "component_product_id": None if last else f"P{i + 1}", "qty_per": "1", "unit": "EA", "scrap_rate": None, "line_type": "ITEM"})
    return E
