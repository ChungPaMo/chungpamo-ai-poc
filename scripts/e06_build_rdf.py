"""E06 RDF 변환기: E01 정규 엔터티 레코드(dict) → RDF 그래프 (rdflib). 온톨로지 TTL 생성과 왕복(의미 보존) 확인 포함.

    .\\.venv\\Scripts\\python.exe scripts\\e06_build_rdf.py          # ontology/e06_minimal.ttl 생성 + 정상 데이터 변환·왕복 확인

매핑 원칙 (docs/e06_rdf_mapping.md)
- 레코드 노드  rec/{record_uid}           : 원본 레코드 1건 = 노드 1개 (중복 업무 ID도 레코드별로 따로 남김)
- 업무 키 노드 id/{엔터티}/{키 값…}         : 같은 업무 키를 가진 레코드는 같은 키 노드를 가리킴 (cp:hasKey)
- 마스터 레코드(Unit·Product·Material·Supplier·BOM·Resource·ProductionPlan)가 있을 때만 키 노드에 rdf:type을 붙인다.
  참조만 있고 마스터 레코드가 없으면 키 노드는 타입 없이 남는다 (실체를 만들지 않음 → SHACL sh:class로 누락 검출)
- 속성 IRI cp:{엔터티}_{필드}. 값은 모델의 선언 타입 리터럴(xsd:decimal·integer·boolean·date, 문자열은 일반 리터럴)로 그대로 옮긴다.
  변환기는 값이 맞는지 판정하지 않는다. rdflib가 형식이 틀린 리터럴로 표시한 경우(ill_typed)는 '변환 기록'으로 따로 남긴다.
- null(None)은 트리플을 만들지 않는다. 빈 문자열은 그대로 리터럴 ""로 남긴다. 참조 값이 문자열이 아니거나 비어 있으면 IRI 대신 리터럴로 남긴다.
- 계보: 레코드 → cp:inDataset → 데이터셋 노드(데이터셋 해시, 정답셋 v2 해시, 변환기). OWL 추론 없음.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from urllib.parse import quote, unquote

from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

import e05_dataset as D
from e05_validate_sql import FK

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://example.org/chungpamo/e06/"
CP = Namespace(BASE + "ns#")
REC = BASE + "rec/"
ID = BASE + "id/"
ONTOLOGY = ROOT / "ontology" / "e06_minimal.ttl"
BUILDER_VERSION = "e06_build_rdf v1"

KEYS = {"Unit": [("Unit", ("unit_code",))], "Product": [("Product", ("product_id",))], "Material": [("Material", ("material_id",))],
        "Supplier": [("Supplier", ("supplier_id",))], "SupplierMaterial": [("SupplierMaterial", ("supplier_id", "material_id"))],
        "BOM": [("BOM", ("bom_id",))], "BOMLine": [("BOMLine", ("bom_id", "line_no"))], "Order": [("Order", ("order_id",))],
        "SalesHistory": [("SalesHistory", ("product_id", "period_start", "period_grain"))],
        "Inventory": [("Inventory", ("item_type", "item_id", "as_of_date"))], "Resource": [("Resource", ("resource_id",))],
        "Operation": [("Operation", ("operation_id",)), ("OperationSeq", ("product_id", "sequence_no"))],
        "ProductionPlan": [("ProductionPlan", ("plan_id",))], "ProductionPlanLine": [("ProductionPlanLine", ("plan_id", "line_no"))]}
MASTER = {"Unit", "Product", "Material", "Supplier", "BOM", "Resource", "ProductionPlan"}
REFS = {("Unit", "base_unit_code"): "Unit", ("Product", "base_unit"): "Unit", ("Material", "base_unit"): "Unit",
        ("SupplierMaterial", "supplier_id"): "Supplier", ("SupplierMaterial", "material_id"): "Material", ("BOM", "product_id"): "Product",
        ("BOMLine", "bom_id"): "BOM", ("BOMLine", "component_material_id"): "Material", ("BOMLine", "component_product_id"): "Product",
        ("BOMLine", "unit"): "Unit", ("Order", "product_id"): "Product", ("Order", "unit"): "Unit", ("SalesHistory", "product_id"): "Product",
        ("Inventory", "unit"): "Unit", ("Operation", "product_id"): "Product", ("Operation", "resource_id"): "Resource",
        ("ProductionPlanLine", "plan_id"): "ProductionPlan", ("ProductionPlanLine", "product_id"): "Product",
        ("ProductionPlanLine", "resource_id"): "Resource", ("ProductionPlanLine", "unit"): "Unit"}
# Inventory.item_id는 item_type 값에 따라 대상이 정해지는 조건부 참조 (PRODUCT → Product, MATERIAL → Material)
COND_REFS = {("Inventory", "item_id"): ("item_type", {"PRODUCT": "Product", "MATERIAL": "Material"})}
XSD_OF = {"decimal": XSD.decimal, "int": XSD.integer, "bool": XSD.boolean, "date": XSD.date}


def prop(ent: str, field: str) -> URIRef:
    return CP[f"{ent}_{field}"]


def key_iri(kind: str, parts) -> URIRef:
    return URIRef(ID + kind + "/" + "/".join(quote(str(p), safe="") for p in parts))


def rec_iri(uid, ent: str, i: int) -> URIRef:
    return URIRef(REC + quote(uid, safe="")) if isinstance(uid, str) and uid else URIRef(REC + f"_missing/{ent}/{i}")


def lexical(v) -> str:
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


def ref_target(ent, field, rec):
    if (ent, field) in REFS:
        return REFS[(ent, field)]
    if (ent, field) in COND_REFS:
        typ_field, table = COND_REFS[(ent, field)]
        return table.get(rec.get(typ_field))
    return None


def build_graph(ents: dict, dataset_id: str, notes: list | None = None, dataset_sha: str | None = None) -> Graph:
    """엔터티 dict → 데이터 그래프. notes에 변환 기록(형식이 틀린 리터럴, IRI로 만들 수 없는 참조 값)을 추가한다."""
    g = Graph()
    ds = URIRef(BASE + "dataset/" + quote(dataset_id, safe=""))
    g.add((ds, RDF.type, CP.Dataset))
    g.add((ds, CP.datasetId, Literal(dataset_id)))
    g.add((ds, CP.groundTruthSha256, Literal(D.GT_SHA256)))
    if dataset_sha:
        g.add((ds, CP.datasetSha256, Literal(dataset_sha)))
    g.add((ds, CP.builtBy, Literal(BUILDER_VERSION)))
    for ent in D.ENTITY_ORDER:
        cls = CP[f"{ent}Record"]
        kinds = FK[ent]
        for i, rec in enumerate(ents.get(ent, [])):
            r = rec_iri(rec.get("record_uid"), ent, i)
            g.add((r, RDF.type, cls))
            g.add((r, CP.inDataset, ds))
            for field, v in rec.items():
                if v is None:
                    continue
                p = prop(ent, field)
                tgt = ref_target(ent, field, rec)
                if (ent, field) in REFS or (ent, field) in COND_REFS:
                    if tgt and isinstance(v, str) and v != "":
                        g.add((r, p, key_iri(tgt, [v])))
                    else:
                        g.add((r, p, Literal(lexical(v))))
                        if notes is not None:
                            notes.append({"kind": "ref_not_iri", "entity": ent, "record_uid": rec.get("record_uid"), "field": field, "value": lexical(v)})
                    continue
                kind = kinds.get(field, {}).get("kind", "text")
                if kind in XSD_OF:
                    lit = Literal(lexical(v), datatype=XSD_OF[kind])
                    if notes is not None and lit.ill_typed:
                        notes.append({"kind": "ill_typed_literal", "entity": ent, "record_uid": rec.get("record_uid"), "field": field, "value": lexical(v)})
                else:
                    lit = Literal(lexical(v))
                g.add((r, p, lit))
            for kind_name, fields in KEYS[ent]:
                parts = [rec.get(f) for f in fields]
                if all(x not in (None, "") for x in parts):
                    k = key_iri(kind_name, [lexical(x) for x in parts])
                    g.add((r, CP.hasKey, k))
                    if ent in MASTER and kind_name == ent:
                        g.add((k, RDF.type, CP[ent]))
    return g


def canonical_nt(g: Graph) -> str:
    lines = [l for l in g.serialize(format="nt").splitlines() if l.strip()]
    return "\n".join(sorted(lines)) + "\n"


def graph_sha256(g: Graph) -> str:
    return hashlib.sha256(canonical_nt(g).encode("utf-8")).hexdigest()


def round_trip(g: Graph, ents: dict) -> dict:
    """그래프에서 레코드를 다시 읽어 원본 dict와 값(어휘형)을 비교 — 변환이 의미를 바꾸지 않았는지 확인."""
    back = {}
    for ent in D.ENTITY_ORDER:
        for r in g.subjects(RDF.type, CP[f"{ent}Record"]):
            vals = {}
            for p, o in g.predicate_objects(r):
                name = str(p)[len(str(CP)):]
                if not name.startswith(ent + "_"):
                    continue
                f = name[len(ent) + 1:]
                vals[f] = unquote(str(o).rsplit("/", 1)[1]) if isinstance(o, URIRef) else str(o)
            back[(ent, str(r))] = vals
    mism, n = [], 0
    for ent in D.ENTITY_ORDER:
        for i, rec in enumerate(ents.get(ent, [])):
            n += 1
            got = back.get((ent, str(rec_iri(rec.get("record_uid"), ent, i))), {})
            want = {f: lexical(v) for f, v in rec.items() if v is not None}
            if got != want:
                mism.append({"entity": ent, "record_uid": rec.get("record_uid"), "missing": sorted(set(want) - set(got)),
                             "extra": sorted(set(got) - set(want)), "changed": sorted(f for f in want if f in got and got[f] != want[f])})
    dup_iri = sum(len(v) for v in ents.values()) - len(back)
    return {"records": n, "record_nodes": len(back), "record_iri_collisions": dup_iri, "mismatches": mism}


def ontology_ttl() -> str:
    """최소 어휘(클래스·속성·범위). 문서화용이며 검증·추론에 쓰지 않는다 (OWL 추론 미사용)."""
    L = ["# E06 최소 온톨로지 (scripts/e06_build_rdf.py가 E01 모델 정의에서 생성). OWL 추론에 쓰지 않음 — 어휘 문서화용.",
         "@prefix cp: <" + str(CP) + "> .", "@prefix owl: <http://www.w3.org/2002/07/owl#> .", "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
         "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", "",
         f"<{BASE}ns> a owl:Ontology ; rdfs:label \"충파모 E06 최소 제조 데이터 어휘\" ; rdfs:comment \"레코드 노드(cp:*Record)와 업무 키 노드(cp:Product 등)를 구분한다\" .", "",
         "cp:Dataset a owl:Class ; rdfs:label \"데이터셋\" .", "cp:hasKey a owl:ObjectProperty ; rdfs:comment \"레코드 → 업무 키 노드\" .",
         "cp:inDataset a owl:ObjectProperty ; rdfs:range cp:Dataset .", "cp:datasetId a owl:DatatypeProperty .", "cp:datasetSha256 a owl:DatatypeProperty .",
         "cp:groundTruthSha256 a owl:DatatypeProperty .", "cp:builtBy a owl:DatatypeProperty .", ""]
    for ent in D.ENTITY_ORDER:
        L.append(f"cp:{ent}Record a owl:Class ; rdfs:label \"{ent} 원본 레코드\" .")
        if ent in MASTER:
            L.append(f"cp:{ent} a owl:Class ; rdfs:label \"{ent} (업무 키로 식별되는 개체)\" .")
        for field, d in FK[ent].items():
            p = f"cp:{ent}_{field}"
            tgt = REFS.get((ent, field))
            if tgt:
                L.append(f"{p} a owl:ObjectProperty ; rdfs:domain cp:{ent}Record ; rdfs:range cp:{tgt} .")
            elif (ent, field) in COND_REFS:
                L.append(f"{p} a owl:ObjectProperty ; rdfs:domain cp:{ent}Record ; rdfs:comment \"item_type에 따라 cp:Product 또는 cp:Material\" .")
            else:
                rng = {"decimal": "xsd:decimal", "int": "xsd:integer", "bool": "xsd:boolean", "date": "xsd:date"}.get(d["kind"], "xsd:string")
                L.append(f"{p} a owl:DatatypeProperty ; rdfs:domain cp:{ent}Record ; rdfs:range {rng} .")
        L.append("")
    return "\n".join(L)


def main() -> int:
    gt = D.load_gt()
    ONTOLOGY.parent.mkdir(exist_ok=True)
    ttl = ontology_ttl()
    Graph().parse(data=ttl, format="turtle")      # 문법 확인
    ONTOLOGY.write_text(ttl, encoding="utf-8", newline="\n")
    notes = []
    g = build_graph(gt["entities"], "clean", notes, D.dataset_sha256(gt["entities"]))
    rt = round_trip(g, gt["entities"])
    print({"triples": len(g), "graph_sha256": graph_sha256(g), "conversion_notes": len(notes), "round_trip_mismatches": len(rt["mismatches"]),
           "record_nodes": rt["record_nodes"], "records": rt["records"]})
    return 0 if not rt["mismatches"] and rt["record_iri_collisions"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
