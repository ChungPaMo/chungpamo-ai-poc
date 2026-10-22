"""E06 RDF/SHACL 검증기 (방식 B). 엔터티 dict → RDF 그래프(e06_build_rdf) → pyshacl 검증 → E05와 같은 보고 형식.

- 검출 출처를 나눈다: shacl_core / shacl_sparql (shape의 cp:engine) / conversion(변환 기록, 채점에 넣지 않음).
- 외부 Python 검증은 쓰지 않는다. V13(생산능력)은 shape가 없어 보고하지 않는다.
- pyshacl 옵션: inference='none'(추론 없음), allow_warnings=True, abort_on_first=False.
- 평가셋 정답은 읽지 않는다.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from pathlib import Path

from pyshacl import validate as shacl_validate
from rdflib import RDF, Graph, Namespace, URIRef

import e05_dataset as D
from e06_build_rdf import CP, build_graph
from e06_shapes import RULES, shapes_ttl

SHN = Namespace("http://www.w3.org/ns/shacl#")
logging.getLogger("pyshacl").setLevel(logging.ERROR)
logging.getLogger("rdflib").setLevel(logging.ERROR)


@lru_cache(maxsize=4)
def shapes_graph(reference_date: str, compare: str = "sparql") -> tuple[Graph, dict]:
    ttl, _ = shapes_ttl({"reference_date": reference_date}, compare)
    g = Graph().parse(data=ttl, format="turtle")
    meta = {}
    for s in g.subjects(CP.ruleId, None):
        meta[s] = (str(g.value(s, CP.ruleId)), str(g.value(s, CP.fieldName)), str(g.value(s, CP.engine)))
    return g, meta


def record_index(g: Graph) -> dict:
    out = {}
    for ent in D.ENTITY_ORDER:
        for r in g.subjects(RDF.type, CP[f"{ent}Record"]):
            uid = g.value(r, CP[f"{ent}_record_uid"])
            out[r] = (ent, None if uid is None else str(uid))
    return out


def parse_results(rg: Graph, data: Graph, meta: dict, dataset_id: str) -> tuple[list[dict], list[dict]]:
    idx = record_index(data)
    reports, unmapped, seen = [], [], set()
    for res in rg.subjects(RDF.type, SHN.ValidationResult):
        focus, src = rg.value(res, SHN.focusNode), rg.value(res, SHN.sourceShape)
        val = rg.value(res, SHN.value)
        if src not in meta or focus not in idx:
            unmapped.append({"focus": str(focus), "source_shape": str(src), "message": str(rg.value(res, SHN.resultMessage))})
            continue
        rule, field, engine = meta[src]
        ent, uid = idx[focus]
        key = (rule, uid, field)
        if key in seen:
            continue
        seen.add(key)
        r = RULES[rule]
        reports.append({"dataset_id": dataset_id, "rule_id": rule, "layer": r["layer"], "entity": ent, "record_uid": uid,
                        "field_path": f"{ent}.{field}", "field": field, "severity": r["severity"], "detected": True,
                        "actual_value": None if val is None else str(val), "expected_constraint": r["description"],
                        "explanation": str(rg.value(res, SHN.resultMessage) or ""),
                        "evidence": {"source_shape": str(src), "focus_node": str(focus), "result_path": str(rg.value(res, SHN.resultPath) or "")},
                        "source": "shacl_core" if engine == "CORE" else "shacl_sparql"})
    reports.sort(key=lambda x: (x["rule_id"], str(x["record_uid"]), x["field"]))
    return reports, unmapped


@lru_cache(maxsize=4)
def split_shapes(reference_date: str, compare: str = "sparql") -> tuple[Graph, list[tuple]]:
    """hybrid 방식용: Core shape만 남긴 shape 그래프 + SPARQL 규칙 목록(shape IRI, 대상 클래스, $this를 ?this로 바꾼 질의)."""
    sg, meta = shapes_graph(reference_date, compare)
    core = Graph()
    for t in sg:
        core.add(t)
    sparql = []
    for s, (rule, field, engine) in meta.items():
        if engine != "SPARQL":
            continue
        cons = sg.value(s, SHN.sparql)
        sel = str(sg.value(cons, SHN.select)).replace("$this", "?this")
        cls = sg.value(s, SHN.targetClass)
        sel = sel.replace("WHERE {", f"WHERE {{ ?this a <{cls}> .", 1)
        sparql.append((s, sel))
        for t in list(core.triples((s, None, None))):
            core.remove(t)
    return core, sorted(sparql, key=lambda x: str(x[0]))


PREFIXES = f"PREFIX cp: <{CP}>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"


def validate(ents: dict, params: dict, dataset_id: str, compare: str = "sparql", engine: str = "pyshacl") -> dict:
    """engine="pyshacl": 모든 shape를 pyshacl로 (SHACL 방식). engine="hybrid": Core shape는 pyshacl, SPARQL 규칙은 같은 질의를 rdflib로 규칙당 1회 실행."""
    t0 = time.perf_counter()
    notes = []
    data = build_graph(ents, dataset_id, notes)
    t1 = time.perf_counter()
    sg, meta = shapes_graph(params["reference_date"], compare)
    shapes = sg if engine == "pyshacl" else split_shapes(params["reference_date"], compare)[0]
    try:
        conforms, rg, _ = shacl_validate(data, shacl_graph=shapes, inference="none", abort_on_first=False, allow_warnings=True)
        error = None
    except Exception as e:                        # pyshacl 내부 오류 — 검증 실패로 그대로 기록 (조용히 넘기지 않음)
        conforms, rg, error = None, Graph(), f"{type(e).__name__}: {e}"
    t2 = time.perf_counter()
    reports, unmapped = parse_results(rg, data, meta, dataset_id)
    t3 = t2
    if engine == "hybrid":
        idx = record_index(data)
        seen = {(r["rule_id"], r["record_uid"], r["field"]) for r in reports}
        for s, sel in split_shapes(params["reference_date"], compare)[1]:
            rule, field, _ = meta[s]
            for row in data.query(PREFIXES + sel):
                ent, uid = idx[row.this]
                if (rule, uid, field) in seen:
                    continue
                seen.add((rule, uid, field))
                r = RULES[rule]
                reports.append({"dataset_id": dataset_id, "rule_id": rule, "layer": r["layer"], "entity": ent, "record_uid": uid,
                                "field_path": f"{ent}.{field}", "field": field, "severity": r["severity"], "detected": True,
                                "actual_value": None if row.value is None else str(row.value), "expected_constraint": r["description"],
                                "explanation": "SPARQL 직접 질의", "evidence": {"source_shape": str(s), "focus_node": str(row.this)}, "source": "sparql_direct"})
        t3 = time.perf_counter()
        reports.sort(key=lambda x: (x["rule_id"], str(x["record_uid"]), x["field"]))
    conv = [{"dataset_id": dataset_id, **n, "source": "conversion"} for n in notes]
    return {"reports": reports, "conversion_notes": conv, "unmapped_results": unmapped, "error": error, "conforms": conforms,
            "triples": len(data), "build_s": t1 - t0, "shacl_s": t2 - t1, "sparql_direct_s": t3 - t2}


if __name__ == "__main__":
    gt = D.load_gt()
    r = validate(gt["entities"], gt["parameters"], "clean")
    print({k: (len(v) if isinstance(v, list) else v) for k, v in r.items()})
    for x in r["reports"][:10]:
        print(x["rule_id"], x["entity"], x["record_uid"], x["field"], x["explanation"][:80])
