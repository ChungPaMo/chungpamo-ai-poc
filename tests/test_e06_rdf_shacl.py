"""E06 RDF/SHACL 테스트: 매핑 결정성·왕복, shape 메타데이터, 정상 데이터 무오탐, 단일 주입 검출, Q1~Q5 정답, pyshacl·rdflib 동작 확인."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

import e05_dataset as D
import e06_queries as Q
import e06_validate_shacl as V
from e06_build_rdf import CP, ID, build_graph, graph_sha256, ontology_ttl, round_trip
from e06_shapes import shapes_ttl

logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parents[1]
GT = D.load_gt()
SPEC = json.loads((D.EVAL_DIR / "eval_set_v1.json").read_text(encoding="utf-8"))
SINGLES = [d for d in SPEC["datasets"] if d["kind"] == "single"]
CATALOG = json.loads((ROOT / "configs" / "e05_validation_rules.json").read_text(encoding="utf-8"))


def ents_of(ds):
    return D.apply_ops(GT["entities"], ds["ops"], ds["dataset_id"])[0]


def test_e06_code_does_not_read_truth():
    for f in ("e06_build_rdf.py", "e06_shapes.py", "e06_validate_shacl.py", "e06_queries.py"):
        text = (ROOT / "scripts" / f).read_text(encoding="utf-8")
        assert '"truth"' not in text and "eval_set_v1" not in text and "injected_errors" not in text, f
    assert '["expected"]' not in (ROOT / "scripts" / "e06_queries.py").read_text(encoding="utf-8").split("def expected")[0]


def test_rdf_build_is_deterministic_and_round_trips():
    g1, g2 = build_graph(GT["entities"], "clean"), build_graph(GT["entities"], "clean")
    assert graph_sha256(g1) == graph_sha256(g2)
    rt = round_trip(g1, GT["entities"])
    assert rt["mismatches"] == [] and rt["record_iri_collisions"] == 0 and rt["record_nodes"] == 353


def test_missing_master_is_not_materialized():
    ents = json.loads(json.dumps(GT["entities"]))
    ents["Material"] = [m for m in ents["Material"] if m["material_id"] != "M007"]
    g = build_graph(ents, "x")
    assert (URIRef(ID + "Material/M007"), RDF.type, CP.Material) not in g
    assert (URIRef(ID + "Material/M001"), RDF.type, CP.Material) in g


def test_generated_ttl_files_match_generators():
    assert (ROOT / "ontology" / "e06_minimal.ttl").read_text(encoding="utf-8") == ontology_ttl()
    assert (ROOT / "ontology" / "e06_shapes.ttl").read_text(encoding="utf-8") == shapes_ttl(GT["parameters"])[0]
    assert (ROOT / "ontology" / "e06_shapes_core_compare.ttl").read_text(encoding="utf-8") == shapes_ttl(GT["parameters"], "core")[0]


def test_every_scored_rule_has_a_shape_and_v13_has_none():
    _, count = shapes_ttl(GT["parameters"])
    rules = {r for r, _ in count}
    scored = {r["rule_id"] for r in CATALOG["rules"] if r["severity"] != "INFO"}
    assert rules == scored and "V13" not in rules
    sg, meta = V.shapes_graph(GT["parameters"]["reference_date"])
    assert len(meta) == sum(count.values())


def test_clean_data_conforms_pyshacl_and_hybrid():
    full = V.validate(GT["entities"], GT["parameters"], "clean")
    hyb = V.validate(GT["entities"], GT["parameters"], "clean", engine="hybrid")
    assert full["error"] is None and full["reports"] == [] and full["unmapped_results"] == [] and full["conversion_notes"] == []
    assert hyb["reports"] == []


@pytest.mark.parametrize("ds", SINGLES, ids=[d["dataset_id"] for d in SINGLES])
def test_single_injection_detected_by_shacl_hybrid(ds):
    got = {(r["rule_id"], r["record_uid"]) for r in V.validate(ents_of(ds), GT["parameters"], ds["dataset_id"], engine="hybrid")["reports"]}
    for x in ds["truth"]["expected"]:
        for u in x["record_uids"]:
            assert (x["rule"], u) in got, (ds["dataset_id"], x["rule"], u)


def test_pyshacl_equals_hybrid_on_compound():
    ds = next(d for d in SPEC["datasets"] if d["dataset_id"] == "C-3")
    a = V.validate(ents_of(ds), GT["parameters"], "C-3")["reports"]
    b = V.validate(ents_of(ds), GT["parameters"], "C-3", engine="hybrid")["reports"]
    key = lambda rs: sorted((r["rule_id"], str(r["record_uid"]), r["field"]) for r in rs)
    assert key(a) == key(b)


@pytest.mark.parametrize("cls,kw", [(Q.PyProvider, {}), (Q.SqlProvider, {}), (Q.SparqlProvider, {}), (Q.SparqlProvider, {"naive": True})],
                         ids=["python", "sqlite", "sparql", "sparql_naive"])
def test_q1_to_q5_match_expected_cq(cls, kw):
    s = Q.score(Q.run_all(cls(GT["entities"], GT["parameters"], **kw), GT["parameters"]), Q.expected(GT))
    assert all(v["exact"] for v in s.values()), s


def test_sparql_path_cannot_filter_intermediate_bom_status():
    ents = Q.chain_entities(3)
    ents["Material"].append({**ents["Material"][0], "record_uid": D.new_uid("t", "m"), "material_id": "MY"})
    ents["BOM"].append({**ents["BOM"][1], "record_uid": D.new_uid("t", "b"), "bom_id": "B1-OLD", "is_active": False})
    ents["BOMLine"].append({**ents["BOMLine"][1], "record_uid": D.new_uid("t", "l"), "bom_id": "B1-OLD", "component_type": "MATERIAL",
                            "component_material_id": "MY", "component_product_id": None})
    assert Q.PyProvider(ents, GT["parameters"]).ancestors_finished("MATERIAL", "MY") == []
    assert Q.SqlProvider(ents, GT["parameters"]).ancestors_finished("MATERIAL", "MY") == []
    assert Q.SparqlProvider(ents, GT["parameters"]).ancestors_finished("MATERIAL", "MY") == []
    assert Q.SparqlProvider(ents, GT["parameters"], naive=True).ancestors_finished("MATERIAL", "MY") == ["P0"]   # 경로식만 쓰면 오답


def test_rdflib_decimal_and_date_lexical_leniency_observed():
    """rdflib 7.6.0 동작 기록: XSD 어휘 규칙상 틀린 값을 정상으로 받아들임 (보고서 결함). 버전이 바뀌면 이 테스트가 알려준다."""
    for v in ("NaN", "1e3", " 12", "１２", "1_000"):
        assert not Literal(v, datatype=XSD.decimal).ill_typed, v
    assert not Literal("2026-11-15T00:00", datatype=XSD.date).ill_typed
    for v, t in (("1O50", XSD.decimal), ("2026-02-30", XSD.date), ("3.0", XSD.integer)):
        assert Literal(v, datatype=t).ill_typed, v


def test_pyshacl_core_comparison_aborts_on_ill_typed_date():
    from pyshacl import validate
    EX = Namespace("http://example.org/t#")
    g = Graph()
    g.add((EX.n, RDF.type, EX.T))
    g.add((EX.n, EX.a, Literal("2026-11-10", datatype=XSD.date)))
    g.add((EX.n, EX.b, Literal("2026-02-30", datatype=XSD.date)))
    s = Graph().parse(data="""@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <http://example.org/t#> .
        ex:S a sh:NodeShape ; sh:targetClass ex:T ; sh:property [ sh:path ex:a ; sh:lessThanOrEquals ex:b ] .""", format="turtle")
    with pytest.raises(TypeError):
        validate(g, shacl_graph=s)


def test_requirements_lock_pins_rdflib_and_pyshacl():
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    assert "rdflib==7.6.0" in lock and "pyshacl==0.40.1" in lock
