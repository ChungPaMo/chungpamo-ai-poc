"""E06 SHACL shape 생성기 → ontology/e06_shapes.ttl (기본), ontology/e06_shapes_core_compare.ttl (비교 제약을 Core로 쓴 변형)

    .\\.venv\\Scripts\\python.exe scripts\\e06_shapes.py

- 구조 규칙(S01~S07)·참조 규칙(R01~R07)은 E01 모델 정의(FK = e05_validate_sql.field_kinds)에서 생성한다 (E05 SQL 생성 질의와 같은 출처).
- 관계·업무 규칙은 SHACL Core 논리 제약(sh:or·sh:not·sh:in·경로) 또는 SHACL-SPARQL 제약(sh:sparql)으로 직접 작성한다.
- SPARQL 질의는 바인딩된 변수부터 조회한다. 속성 IRI가 엔터티별(cp:{엔터티}_{필드})이므로 다른 레코드의 rdf:type 패턴은 넣지 않는다
  (1차 작성본은 타입 패턴을 넣어 규모 증가 시 시간이 비선형으로 늘었음 — 보고서 §8).
- 모든 shape는 IRI를 가지며 cp:ruleId(E05 규칙 ID)·cp:fieldName(보고 필드)·cp:engine(CORE/SPARQL)을 단다 → 검증 결과를 E05 규칙에 명시적으로 대응.
- V13(생산능력)은 계산 규칙이라 shape를 만들지 않는다 (docs/e06_shacl_rule_mapping.md 분류 4).
- compare="sparql"(기본): 두 속성 비교(V02·V07·B05)를 SPARQL FILTER로. compare="core": sh:lessThan·sh:lessThanOrEquals로
  (pyshacl 0.40.1은 비교 대상에 형식이 틀린 리터럴이 있으면 TypeError로 검증 전체가 중단됨 — 측정용 변형).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import e05_dataset as D
from e05_validate_sql import FK, FK_RULE
from e06_build_rdf import BASE, COND_REFS, CP, ID, REFS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ontology" / "e06_shapes.ttl"
OUT_CORE = ROOT / "ontology" / "e06_shapes_core_compare.ttl"
SH = BASE + "shape/"
RULES = {r["rule_id"]: r for r in json.loads((ROOT / "configs" / "e05_validation_rules.json").read_text(encoding="utf-8"))["rules"]}
XSD_T = {"decimal": "xsd:decimal", "int": "xsd:integer", "bool": "xsd:boolean", "date": "xsd:date"}
REF_RULE = {**FK_RULE, ("Unit", "base_unit_code"): "R07"}


def lit(v, kind):
    return f'"{v}"^^{XSD_T[kind]}' if kind in XSD_T else f'"{v}"'


class Shapes:
    def __init__(self):
        self.blocks, self.count = [], {}

    def iri(self, rule, ent, field, tag):
        return f"<{SH}{rule}/{ent}/{field}/{tag}>"

    def meta(self, rule, field, engine):
        sev = {"ERROR": "sh:Violation", "WARNING": "sh:Warning"}[RULES[rule]["severity"]]
        self.count[(rule, engine)] = self.count.get((rule, engine), 0) + 1
        return f'sh:severity {sev} ; cp:ruleId "{rule}" ; cp:fieldName "{field}" ; cp:engine "{engine}"'

    def prop(self, rule, ent, field, tag, body, path=None, raw_path=None):
        self.blocks.append(f"{self.iri(rule, ent, field, tag)} a sh:PropertyShape ; sh:targetClass cp:{ent}Record ; sh:path {raw_path or 'cp:' + ent + '_' + (path or field)} ;\n"
                           f"    {body} ;\n    {self.meta(rule, field, 'CORE')} .")

    def node(self, rule, ent, field, tag, body):
        self.blocks.append(f"{self.iri(rule, ent, field, tag)} a sh:NodeShape ; sh:targetClass cp:{ent}Record ;\n    {body} ;\n"
                           f"    {self.meta(rule, field, 'CORE')} .")

    def sparql(self, rule, ent, field, tag, select):
        self.blocks.append(f"{self.iri(rule, ent, field, tag)} a sh:NodeShape ; sh:targetClass cp:{ent}Record ;\n"
                           f"    sh:sparql [ a sh:SPARQLConstraint ; sh:prefixes <{SH}prefixes> ; sh:message \"{RULES[rule]['description'].replace(chr(34), '')}\" ;\n"
                           f'        sh:select """{select.strip()}""" ] ;\n    {self.meta(rule, field, "SPARQL")} .')


def p(ent, field):
    return f"cp:{ent}_{field}"


def bom_candidate(b, prod, d, q):
    """schema §3.6 BOM 버전 선택 조건 (site_id = null 데이터셋: 사이트가 비어 있는 버전만 후보)."""
    return f"""{b} cp:BOM_product_id {prod} ; cp:BOM_status "APPROVED" ; cp:BOM_is_active true ;
              cp:BOM_valid_from ?vf{b[1:]} ; cp:BOM_min_qty ?mn{b[1:]} .
        OPTIONAL {{ {b} cp:BOM_valid_to ?vt{b[1:]} }} OPTIONAL {{ {b} cp:BOM_max_qty ?mx{b[1:]} }} OPTIONAL {{ {b} cp:BOM_site_id ?st{b[1:]} }}
        FILTER(?vf{b[1:]} <= {d} && (!BOUND(?vt{b[1:]}) || {d} <= ?vt{b[1:]}) && ?mn{b[1:]} <= {q} && (!BOUND(?mx{b[1:]}) || {q} < ?mx{b[1:]}) && !BOUND(?st{b[1:]}))"""


def shapes_ttl(params: dict, compare: str = "sparql") -> tuple[str, dict]:
    S = Shapes()
    # ---- 구조·참조 (모델 정의에서 생성) ----
    for ent in D.ENTITY_ORDER:
        for field, d in FK[ent].items():
            if d["required"]:
                S.prop("S01", ent, field, "minCount", "sh:minCount 1")
                S.prop("S01", ent, field, "blank", "sh:minLength 1")
            else:
                S.prop("S07", ent, field, "blank", "sh:minLength 1")
            ref = (ent, field) in REFS or (ent, field) in COND_REFS
            if not ref and d["kind"] in ("decimal", "int", "bool"):
                S.prop("S02", ent, field, "datatype", f"sh:datatype {XSD_T[d['kind']]}")
            if d["kind"] == "date":
                S.prop("S03", ent, field, "datatype", "sh:datatype xsd:date")
            if d["kind"] == "enum":
                S.prop("S04", ent, field, "in", "sh:in ( " + " ".join(f'"{v}"' for v in d["enum"]) + " )")
            for k, v in d["cons"].items():
                rule = "V01" if (ent, field) == ("Inventory", "on_hand_qty") else "S06"
                facet = {"gt": "sh:minExclusive", "ge": "sh:minInclusive", "lt": "sh:maxExclusive", "le": "sh:maxInclusive"}[k]
                S.prop(rule, ent, field, k, f"{facet} {lit(v, d['kind'])}")
            if (ent, field) in REFS:
                tgt, rule = REFS[(ent, field)], REF_RULE[(ent, field)]
                if ent == "BOMLine" and field in ("component_material_id", "component_product_id"):
                    want = "MATERIAL" if field == "component_material_id" else "PRODUCT"
                    S.node(rule, ent, field, "class", f'sh:or ( [ sh:not [ sh:path {p(ent, "component_type")} ; sh:hasValue "{want}" ] ] '
                                                      f"[ sh:path {p(ent, field)} ; sh:class cp:{tgt} ] )")
                else:
                    S.prop(rule, ent, field, "class", f"sh:class cp:{tgt}")
        S.prop("S05", ent, "record_uid", "pattern", 'sh:pattern "^rec_[0-9a-f]{16}$"')
    for typ, tgt, rule in (("PRODUCT", "Product", "R01"), ("MATERIAL", "Material", "R02")):
        S.node(rule, "Inventory", "item_id", f"class_{typ.lower()}", f'sh:or ( [ sh:not [ sh:path cp:Inventory_item_type ; sh:hasValue "{typ}" ] ] '
                                                                    f"[ sh:path cp:Inventory_item_id ; sh:class cp:{tgt} ] )")
    # ---- 업무 키 중복 ----
    for ent in D.ENTITY_ORDER:
        rule = "V04" if ent == "Inventory" else "S08"
        S.sparql(rule, ent, "*", "dup", f"""SELECT $this ?value WHERE {{ $this cp:hasKey ?k . ?o cp:hasKey ?k . FILTER(?o != $this) BIND(STR(?k) AS ?value) }}""")
    # ---- BOM·관계 ----
    S.sparql("B01", "BOMLine", "component_product_id", "cycle", """
SELECT $this ?value WHERE {
  $this cp:BOMLine_component_type "PRODUCT" ; cp:BOMLine_bom_id ?b ; cp:BOMLine_component_product_id ?v .
  ?bom cp:hasKey ?b ; cp:BOM_product_id ?u .
  FILTER(?u = ?v || EXISTS { ?v (^cp:BOM_product_id/cp:hasKey/^cp:BOMLine_bom_id/cp:BOMLine_component_product_id)+ ?u })
  BIND(STR(?v) AS ?value) }""")
    S.sparql("B02", "BOM", "*", "overlap", """
SELECT $this ?value WHERE {
  $this cp:BOM_status "APPROVED" ; cp:BOM_is_active true ; cp:BOM_product_id ?p ; cp:BOM_valid_from ?xf ; cp:BOM_min_qty ?xn .
  ?y cp:BOM_product_id ?p ; cp:BOM_status "APPROVED" ; cp:BOM_is_active true ; cp:BOM_valid_from ?yf ; cp:BOM_min_qty ?yn .
  FILTER(?y != $this)
  OPTIONAL { $this cp:BOM_valid_to ?xt } OPTIONAL { ?y cp:BOM_valid_to ?yt } OPTIONAL { $this cp:BOM_max_qty ?xm } OPTIONAL { ?y cp:BOM_max_qty ?ym }
  OPTIONAL { $this cp:BOM_site_id ?xs } OPTIONAL { ?y cp:BOM_site_id ?ys }
  FILTER((!BOUND(?yt) || ?xf <= ?yt) && (!BOUND(?xt) || ?yf <= ?xt) && (!BOUND(?ym) || ?xn < ?ym) && (!BOUND(?xm) || ?yn < ?xm)
         && (!BOUND(?xs) || !BOUND(?ys) || ?xs = ?ys))
  BIND(STR(?y) AS ?value) }""")
    S.sparql("B03", "BOM", "status", "active_draft", """
SELECT $this ?value WHERE { $this cp:BOM_is_active true ; cp:BOM_status ?value . FILTER(STR(?value) != "APPROVED" && STR(?value) != "") }""")
    S.sparql("B04", "BOM", "*", "version_dup", """
SELECT $this ?value WHERE { $this cp:BOM_product_id ?p ; cp:BOM_bom_version ?value . FILTER(STR(?value) != "")
  ?o cp:BOM_product_id ?p ; cp:BOM_bom_version ?value . FILTER(?o != $this) }""")
    if compare == "core":
        S.prop("B05", "BOM", "valid_to", "order", "sh:lessThanOrEquals cp:BOM_valid_to", path="valid_from")
        S.prop("B05", "BOM", "max_qty", "order", "sh:lessThan cp:BOM_max_qty", path="min_qty")
    else:
        S.sparql("B05", "BOM", "valid_to", "order", "SELECT $this ?value WHERE { $this cp:BOM_valid_from ?f ; cp:BOM_valid_to ?value . FILTER(?value < ?f) }")
        S.sparql("B05", "BOM", "max_qty", "order", "SELECT $this ?value WHERE { $this cp:BOM_min_qty ?n ; cp:BOM_max_qty ?value . FILTER(?value <= ?n) }")
    pl = "cp:ProductionPlanLine_"
    head = f"""$this {pl}production_mode "INHOUSE" ; {pl}period_start ?d ; {pl}planned_qty ?q ; {pl}product_id ?p .
  FILTER(?d >= "0001-01-01"^^xsd:date && ?q >= 0)"""      # 날짜·수량을 해석할 수 없는 라인은 건너뜀 (E05와 같음)
    S.sparql("B06", "ProductionPlanLine", "product_id", "none", f"""
SELECT $this ?value WHERE {{ {head}
  FILTER NOT EXISTS {{ {bom_candidate("?b", "?p", "?d", "?q")} }}
  BIND(STR(?p) AS ?value) }}""")
    S.sparql("B06", "ProductionPlanLine", "product_id", "ambiguous", f"""
SELECT $this ?value WHERE {{ {head}
  {bom_candidate("?b", "?p", "?d", "?q")}
  {bom_candidate("?c", "?p", "?d", "?q")}
  FILTER(?b != ?c) BIND(STR(?p) AS ?value) }}""")
    bl = "cp:BOMLine_"
    S.node("B07", "BOMLine", "component_type", "consistency",
           f'sh:or ( [ sh:not [ sh:path {bl}component_type ; sh:in ( "MATERIAL" "PRODUCT" ) ; sh:minCount 1 ] ]\n'
           f'      [ sh:and ( [ sh:path {bl}component_type ; sh:hasValue "MATERIAL" ] [ sh:path {bl}component_material_id ; sh:minCount 1 ] [ sh:path {bl}component_product_id ; sh:maxCount 0 ] ) ]\n'
           f'      [ sh:and ( [ sh:path {bl}component_type ; sh:hasValue "PRODUCT" ] [ sh:path {bl}component_product_id ; sh:minCount 1 ] [ sh:path {bl}component_material_id ; sh:maxCount 0 ] ) ] )')
    dim = """$this {u} ?u . ?ur cp:hasKey ?u ; cp:Unit_dimension ?du .
  ?br cp:hasKey ?bu ; cp:Unit_dimension ?db . FILTER(STR(?du) != STR(?db)) BIND(STR(?u) AS ?value)"""
    S.sparql("B08", "BOMLine", "unit", "dimension", f"""
SELECT $this ?value WHERE {{
  {{ $this {bl}component_type "MATERIAL" ; {bl}component_material_id ?i . ?ir cp:hasKey ?i ; cp:Material_base_unit ?bu }}
  UNION {{ $this {bl}component_type ?t . FILTER(STR(?t) != "MATERIAL") $this {bl}component_product_id ?i . ?ir cp:hasKey ?i ; cp:Product_base_unit ?bu }}
  {dim.format(u=bl + "unit")} }}""")
    S.sparql("B08", "Order", "unit", "dimension", f"""
SELECT $this ?value WHERE {{ $this cp:Order_product_id ?i . ?ir cp:hasKey ?i ; cp:Product_base_unit ?bu .
  {dim.format(u="cp:Order_unit")} }}""")
    S.sparql("B08", "Inventory", "unit", "dimension", f"""
SELECT $this ?value WHERE {{ $this cp:Inventory_item_id ?i . ?ir cp:hasKey ?i ; (cp:Material_base_unit|cp:Product_base_unit) ?bu .
  {dim.format(u="cp:Inventory_unit")} }}""")
    S.sparql("B08", "ProductionPlanLine", "unit", "dimension", f"""
SELECT $this ?value WHERE {{ $this {pl}product_id ?i . ?ir cp:hasKey ?i ; cp:Product_base_unit ?bu .
  {dim.format(u=pl + "unit")} }}""")
    S.prop("B09", "BOM", "*", "has_line", "sh:minCount 1", raw_path="( cp:hasKey [ sh:inversePath cp:BOMLine_bom_id ] )")
    S.sparql("B10", "BOMLine", "*", "same_component", f"""
SELECT $this ?value WHERE {{ $this {bl}bom_id ?b . {{ $this {bl}component_material_id ?c }} UNION {{ $this {bl}component_product_id ?c }}
  ?o {bl}bom_id ?b . {{ ?o {bl}component_material_id ?c }} UNION {{ ?o {bl}component_product_id ?c }}
  FILTER(?o != $this) BIND(STR(?c) AS ?value) }}""")
    sm = "cp:SupplierMaterial_"
    S.sparql("B11", "SupplierMaterial", "is_preferred", "none", f"""
SELECT $this ?value WHERE {{ $this {sm}material_id ?m .
  FILTER NOT EXISTS {{ ?s {sm}material_id ?m ; {sm}is_preferred true }} BIND(STR(?m) AS ?value) }}""")
    S.sparql("B11", "SupplierMaterial", "is_preferred", "multiple", f"""
SELECT $this ?value WHERE {{ $this {sm}material_id ?m . ?a {sm}material_id ?m ; {sm}is_preferred true . BIND(STR(?m) AS ?value) }}
GROUP BY $this ?value HAVING (COUNT(DISTINCT ?a) > 1)""")
    sh_ = "cp:SalesHistory_"
    S.sparql("B12", "SalesHistory", "allocation_share", "sum", f"""
SELECT $this ?value WHERE {{ $this {sh_}generation_method "ALLOCATED" ; {sh_}derived_from_record_uid ?src ; {sh_}allocation_share ?value .
  ?r {sh_}derived_from_record_uid ?src ; {sh_}allocation_share ?s ; {sh_}generation_method "ALLOCATED" }}
GROUP BY $this ?value HAVING (ABS(SUM(?s) - 1) > 0.0005)""")
    for field in ("derived_from_record_uid", "allocation_share"):
        S.node("B13", "SalesHistory", field, "allocated_requires",
               f'sh:or ( [ sh:not [ sh:path {sh_}generation_method ; sh:hasValue "ALLOCATED" ] ] [ sh:path {sh_}{field} ; sh:minCount 1 ] )')
    pr = "cp:Product_"
    S.node("B14", "Product", "outsourcing_unit_cost", "cost_only_if_allowed",
           f"sh:or ( [ sh:not [ sh:path {pr}outsourcing_allowed ; sh:datatype xsd:boolean ; sh:minCount 1 ] ]\n"
           f"      [ sh:and ( [ sh:path {pr}outsourcing_allowed ; sh:hasValue true ] [ sh:path {pr}outsourcing_unit_cost ; sh:minCount 1 ] ) ]\n"
           f"      [ sh:and ( [ sh:path {pr}outsourcing_allowed ; sh:hasValue false ] [ sh:path {pr}outsourcing_unit_cost ; sh:maxCount 0 ] ) ] )")
    # ---- 업무 ----
    inv = "cp:Inventory_"
    if compare == "core":
        S.prop("V02", "Inventory", "allocated_qty", "le_on_hand", f"sh:lessThanOrEquals {inv}on_hand_qty")
    else:
        S.sparql("V02", "Inventory", "allocated_qty", "le_on_hand", f"SELECT $this ?value WHERE {{ $this {inv}allocated_qty ?value ; {inv}on_hand_qty ?h . FILTER(?value > ?h) }}")
    for field in ("on_hand_qty", "allocated_qty", "on_order_qty"):
        S.sparql("V03", "Inventory", field, "ea_integer", f"SELECT $this ?value WHERE {{ $this {inv}unit <{ID}Unit/EA> ; {inv}{field} ?value . FILTER(?value != FLOOR(?value)) }}")
    S.node("V05", "Inventory", "expected_receipt_date", "receipt_required",
           f"sh:or ( [ sh:path {inv}on_order_qty ; sh:maxInclusive 0 ] [ sh:path {inv}expected_receipt_date ; sh:minCount 1 ] )")
    S.prop("V06", "Inventory", "as_of_date", "le_reference", f'sh:maxInclusive "{params["reference_date"]}"^^xsd:date')
    if compare == "core":
        S.prop("V07", "Order", "due_date", "ge_order", "sh:lessThanOrEquals cp:Order_due_date", path="order_date")
    else:
        S.sparql("V07", "Order", "due_date", "ge_order", "SELECT $this ?value WHERE { $this cp:Order_order_date ?o ; cp:Order_due_date ?value . FILTER(?value < ?o) }")
    S.sparql("V08", "Order", "product_id", "no_operation", """
SELECT $this ?value WHERE { $this cp:Order_status "OPEN" ; cp:Order_product_id ?p . FILTER NOT EXISTS { ?op cp:Operation_product_id ?p } BIND(STR(?p) AS ?value) }""")
    S.sparql("V08", "ProductionPlanLine", "product_id", "no_operation", f"""
SELECT $this ?value WHERE {{ $this {pl}production_mode "INHOUSE" ; {pl}product_id ?p . FILTER NOT EXISTS {{ ?op cp:Operation_product_id ?p }} BIND(STR(?p) AS ?value) }}""")
    S.sparql("V09", "ProductionPlanLine", "resource_id", "resource_in_routing", f"""
SELECT $this ?value WHERE {{ $this {pl}production_mode "INHOUSE" ; {pl}product_id ?p ; {pl}resource_id ?value .
  FILTER EXISTS {{ ?op cp:Operation_product_id ?p }}
  FILTER NOT EXISTS {{ ?op2 cp:Operation_product_id ?p ; cp:Operation_resource_id ?value }} }}""")
    S.sparql("V10", "ProductionPlanLine", "resource_id", "mode_resource", f"""
SELECT $this ?value WHERE {{ $this {pl}production_mode ?value . FILTER(STR(?value) = "INHOUSE" || STR(?value) = "OUTSOURCE")
  BIND(EXISTS {{ $this {pl}resource_id ?r }} AS ?hasR) FILTER((STR(?value) = "OUTSOURCE") = ?hasR) }}""")
    S.sparql("V11", "ProductionPlanLine", "production_mode", "outsource_not_allowed", f"""
SELECT $this ?value WHERE {{ $this {pl}production_mode ?value ; {pl}product_id ?p . FILTER(STR(?value) = "OUTSOURCE")
  ?pr cp:hasKey ?p ; cp:Product_outsourcing_allowed false }}""")
    S.sparql("V12", "ProductionPlanLine", "period_start", "within_horizon", f"""
SELECT $this ?value WHERE {{ $this {pl}period_start ?value ; {pl}plan_id ?pl .
  ?pr cp:hasKey ?pl ; cp:ProductionPlan_horizon_start ?hs ; cp:ProductionPlan_horizon_end ?he .
  FILTER(?value < ?hs || ?value > ?he) }}""")
    head_ttl = ["# E06 SHACL shapes (scripts/e06_shapes.py가 생성 — 직접 수정하지 말고 생성기를 고친다).",
                f"# 비교 제약 방식: {compare}. 규칙 ID는 configs/e05_validation_rules.json. V13(생산능력)은 shape 없음.",
                "@prefix sh: <http://www.w3.org/ns/shacl#> .", "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
                "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .", f"@prefix cp: <{CP}> .", "",
                f"<{SH}prefixes> sh:declare [ sh:prefix \"cp\" ; sh:namespace \"{CP}\"^^xsd:anyURI ] ,",
                "    [ sh:prefix \"xsd\" ; sh:namespace \"http://www.w3.org/2001/XMLSchema#\"^^xsd:anyURI ] ,",
                "    [ sh:prefix \"rdf\" ; sh:namespace \"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"^^xsd:anyURI ] .", ""]
    return "\n".join(head_ttl + [b + "\n" for b in S.blocks]), S.count


def main() -> int:
    from rdflib import Graph
    params = D.load_gt()["parameters"]
    for path, mode in ((OUT, "sparql"), (OUT_CORE, "core")):
        ttl, count = shapes_ttl(params, mode)
        Graph().parse(data=ttl, format="turtle")
        path.write_text(ttl, encoding="utf-8", newline="\n")
        rules = sorted({r for r, _ in count})
        print(path.name, {"shapes": sum(count.values()), "rules": len(rules),
                          "core_shapes": sum(v for (r, e), v in count.items() if e == "CORE"), "sparql_shapes": sum(v for (r, e), v in count.items() if e == "SPARQL")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
