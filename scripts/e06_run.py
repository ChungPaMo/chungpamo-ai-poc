"""E06 실행: RDF/SHACL 검증 정확도(E05 평가셋·정답·채점기 그대로) → Q1~Q5 관계 조회 → S/M/L 성능 → 결과 기록.

    .\\.venv\\Scripts\\python.exe scripts\\e06_run.py --stage accuracy|queries|perf|report|all

- 입력은 읽기 전용: ground_truth_v2(해시 확인), E05 평가셋 v1(manifest 해시·데이터셋 해시 확인), E05 결과(results/E05_schema_sql/scores.json).
- 방식: shacl_pyshacl (모든 shape를 pyshacl로 — SHACL 방식 본 결과), shacl_hybrid (Core shape는 pyshacl, SPARQL 규칙은 같은 질의를 rdflib로 1회 — 엔진 비용 비교용),
  shacl_core_compare (두 속성 비교를 sh:lessThan 계열 Core 제약으로 쓴 변형 — pyshacl 중단 건수 측정용).
- 외부 API·네트워크 사용 없음. 결과: results/E06_rdf_shacl/ (합성 데이터만). 상태 RUNNING.
"""

from __future__ import annotations

import argparse
import ast
import csv
import datetime as dt
import hashlib
import io
import json
import logging
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

import e05_dataset as D
import e05_run as R5
import e05_score as SC

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "E06_rdf_shacl"
E05_SCORES = ROOT / "results" / "E05_schema_sql" / "scores.json"
SPEC = D.EVAL_DIR / "eval_set_v1.json"
MANIFEST = D.EVAL_DIR / "manifest_v1.json"
REPEATS = 3
logging.disable(logging.CRITICAL)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wj(name, obj):
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")


def rj(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def load_inputs():
    gt = D.load_gt()
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha(SPEC) != man["eval_set_sha256"]:
        raise SystemExit("평가셋 해시 불일치 → 중단")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    mds = {d["dataset_id"]: d["dataset_sha256"] for d in man["datasets"]}
    return gt, man, spec, mds


# ------------------------------------------------------------------ accuracy
def stage_accuracy():
    import e06_validate_shacl as V
    from e06_build_rdf import build_graph, graph_sha256, round_trip
    gt, man, spec, mds = load_inputs()
    implemented = {r for r, _ in __import__("e06_shapes").shapes_ttl(gt["parameters"])[1]}
    methods = ["shacl_pyshacl", "shacl_hybrid", "shacl_core_compare"]
    results = {m: [] for m in methods}
    reports = {m: {} for m in methods}
    runinfo = {m: {} for m in methods}
    conv, rt, det = {}, {}, {}
    for ds in spec["datasets"]:
        did = ds["dataset_id"]
        ents, _ = D.apply_ops(gt["entities"], ds["ops"], did)
        if D.dataset_sha256(ents) != mds[did]:
            raise SystemExit(f"데이터셋 {did} 해시 불일치 → 중단")
        counts = {e: len(v) for e, v in ents.items()}
        g1, g2 = build_graph(ents, did), build_graph(ents, did)
        det[did] = {"graph_sha256": graph_sha256(g1), "rebuild_equal": graph_sha256(g1) == graph_sha256(g2), "triples": len(g1)}
        r = round_trip(g1, ents)
        rt[did] = {"mismatches": len(r["mismatches"]), "record_iri_collisions": r["record_iri_collisions"]}
        for m in methods:
            kw = {"shacl_pyshacl": {}, "shacl_hybrid": {"engine": "hybrid"}, "shacl_core_compare": {"compare": "core"}}[m]
            out = V.validate(ents, gt["parameters"], did, **kw)
            reports[m][did] = out["reports"]
            runinfo[m][did] = {"error": out["error"], "unmapped": len(out["unmapped_results"]), "shacl_s": round(out["shacl_s"], 3),
                               "sparql_direct_s": round(out["sparql_direct_s"], 3), "reports": len(out["reports"])}
            results[m].append(SC.score_dataset(ds, out["reports"], counts, implemented))
            if m == "shacl_pyshacl":
                notes = out["conversion_notes"]
                exp_keys = {(u, x["field"]) for x in ds["truth"]["expected"] for u in x["record_uids"]}
                conv[did] = {"notes": len(notes), "kinds": sorted({n["kind"] for n in notes}),
                             "expected_items_also_flagged_at_conversion": sorted(f"{n['record_uid']}|{n['field']}" for n in notes if (n["record_uid"], n["field"]) in exp_keys)}
        print(did, {m: runinfo[m][did]["reports"] for m in methods}, flush=True)
    # 반복 일치: pyshacl 두 번째 실행 (정상·경계 통과·복합 + 단일 일부)
    rep_ids = [d["dataset_id"] for d in spec["datasets"] if d["kind"] in ("clean", "pass", "compound")] + ["I-B01a", "I-B02a", "I-V02", "I-V07", "I-S08c"]
    repeat = {}
    for ds in spec["datasets"]:
        if ds["dataset_id"] in rep_ids:
            ents, _ = D.apply_ops(gt["entities"], ds["ops"], ds["dataset_id"])
            again = V.validate(ents, gt["parameters"], ds["dataset_id"])["reports"]
            repeat[ds["dataset_id"]] = again == reports["shacl_pyshacl"][ds["dataset_id"]]
    agg = {m: SC.aggregate(results[m], implemented) for m in methods}
    by_source = {}
    for did, reps in reports["shacl_pyshacl"].items():
        for x in reps:
            by_source[x["source"]] = by_source.get(x["source"], 0) + 1
    same = {did: sorted(map(str, ((x["rule_id"], x["record_uid"], x["field"]) for x in reports["shacl_pyshacl"][did]))) ==
            sorted(map(str, ((x["rule_id"], x["record_uid"], x["field"]) for x in reports["shacl_hybrid"][did]))) for did in reports["shacl_pyshacl"]}
    tp_source = {}
    for ds, res in zip(spec["datasets"], results["shacl_pyshacl"]):
        expk = {(x["rule"], u) for x in ds["truth"]["expected"] for u in x["record_uids"]}
        for x in reports["shacl_pyshacl"][ds["dataset_id"]]:
            if (x["rule_id"], x["record_uid"]) in expk:
                tp_source[x["source"]] = tp_source.get(x["source"], 0) + 1
    e05 = json.loads(E05_SCORES.read_text(encoding="utf-8"))
    cmp = {}
    for m5 in ("python_full", "sql_queries"):
        d5 = {r["dataset_id"]: r for r in e05["datasets"][m5]}
        diff = []
        for r in results["shacl_pyshacl"]:
            a, b = set(r["matched_rules"]), set(d5[r["dataset_id"]]["matched_rules"])
            if a != b or r["classes"].get("fp", 0) != d5[r["dataset_id"]]["classes"].get("fp", 0):
                diff.append({"dataset_id": r["dataset_id"], "shacl_matched": sorted(a), f"{m5}_matched": sorted(b),
                             "shacl_fp": r["classes"].get("fp", 0), f"{m5}_fp": d5[r["dataset_id"]]["classes"].get("fp", 0)})
        cmp[m5] = {"ERROR": e05["aggregate"][m5]["ERROR"], "WARNING": e05["aggregate"][m5]["WARNING"], "datasets_differing_from_shacl": diff}
    crashes = {did: v["error"] for did, v in runinfo["shacl_core_compare"].items() if v["error"]}
    wj("accuracy.json", {"aggregate": agg, "datasets": results, "runinfo": runinfo, "conversion": conv, "round_trip": rt, "determinism": det,
                         "repeat_pyshacl_equal": repeat, "pyshacl_vs_hybrid_equal": same, "reports_by_source": by_source, "tp_reports_by_source": tp_source,
                         "e05_comparison": cmp, "core_compare_crashes": crashes, "implemented_rules": sorted(implemented)})
    wj("reports_pyshacl.json", reports["shacl_pyshacl"])
    print(json.dumps({m: {"ERROR": agg[m]["ERROR"], "WARNING": agg[m]["WARNING"], "events": agg[m]["events_ERROR"]} for m in methods}, ensure_ascii=False))
    print("crashes", len(crashes), "hybrid==pyshacl", sum(same.values()), "/", len(same), "repeat", repeat)


# ------------------------------------------------------------------ queries
def peak_mb() -> float:
    """현재 인터프리터의 피크 메모리 (Windows: peak working set, 그 밖: 현재 RSS)."""
    mi = psutil.Process().memory_info()
    return round(getattr(mi, "peak_wset", mi.rss) / 1048576, 1)


def queries_child(method: str):
    import e06_queries as Q
    gt = D.load_gt()
    t0 = time.perf_counter()
    cls = {"python": Q.PyProvider, "sqlite": Q.SqlProvider, "sparql": Q.SparqlProvider, "sparql_naive": Q.SparqlProvider}[method]
    P = cls(gt["entities"], gt["parameters"], **({"naive": True} if method == "sparql_naive" else {}))
    setup = time.perf_counter() - t0
    times = []
    ans = None
    for _ in range(REPEATS):
        t = time.perf_counter()
        ans = Q.run_all(P, gt["parameters"])
        times.append(time.perf_counter() - t)
    per_q = {}
    cq = gt["parameters"]["cq"]
    for qid, fn in (("Q1", lambda: [P.bom_candidates(c["product_id"], c["date"], Q.dd(c["qty"])) for c in cq["CQ-04"]["cases"]]),
                    ("Q2", lambda: [P.ancestors_finished("MATERIAL", m) for m in cq["CQ-05"]["material_ids"]]),
                    ("Q3Q4", lambda: Q.mrp(P, gt["parameters"])),
                    ("Q5", lambda: [P.ancestors_finished("MATERIAL", m) for m in P.long_lead_materials(cq["CQ-10"]["min_lead_time_days"])])):
        ts = []
        for _ in range(REPEATS):
            t = time.perf_counter()
            fn()
            ts.append(time.perf_counter() - t)
        per_q[qid] = statistics.median(ts)
    score = Q.score(ans, Q.expected(gt))
    print(json.dumps({"ok": True, "setup_s": setup, "run_all_s_median": statistics.median(times), "per_query_s_median": per_q, "score": score,
                      "self_peak_mb": peak_mb()}, default=str))


def chain_child(method: str, depth: int):
    import e06_queries as Q
    gt = D.load_gt()
    ents = Q.chain_entities(depth)
    cls = {"python": Q.PyProvider, "sqlite": Q.SqlProvider, "sparql": Q.SparqlProvider, "sparql_naive": Q.SparqlProvider}[method]
    P = cls(ents, gt["parameters"], **({"naive": True} if method == "sparql_naive" else {}))
    ts, ans = [], None
    for _ in range(REPEATS):
        if method == "sparql":
            P._used = None                      # 사용 간선 CONSTRUCT도 매회 포함
        t = time.perf_counter()
        ans = P.ancestors_finished("MATERIAL", "MX")
        ts.append(time.perf_counter() - t)
    print(json.dumps({"ok": True, "depth": depth, "q2_s_median": statistics.median(ts), "answer": ans, "correct": ans == ["P0"], "self_peak_mb": peak_mb()}))


def child_run(args, timeout=None):
    cmd = [sys.executable, str(Path(__file__))] + args
    t0 = time.perf_counter()
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=fo, stderr=fe)
        proc, peak = psutil.Process(p.pid), 0
        while p.poll() is None:
            try:      # venv python.exe는 실제 인터프리터를 자식으로 띄우는 런처 → 자식까지 합산
                peak = max(peak, proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True)))
            except psutil.Error:
                pass
            if timeout and time.perf_counter() - t0 > timeout:
                p.kill()
                p.wait()
                return {"ok": False, "timeout_s": timeout, "wall_s": time.perf_counter() - t0, "peak_rss_mb": round(peak / 1048576, 1)}
            time.sleep(0.01)
        fo.seek(0)
        fe.seek(0)
        lines = fo.read().decode("utf-8").strip().splitlines()
        err = fe.read().decode("utf-8", "replace")[-1500:]
    res = json.loads(lines[-1]) if lines else {"ok": False, "stderr": err}
    res.update({"wall_s": time.perf_counter() - t0, "peak_rss_mb": round(peak / 1048576, 1)})
    return res


def query_complexity():
    import e06_queries as Q
    src = (ROOT / "scripts" / "e06_queries.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    py = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == "PyProvider":
            py = {f.name: f.end_lineno - f.lineno + 1 for f in n.body if isinstance(f, ast.FunctionDef)}
    stat = lambda d: {k: {"chars": len(" ".join(v.split())), "lines": len(v.strip().splitlines())} for k, v in d.items()}
    return {"python_function_lines": py, "sql": stat(Q.SQL), "sparql": stat(Q.SPARQL)}


def stage_queries():
    import e06_queries as Q
    from e06_build_rdf import build_graph
    gt = D.load_gt()
    out = {"methods": {}, "chain": [], "complexity": query_complexity()}
    for m in ("python", "sqlite", "sparql", "sparql_naive"):
        out["methods"][m] = child_run(["--queries-child", m])
        print(m, {q: (v["correct"], v["expected_items"]) for q, v in out["methods"][m]["score"].items()}, round(out["methods"][m]["run_all_s_median"], 4), flush=True)
    for depth in (2, 4, 8, 16, 32, 64):
        for m in ("python", "sqlite", "sparql", "sparql_naive"):
            r = child_run(["--chain-child", m, str(depth)])
            out["chain"].append({"method": m, **r})
    # 판별 사례: 중간 단계 BOM이 비활성일 때 속성 경로만 쓰면 잘못된 상위 제품이 나오는지
    ents = Q.chain_entities(3)
    ents["Material"].append({**ents["Material"][0], "record_uid": D.new_uid("chain", "disc", "m"), "material_id": "MY"})
    ents["BOM"].append({**ents["BOM"][1], "record_uid": D.new_uid("chain", "disc", "b"), "bom_id": "B1-OLD", "bom_version": "V0", "is_active": False})
    ents["BOMLine"].append({**ents["BOMLine"][1], "record_uid": D.new_uid("chain", "disc", "l"), "bom_id": "B1-OLD",
                            "component_type": "MATERIAL", "component_material_id": "MY", "component_product_id": None})
    disc = {}
    for name, P in (("python", Q.PyProvider(ents, gt["parameters"])), ("sqlite", Q.SqlProvider(ents, gt["parameters"])),
                    ("sparql", Q.SparqlProvider(ents, gt["parameters"])), ("sparql_naive", Q.SparqlProvider(ents, gt["parameters"], naive=True))):
        disc[name] = P.ancestors_finished("MATERIAL", "MY")
    out["discrimination_inactive_bom"] = {"case": "P1의 비활성 BOM(B1-OLD)에만 자재 MY가 있음. 기대 정답: MY를 쓰는 완제품 없음 []", "answers": disc}
    wj("queries.json", out)
    print("discrimination", disc)


# ------------------------------------------------------------------ perf
def scaled_c1(k: int):
    gt = D.load_gt()
    base = R5.scale(gt["entities"], k)
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    c1 = next(d for d in spec["datasets"] if d["dataset_id"] == "C-1")
    ops = json.loads(json.dumps(c1["ops"]))
    for op in ops:
        op["where"] = {kk: (f"{v}_0" if kk in ("order_id", "bom_id", "material_id", "item_id", "product_id") and isinstance(v, str) and k > 1 else v)
                       for kk, v in op.get("where", {}).items()}
    ents, _ = D.apply_ops(base, ops, f"perf{k}")
    return gt, ents


def perf_child(method: str, k: int):
    import e06_queries as Q
    import e06_validate_shacl as V
    from pyshacl import validate as shacl_validate
    from rdflib import Graph
    from e06_build_rdf import build_graph
    gt, ents = scaled_c1(k)
    t0 = time.perf_counter()
    g = build_graph(ents, f"perf{k}")
    t1 = time.perf_counter()
    blob = g.serialize(format="turtle").encode("utf-8")
    t2 = time.perf_counter()
    g2 = Graph().parse(data=blob.decode("utf-8"), format="turtle")
    t3 = time.perf_counter()
    if method == "shacl_pyshacl":
        sg, meta = V.shapes_graph(gt["parameters"]["reference_date"])
        _, rg, _ = shacl_validate(g2, shacl_graph=sg, inference="none", abort_on_first=False, allow_warnings=True)
        reps, _ = V.parse_results(rg, g2, meta, "perf")
        t4 = t5 = time.perf_counter()
    else:
        core, sparqls = V.split_shapes(gt["parameters"]["reference_date"])
        sg, meta = V.shapes_graph(gt["parameters"]["reference_date"])
        _, rg, _ = shacl_validate(g2, shacl_graph=core, inference="none", abort_on_first=False, allow_warnings=True)
        reps, _ = V.parse_results(rg, g2, meta, "perf")
        t4 = time.perf_counter()
        n = sum(len(list(g2.query(V.PREFIXES + sel))) for _, sel in sparqls)
        t5 = time.perf_counter()
    P = Q.SparqlProvider(None, gt["parameters"], graph=g2)
    tq = time.perf_counter()
    P.ancestors_finished("MATERIAL", "M001_0" if k > 1 else "M001")
    P.long_lead_materials(14)
    tq2 = time.perf_counter()
    print(json.dumps({"ok": True, "method": method, "scale": k, "records": sum(len(v) for v in ents.values()), "triples": len(g2), "turtle_bytes": len(blob),
                      "rdf_build_s": t1 - t0, "serialize_s": t2 - t1, "load_s": t3 - t2, "validate_core_or_all_s": t4 - t3, "sparql_rules_s": t5 - t4,
                      "validate_s": t5 - t3, "pipeline_s": t5 - t0, "sparql_query_q2q5_s": tq2 - tq, "self_peak_mb": peak_mb()}))


PERF_DIR = "perf_v2"   # 2026-10-21 재측정 결과. 이전 perf.json(메모리 측정 버그가 있던 부분 실행)은 덮어쓰지 않고 보존


def stage_perf(scales=(1, 10, 50), methods=("shacl_hybrid", "shacl_pyshacl"), timeout=None):   # 시간 상한 없음 (사용자 지시)
    rows, raw = [], []
    for k in scales:
        for m in ("python_full", "sql_queries"):
            t = [R5.perf_child(m, k, None, False) for _ in range(REPEATS)]
            rows.append(summ_e05(m, k, t))
            raw.append({"method": m, "scale": k, "runs": t})
            print(rows[-1], flush=True)
        for m in methods:
            t = [child_run(["--perf-child", m, str(k)], timeout=timeout) for _ in range(REPEATS)]
            rows.append(summ_e06(m, k, t))
            raw.append({"method": m, "scale": k, "runs": t})
            print(rows[-1], flush=True)
            wj(f"{PERF_DIR}/perf.json", rows)
            wj(f"{PERF_DIR}/perf_runs.json", raw)
            if not all(x.get("ok") for x in t):
                break
    wj(f"{PERF_DIR}/perf.json", rows)
    wj(f"{PERF_DIR}/perf_runs.json", raw)


def rng(xs):
    return (round(min(xs), 4), round(max(xs), 4)) if xs else (None, None)


def med(xs):
    return round(statistics.median(xs), 4) if xs else None


def summ_e05(m, k, t):
    ok = [x for x in t if x.get("ok")]
    return {"method": m, "scale": k, "records": ok[0]["records"] if ok else None, "runs_ok": f"{len(ok)}/{len(t)}", "triples": None, "turtle_bytes": None,
            "convert_s": med([x["load_s"] for x in ok]), "serialize_s": None, "load_s": None, "validate_s": med([x["validate_s"] for x in ok]),
            "pipeline_s": med([x["load_s"] + x["validate_s"] for x in ok]), "wall_s": med([x["wall_s"] for x in ok]), "peak_rss_mb": med([x["peak_rss_mb"] for x in ok]),
            "self_peak_mb": None, "validate_s_min": rng([x["validate_s"] for x in ok])[0], "validate_s_max": rng([x["validate_s"] for x in ok])[1],
            "pipeline_s_min": None, "pipeline_s_max": None,
            "sparql_query_q2q5_s": None, "note": "E05 검증기 재측정(같은 세션). convert_s = SQLite 적재(Python은 0)"}


def summ_e06(m, k, t):
    ok = [x for x in t if x.get("ok")]
    return {"method": m, "scale": k, "records": ok[0]["records"] if ok else None, "runs_ok": f"{len(ok)}/{len(t)}",
            "triples": ok[0]["triples"] if ok else None, "turtle_bytes": ok[0]["turtle_bytes"] if ok else None,
            "convert_s": med([x["rdf_build_s"] for x in ok]), "serialize_s": med([x["serialize_s"] for x in ok]), "load_s": med([x["load_s"] for x in ok]),
            "validate_s": med([x["validate_s"] for x in ok]), "pipeline_s": med([x["pipeline_s"] for x in ok]), "wall_s": med([x["wall_s"] for x in ok]),
            "peak_rss_mb": med([x["peak_rss_mb"] for x in t]), "self_peak_mb": med([x["self_peak_mb"] for x in ok]),
            "validate_s_min": rng([x["validate_s"] for x in ok])[0], "validate_s_max": rng([x["validate_s"] for x in ok])[1],
            "pipeline_s_min": rng([x["pipeline_s"] for x in ok])[0], "pipeline_s_max": rng([x["pipeline_s"] for x in ok])[1],
            "sparql_query_q2q5_s": med([x["sparql_query_q2q5_s"] for x in ok]),
            "note": "" if len(ok) == len(t) else f"시간 초과 {len(t) - len(ok)}회 (상한 {t[0].get('timeout_s')} s)"}


# ------------------------------------------------------------------ report
def complexity():
    out = {}
    for f in ("e06_build_rdf.py", "e06_shapes.py", "e06_validate_shacl.py", "e06_queries.py", "e05_validate_python.py", "e05_validate_sql.py"):
        out[f] = len((ROOT / "scripts" / f).read_text(encoding="utf-8").splitlines())
    ttl = (ROOT / "ontology" / "e06_shapes.ttl").read_text(encoding="utf-8")
    out["e06_shapes.ttl"] = {"lines": len(ttl.splitlines()), "bytes": len(ttl.encode("utf-8"))}
    out["e06_minimal.ttl"] = {"lines": len((ROOT / "ontology" / "e06_minimal.ttl").read_text(encoding="utf-8").splitlines())}
    import e06_shapes
    _, count = e06_shapes.shapes_ttl(D.load_gt()["parameters"])
    per_rule = {}
    for (r, e), v in count.items():
        per_rule.setdefault(r, {})[e] = v
    out["shapes_per_rule"] = dict(sorted(per_rule.items()))
    out["dependencies"] = {p: __import__("importlib.metadata").metadata.version(p) for p in ("rdflib", "pyshacl", "owlrl", "pyparsing", "prettytable", "html5rdf")}
    return out


def stage_report():
    from importlib.metadata import version
    import e06_queries  # noqa: F401
    acc = rj("accuracy.json")
    qs = rj("queries.json") if (OUT / "queries.json").exists() else None
    perf = rj(f"{PERF_DIR}/perf.json") if (OUT / PERF_DIR / "perf.json").exists() else []   # 이전 perf.json(메모리 측정 무효)은 쓰지 않음
    sc = rj("schema_change.json") if (OUT / "schema_change.json").exists() else None
    comp = complexity()
    wj("complexity.json", comp)
    rows = []
    for m, a in acc["aggregate"].items():
        for sev in ("ERROR", "WARNING"):
            rows.append({"method": m, "severity": sev, **{k: a[sev][k] for k in ("tp", "fp", "fn", "tn", "precision", "recall", "f1")},
                         "events_total": a[f"events_{sev}"]["total"], "events_detected": a[f"events_{sev}"]["detected_any"],
                         "fp_on_clean_and_pass": a["fp_on_clean_and_pass"] if sev == "ERROR" else "", "rules_implemented": a["rule_coverage"]["implemented_rules"],
                         "rules_detected": a["rule_coverage"]["rules_detected_at_least_once"], "rules_with_expected": a["rule_coverage"]["rules_with_expected_items"]})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    (OUT / "metrics.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    if perf:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(perf[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(perf)
        (OUT / PERF_DIR / "perf.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    gt = D.load_gt()
    from e06_build_rdf import build_graph, canonical_nt, graph_sha256
    g = build_graph(gt["entities"], "clean", None, D.dataset_sha256(gt["entities"]))
    (OUT / "clean_graph.nt").write_text(canonical_nt(g), encoding="utf-8", newline="\n")
    per_ent = {}
    from rdflib import RDF
    from e06_build_rdf import CP
    for ent in D.ENTITY_ORDER:
        recs = set(g.subjects(RDF.type, CP[f"{ent}Record"]))
        per_ent[ent] = {"records": len(recs), "triples_about_records": sum(1 for r in recs for _ in g.predicate_objects(r))}
    files = {f: sha(ROOT / "scripts" / f) for f in ("e06_build_rdf.py", "e06_shapes.py", "e06_validate_shacl.py", "e06_queries.py", "e06_schema_change.py", "e06_run.py",
                                                    "e05_dataset.py", "e05_score.py", "e05_validate_python.py", "e05_validate_sql.py", "e05_run.py", "e01_models.py")}
    meta = {"experiment_id": "E06", "status": "RUNNING", "run_timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "python": sys.version.split()[0], "packages": {p: version(p) for p in ("rdflib", "pyshacl", "owlrl", "pydantic", "psutil")},
            "inputs": {"ground_truth_v2_sha256": D.GT_SHA256, "eval_set_sha256": json.loads(MANIFEST.read_text(encoding="utf-8"))["eval_set_sha256"],
                       "e05_scores_sha256": sha(E05_SCORES)},
            "outputs": {"ontology_sha256": sha(ROOT / "ontology" / "e06_minimal.ttl"), "shapes_sha256": sha(ROOT / "ontology" / "e06_shapes.ttl"),
                        "shapes_core_compare_sha256": sha(ROOT / "ontology" / "e06_shapes_core_compare.ttl"), "clean_graph_sha256": graph_sha256(g),
                        "clean_triples": len(g), "per_entity": per_ent},
            "code_sha256": files, "external_calls": 0, "pyshacl_options": {"inference": "none", "allow_warnings": True, "abort_on_first": False},
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}
    wj("run_meta.json", meta)
    (OUT / "summary.md").write_text(summary_md(meta, acc, qs, perf, sc, comp), encoding="utf-8", newline="\n")
    (OUT / "failures.md").write_text(failures_md(acc), encoding="utf-8", newline="\n")


def summary_md(meta, acc, qs, perf, sc, comp):
    A = acc["aggregate"]
    L = ["# E06 결과 요약 (자동 생성, scripts/e06_run.py)", "",
         f"- 상태: {meta['status']} (검토 전). 실행 {meta['run_timestamp']}, Python {meta['python']}, rdflib {meta['packages']['rdflib']}, pyshacl {meta['packages']['pyshacl']}",
         f"- 입력: ground_truth_v2 {meta['inputs']['ground_truth_v2_sha256'][:12]}…, eval_set_v1 {meta['inputs']['eval_set_sha256'][:12]}… (E05와 같은 평가셋·정답·채점기)",
         f"- 정상 데이터 그래프: {meta['outputs']['clean_triples']} 트리플, sha256 {meta['outputs']['clean_graph_sha256'][:12]}…",
         "- **해석 주의**: 평가셋·정답·규칙 카탈로그·shape를 같은 작성자가 만들었다. 수치는 카탈로그 규칙의 SHACL 표현 일치도이며 일반화 성능이 아니다.", "",
         "## 정확도 (규칙 단위)", "", "| 방식 | 심각도 | TP | FP | FN | Precision | Recall | F1 | 사건 | 규칙 검출/기대 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m, a in A.items():
        for sev in ("ERROR", "WARNING"):
            L.append(f"| {m} | {sev} | {a[sev]['tp']} | {a[sev]['fp']} | {a[sev]['fn']} | {a[sev]['precision']} | {a[sev]['recall']} | {a[sev]['f1']} | "
                     f"{a[f'events_{sev}']['detected_any']}/{a[f'events_{sev}']['total']} | {a['rule_coverage']['rules_detected_at_least_once']}/{a['rule_coverage']['rules_with_expected_items']} |")
    for m5, c in acc["e05_comparison"].items():
        L.append(f"| E05 {m5} | ERROR | {c['ERROR']['tp']} | {c['ERROR']['fp']} | {c['ERROR']['fn']} | {c['ERROR']['precision']} | {c['ERROR']['recall']} | {c['ERROR']['f1']} | | |")
    L += ["", f"- 정상·경계 통과 오탐: " + ", ".join(f"{m} {a['fp_on_clean_and_pass']}" for m, a in A.items()),
          f"- 검출 출처(shacl_pyshacl 전체 보고): {acc['reports_by_source']}, 정답 레코드에 대한 보고: {acc['tp_reports_by_source']}",
          f"- 변환 단계 기록이 있는 데이터셋: {sum(1 for v in acc['conversion'].values() if v['notes'])}개, 그중 기대 항목과 겹친 기록 {sum(len(v['expected_items_also_flagged_at_conversion']) for v in acc['conversion'].values())}건 (SHACL 채점에 넣지 않음)",
          f"- pyshacl 결과 = hybrid 결과: {sum(acc['pyshacl_vs_hybrid_equal'].values())}/{len(acc['pyshacl_vs_hybrid_equal'])}, pyshacl 반복 실행 일치: {sum(acc['repeat_pyshacl_equal'].values())}/{len(acc['repeat_pyshacl_equal'])}",
          f"- RDF 재생성 해시 일치: {sum(1 for v in acc['determinism'].values() if v['rebuild_equal'])}/{len(acc['determinism'])}, 왕복 불일치 합계: {sum(v['mismatches'] for v in acc['round_trip'].values())}",
          f"- Core 비교 제약 변형에서 pyshacl 중단: {len(acc['core_compare_crashes'])}개 데이터셋 — " + ", ".join(f"{k}: {v[:60]}" for k, v in sorted(acc['core_compare_crashes'].items())), ""]
    for m5, c in acc["e05_comparison"].items():
        L.append(f"- E05 {m5}와 검출 규칙·오탐이 다른 데이터셋: {len(c['datasets_differing_from_shacl'])}개 " + ", ".join(d["dataset_id"] for d in c["datasets_differing_from_shacl"]))
    if qs:
        L += ["", "## Q1~Q5 관계 조회 (기대 정답 = GT expected.cq)", "", "| 방식 | Q1 | Q2 | Q3 | Q4 | Q5 | Q1~Q5 1회 s | 준비 s | 피크 RSS MB |", "|---|---|---|---|---|---|---|---|---|"]
        for m, r in qs["methods"].items():
            s = r["score"]
            L.append(f"| {m} | " + " | ".join(f"{s[q]['correct']}/{s[q]['expected_items']}" for q in ("Q1", "Q2", "Q3", "Q4", "Q5")) +
                     f" | {round(r['run_all_s_median'], 4)} | {round(r['setup_s'], 3)} | {r['peak_rss_mb']} |")
        L += ["", f"- 판별 사례(중간 BOM 비활성): {qs['discrimination_inactive_bom']['answers']} (기대 [])", "", "BOM 단계 증가(Q2, 합성 사슬) — 중앙값 s / 정답 여부", "",
              "| 깊이 | " + " | ".join(("python", "sqlite", "sparql", "sparql_naive")) + " |", "|---|---|---|---|---|"]
        for depth in sorted({c["depth"] for c in qs["chain"] if c.get("ok")}):
            cells = []
            for m in ("python", "sqlite", "sparql", "sparql_naive"):
                c = next((x for x in qs["chain"] if x.get("depth") == depth and x["method"] == m), None)
                cells.append(f"{round(c['q2_s_median'], 5)} / {c['correct']}" if c and c.get("ok") else "미측정")
            L.append(f"| {depth} | " + " | ".join(cells) + " |")
    if sc:
        L += ["", "## 규칙·스키마 변경", "", "| 시나리오 | 방식 | 바뀐 파일 | 바뀐 줄 | 회귀: 결과가 바뀐 데이터셋 | 변경 후 정상 데이터 보고 |", "|---|---|---|---|---|---|"]
        for sid, e in sc["scenarios"].items():
            for m, v in e["methods"].items():
                extra = f" (생성된 TTL {v['generated_ttl_lines_changed']}줄)" if "generated_ttl_lines_changed" in v else ""
                L.append(f"| {sid} | {m} | {len(v['files_changed'])} | {v['lines_changed']}{extra} | {v['datasets_changed']} | {v['clean_reports_after']} |")
        for sid, v in sc["data_scenarios"].items():
            L.append(f"- {sid} {v['title']}: " + json.dumps({k: x for k, x in v.items() if k != "title"}, ensure_ascii=False))
    if perf:
        L += ["", "## 성능 (자식 프로세스 3회 중앙값, 오류 섞인 C-1 데이터)", "",
              "| 방식 | 배율 | 레코드 | 트리플 | Turtle KB | 변환 s | 직렬화 s | 로딩 s | 검증 s | 파이프라인 s | 피크 RSS MB(부모 합산) | 피크 MB(자체 기록) | SPARQL Q2·Q5 s | 비고 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in perf:
            L.append(f"| {p['method']} | {p['scale']} | {p['records']} | {p['triples'] or '-'} | {round(p['turtle_bytes'] / 1024) if p['turtle_bytes'] else '-'} | {p['convert_s']} | "
                     f"{p['serialize_s'] if p['serialize_s'] is not None else '-'} | {p['load_s'] if p['load_s'] is not None else '-'} | {p['validate_s']} | {p['pipeline_s']} | "
                     f"{p['peak_rss_mb']} | {p.get('self_peak_mb') if p.get('self_peak_mb') is not None else '-'} | {p['sparql_query_q2q5_s'] if p['sparql_query_q2q5_s'] is not None else '-'} | {p['note']} |")
    else:
        L += ["", "## 성능", "", "미측정"]
    L += ["", "## 구현 규모", "", "```", json.dumps({k: v for k, v in comp.items() if k != "shapes_per_rule"}, ensure_ascii=False), "```"]
    return "\n".join(L) + "\n"


def failures_md(acc):
    L = ["# E06 실패·오탐·미탐 기록 (자동 생성)", "", "판정: scripts/e05_score.py (E05와 동일). 수동 조정 없음.", ""]
    for m, a in acc["aggregate"].items():
        L += [f"## {m}", "", f"- ERROR TP/FP/FN {a['ERROR']['tp']}/{a['ERROR']['fp']}/{a['ERROR']['fn']}, WARNING {a['WARNING']['tp']}/{a['WARNING']['fp']}/{a['WARNING']['fn']}",
              f"- 보고 분류: {a['classes']}", f"- 검출하지 못한 기대 규칙: {', '.join(a['rule_coverage']['never_detected']) or '없음'}", ""]
        res = acc["datasets"][m]
        fps = [(r["dataset_id"], f) for r in res for f in r["false_positives"]]
        if fps:
            L += ["### 오탐", "", "| 데이터셋 | 규칙 | 엔터티 | 필드 |", "|---|---|---|---|"] + [f"| {d} | {f['rule_id']} | {f['entity']} | {f['field']} |" for d, f in fps] + [""]
        fns = [(r["dataset_id"], x) for r in res for sev in ("ERROR", "WARNING") for x in r["by_severity"][sev]["fn_items"]]
        if fns:
            L += ["### 미탐지", "", "| 데이터셋 | 규칙 | 필드 | record_uid |", "|---|---|---|---|"] + [f"| {d} | {x['rule']} | {x['field']} | {x['uid']} |" for d, x in fns] + [""]
        parts = [(r["dataset_id"], p) for r in res for p in r["partial"]]
        if parts:
            L += ["### 부분 탐지", ""] + [f"- {d}: {p['rule_id']} {p['entity']}.{p['field']}" for d, p in parts] + [""]
    for m5, c in acc["e05_comparison"].items():
        if c["datasets_differing_from_shacl"]:
            L += [f"## E05 {m5}와 다른 데이터셋", "", "```", json.dumps(c["datasets_differing_from_shacl"], ensure_ascii=False, indent=1), "```", ""]
    L += ["## 변환 단계 기록 (채점 제외)", ""] + [f"- {k}: {v}" for k, v in acc["conversion"].items() if v["notes"]]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all")
    ap.add_argument("--queries-child")
    ap.add_argument("--chain-child", nargs=2)
    ap.add_argument("--perf-child", nargs=2)
    ap.add_argument("--scales", default="1,10,50")
    a = ap.parse_args()
    if a.queries_child:
        return queries_child(a.queries_child)
    if a.chain_child:
        return chain_child(a.chain_child[0], int(a.chain_child[1]))
    if a.perf_child:
        return perf_child(a.perf_child[0], int(a.perf_child[1]))
    stages = ["accuracy", "queries", "perf", "report"] if a.stage == "all" else a.stage.split(",")
    for s in stages:
        if s == "perf":
            stage_perf(tuple(int(x) for x in a.scales.split(",")))
        else:
            {"accuracy": stage_accuracy, "queries": stage_queries, "report": stage_report}[s]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
