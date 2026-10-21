"""E05 실행: 평가셋 해시 확인 → 4개 방식 검증 → 채점 → 생산능력 계산 대조 → E02 연계 4건 → 규모·규칙 수별 성능(3회) → 결과 기록.

    .\\.venv\\Scripts\\python.exe scripts\\e05_run.py [--skip-perf]

방식: python_full (Pydantic + 독립 함수), python_pydantic_only, sql_queries (SQLite 검증 질의), sql_constraints (SQLite 제약 적재)
결과: results/E05_schema_sql/ (합성 데이터만 포함). 상태 RUNNING. 외부 API·네트워크 사용 없음.
"""

from __future__ import annotations

import argparse
import ast
import copy
import csv
import datetime as dt
import hashlib
import io
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

import e05_dataset as D
import e05_score as SC
import e05_validate_python as PY
import e05_validate_sql as SQ

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "E05_schema_sql"
SPEC = D.EVAL_DIR / "eval_set_v1.json"
MANIFEST = D.EVAL_DIR / "manifest_v1.json"
REPEATS = 3
METHODS = ["python_full", "python_pydantic_only", "sql_queries", "sql_constraints"]
ALL_RULES = {r["rule_id"] for r in SC.CATALOG["rules"] if r["severity"] != "INFO"}
IMPLEMENTED = {"python_full": ALL_RULES, "sql_queries": ALL_RULES,
               "python_pydantic_only": {"S01", "S02", "S03", "S04", "S05", "S06", "S07", "B03", "B05", "B07", "B13", "B14", "V01", "V02", "V05", "V07", "V10"},
               "sql_constraints": {"S01", "S02", "S03", "S04", "S05", "S06", "S08", "R01", "R02", "R03", "R04", "R05", "R06", "R07", "B03", "B05", "B07", "B13", "B14",
                                   "V01", "V02", "V03", "V04", "V05", "V06", "V07", "V10"}}


def run_method(m, ents, params, did, layers=None):
    if m == "python_full":
        return PY.validate(ents, params, did, "full") if layers is None else validate_layers_py(ents, params, did, layers)
    if m == "python_pydantic_only":
        return PY.validate(ents, params, did, "pydantic_only")
    if m == "sql_queries":
        return SQ.run_queries(ents, params, did, layers)
    return SQ.run_constraints(ents, params, did)


def validate_layers_py(ents, params, did, layers):
    rep = PY.Reporter(did)
    PY.schema_layer(ents, rep, include_model_validators=False)
    PY.dup_keys(ents, rep)
    for name in ("referential", "relational", "business"):
        if name in layers:
            fn = PY.LAYERS[name]
            fn(ents, rep) if name == "referential" else fn(ents, rep, params)
    if "business" in layers:
        PY.capacity(ents)
    return {"reports": rep.items, "capacity": []}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def scale(ents, k: int) -> dict:
    """정상 데이터를 k벌 복제: 업무 ID·참조에 접미사, record_uid 재생성, Unit은 공유. 관계·제약은 복제본 안에서 유지."""
    if k == 1:
        return copy.deepcopy(ents)
    idf = {"product_id", "material_id", "supplier_id", "bom_id", "order_id", "resource_id", "operation_id", "plan_id",
           "component_material_id", "component_product_id", "item_id", "derived_from_record_uid"}
    out = {e: ([copy.deepcopy(r) for r in rows] if e == "Unit" else []) for e, rows in ents.items()}
    for i in range(k):
        for e, rows in ents.items():
            if e == "Unit":
                continue
            for r in rows:
                n = dict(r)
                for f in idf:
                    if n.get(f) is not None:
                        n[f] = f"{n[f]}_{i}"
                n["record_uid"] = D.new_uid("scale", str(k), str(i), r["record_uid"])
                out[e].append(n)
    return out


def perf_child(method, k, layers, trace):
    cmd = [sys.executable, str(Path(__file__)), "--perf-child", method, str(k), ",".join(layers) if layers else "all"] + (["--trace"] if trace else [])
    t0 = time.perf_counter()
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=fo, stderr=fe)
        proc, peak = psutil.Process(p.pid), 0
        while p.poll() is None:
            try:
                peak = max(peak, proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True)))
            except psutil.Error:
                pass
            time.sleep(0.005)
        fo.seek(0)
        out = fo.read().decode("utf-8").strip().splitlines()
    res = json.loads(out[-1]) if out else {"ok": False}
    res.update({"wall_s": time.perf_counter() - t0, "peak_rss_mb": round(peak / 1048576, 1)})
    return res


def child_main(argv):
    import tracemalloc
    method, k, layers = argv[0], int(argv[1]), None if argv[2] == "all" else set(argv[2].split(","))
    trace = "--trace" in argv
    gt = D.load_gt()
    base = scale(gt["entities"], k)
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    c1 = next(d for d in spec["datasets"] if d["dataset_id"] == "C-1")
    # 오류가 섞인 큰 데이터: 복제본 0번에 C-1 연산을 같은 방식으로 적용 (업무 ID 접미사 _0)
    ops = json.loads(json.dumps(c1["ops"]))
    for op in ops:
        op["where"] = {kk: (f"{v}_0" if kk in ("order_id", "bom_id", "material_id", "item_id", "product_id") and isinstance(v, str) and k > 1 else v)
                       for kk, v in op.get("where", {}).items()}
    ents, _ = D.apply_ops(base, ops, f"perf{k}")
    if trace:
        tracemalloc.start()
    t0 = time.perf_counter()
    if method.startswith("sql"):
        import sqlite3
        con = sqlite3.connect(":memory:")
        SQ.staging(con, ents)
        load_s = time.perf_counter() - t0
        con.close()
        t1 = time.perf_counter()
        r = run_method(method, ents, gt["parameters"], "perf", layers)
        val_s = time.perf_counter() - t1
    else:
        load_s = 0.0
        t1 = time.perf_counter()
        r = run_method(method, ents, gt["parameters"], "perf", layers)
        val_s = time.perf_counter() - t1
    out = {"ok": True, "method": method, "scale": k, "records": sum(len(v) for v in ents.values()), "load_s": load_s, "validate_s": val_s,
           "reports": len([x for x in r["reports"] if x.get("severity") != "INFO"])}
    if trace:
        out["heap_peak_mb"] = round(tracemalloc.get_traced_memory()[1] / 1048576, 3)
    print(json.dumps(out))


def complexity():
    src = (ROOT / "scripts" / "e05_validate_python.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    funcs = {n.name: n.end_lineno - n.lineno + 1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    params = D.load_gt()["parameters"]
    qs = SQ.rule_queries(params)
    per_rule = {}
    for rule, ent, field, sql in qs:
        d = per_rule.setdefault(rule, {"queries": 0, "sql_chars": 0})
        d["queries"] += 1
        d["sql_chars"] += len(sql)
    ddl = SQ.constraint_ddl(params)
    return {"python": {"file_lines": len(src.splitlines()), "function_lines": funcs, "dependencies": ["pydantic (E01 모델 재사용)", "표준 라이브러리"]},
            "sql": {"rule_queries": len(qs), "generated_structure_queries": len(SQ.generated_queries()), "per_rule": per_rule,
                    "file_lines": len((ROOT / "scripts" / "e05_validate_sql.py").read_text(encoding="utf-8").splitlines()),
                    "constraint_ddl_tables": len(ddl), "constraint_ddl_chars": sum(len(s) for s in ddl), "dependencies": ["sqlite3 (표준, SQLite " + __import__("sqlite3").sqlite_version + ")"]}}


def e02_link(gt):
    """E02 파싱 결과(E02 출력)의 이관 4건 레코드를 정상 데이터에 넣어 E05 규칙이 잡는지 확인."""
    out_dir = ROOT / "results" / "E02_tabular_parsing" / "output"
    inj = {e["error_id"]: e for e in json.loads((ROOT / "data" / "canonical" / "injected_errors_v1.json").read_text(encoding="utf-8"))["errors"]}
    src = {v: json.loads((out_dir / f"invalid_vendor_{v.lower()}.json").read_text(encoding="utf-8")) for v in ("A", "B")}

    def find(vendor, ent, file, row):
        for r in src[vendor]["entities"][ent]:
            s = r["source"]
            rows = s.get("rows") or [int(s.get("row"))] if (s.get("rows") or s.get("row")) else []
            if s.get("file") == file and int(row) in [int(x) for x in rows]:
                return r["values"]
        return None
    cases = [("E01-ERR-009", "B", "Order", "V07", "replace", "order_id"), ("E01-ERR-010", "B", "BOMLine", "B01", "add", None),
             ("E01-ERR-011", "A", "BOM", "B02", "add", None), ("E01-ERR-012", "A", "Inventory", "V02", "replace", "item_id")]
    rows = []
    for eid, vendor, ent, rule, how, key in cases:
        e = inj[eid]
        vals = find(vendor, ent, e["file"], e["row_number"])
        ents = copy.deepcopy(gt["entities"])
        uid = None
        if vals is not None:
            if how == "replace":
                tgt = next(r for r in ents[ent] if r.get(key) == vals[key] and (ent != "Inventory" or r["item_type"] == vals["item_type"]))
                uid = tgt["record_uid"]
                tgt.update(vals)
            else:
                uid = D.new_uid("e02link", eid)
                ents[ent].append({"record_uid": uid, "origin_class": "SYNTHETIC", **({"line_type": "ITEM"} if ent == "BOMLine" else {}), **vals})
        res = {}
        for m in ("python_full", "sql_queries"):
            reps = run_method(m, ents, gt["parameters"], eid)["reports"]
            res[m] = any(r["rule_id"] == rule and r.get("record_uid") == uid for r in reps) if uid else False
        rows.append({"error_id": eid, "e02_scope": "E05 이관 (업무 규칙)", "e02_record_found": vals is not None, "expected_rule": rule,
                     "python_full_detected": res["python_full"], "sql_queries_detected": res["sql_queries"], "description": e["description"]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-perf", action="store_true")
    ap.add_argument("--perf-child", nargs="+")
    a, rest = ap.parse_known_args()
    if a.perf_child:
        child_main(a.perf_child + rest)
        return 0
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    gt = D.load_gt()
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha(SPEC) != man["eval_set_sha256"]:
        raise SystemExit("평가셋 해시 불일치 → 중단")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    mds = {d["dataset_id"]: d["dataset_sha256"] for d in man["datasets"]}
    OUT.mkdir(parents=True, exist_ok=True)
    results = {m: [] for m in METHODS}
    reports_all = {m: [] for m in METHODS}
    capacity_tables, extra = {}, {}
    for ds in spec["datasets"]:
        ents, _ = D.apply_ops(gt["entities"], ds["ops"], ds["dataset_id"])
        if D.dataset_sha256(ents) != mds[ds["dataset_id"]]:
            raise SystemExit(f"데이터셋 {ds['dataset_id']} 해시 불일치 → 중단")
        counts = {e: len(v) for e, v in ents.items()}
        for m in METHODS:
            r = run_method(m, ents, gt["parameters"], ds["dataset_id"])
            reports_all[m] += r["reports"]
            results[m].append(SC.score_dataset(ds, r["reports"], counts, IMPLEMENTED[m]))
            if ds["dataset_id"] == "clean":
                capacity_tables[m] = r.get("capacity", [])
                if m == "sql_constraints":
                    extra["sql_constraints_clean"] = {k: r[k] for k in ("fk_enabled", "rejected_rows", "unclassified_rejections")}
            if m == "sql_constraints":
                extra.setdefault("constraint_rejections", {})[ds["dataset_id"]] = {"rejected_rows": r["rejected_rows"], "unclassified": r["unclassified_rejections"]}
                results[m][-1]["fp_cascade_from_rejected_parent"] = cascade_fps(results[m][-1]["false_positives"], r["reports"], ents)
    agg = {m: SC.aggregate(results[m], IMPLEMENTED[m]) for m in METHODS}
    cap = {m: SC.capacity_check(capacity_tables[m], gt["expected"]) for m in ("python_full", "sql_queries")}
    link = e02_link(gt)
    extra["format_probe"] = format_probe(gt)
    perf = []
    if not a.skip_perf:
        for k in (1, 10, 50):
            for m in ("python_full", "sql_queries", "python_pydantic_only", "sql_constraints"):
                t = [perf_child(m, k, None, False) for _ in range(REPEATS)]
                h = [perf_child(m, k, None, True) for _ in range(REPEATS)]
                perf.append(summ(m, k, "all", t, h))
        for layers in (["schema"], ["schema", "referential"], ["schema", "referential", "relational"], ["schema", "referential", "relational", "business"]):
            for m in ("python_full", "sql_queries"):
                t = [perf_child(m, 10, layers, False) for _ in range(REPEATS)]
                perf.append(summ(m, 10, "+".join(layers), t, []))
    write(started, spec, man, results, agg, cap, link, perf, extra, reports_all)
    print(json.dumps({m: {"ERROR": agg[m]["ERROR"], "events": agg[m]["events_ERROR"]} for m in METHODS}, ensure_ascii=False))
    return 0


PROBE_NUM = ["1e3", " 12", "12 ", "+5", ".5", "5.", "1,000", "１２", "1_000", "0x10", "NaN", "Infinity", "-0", "00012", "12.50"]
PROBE_DATE = ["2026-11-1", "2026-1-15", " 2026-11-15", "2026-11-15T00:00", "20261115", "2026-13-01"]


def format_probe(gt):
    """평가셋 밖 보조 관찰: 숫자·날짜 경계 문자열을 Python(pydantic)과 SQL이 같게 판정하는지. 정답이 없으므로 채점하지 않고 판정 차이만 기록."""
    rows = []
    for ent, field, values in (("Material", "unit_cost", PROBE_NUM), ("Order", "order_date", PROBE_DATE)):
        for v in values:
            ents = copy.deepcopy(gt["entities"])
            ents[ent][0][field] = v
            got = {m: sorted({r["rule_id"] for r in run_method(m, ents, gt["parameters"], "probe")["reports"] if r["severity"] != "INFO" and r["entity"] == ent})
                   for m in ("python_full", "sql_queries")}
            rows.append({"entity": ent, "field": field, "value": v, **got, "agree": got["python_full"] == got["sql_queries"]})
    return rows


def cascade_fps(fps, reports, ents):
    """constraints 모드 오탐 중 '입력에는 부모가 있으나 부모 행이 먼저 적재 거부되어' 자식 FK가 실패한 건수 (연쇄 거부)."""
    n = 0
    for fp in fps:
        rep = next((x for x in reports if x["record_uid"] == fp["record_uid"] and x["rule_id"] == fp["rule_id"] and x["field"] == fp["field"]), None)
        fk = next(((p, pk) for f, p, pk in SQ.FKS.get(fp["entity"], []) if f == fp["field"]), None)
        if rep and fk and any(row.get(fk[1]) == rep["actual_value"] for row in ents.get(fk[0], [])):
            n += 1
    return n


def summ(m, k, layers, t, h):
    ok = [x for x in t if x.get("ok")]
    med = lambda xs: round(statistics.median(xs), 5) if xs else None
    return {"method": m, "scale": k, "layers": layers, "records": ok[0]["records"] if ok else None, "runs_ok": f"{len(ok)}/{len(t)}",
            "load_s_median": med([x["load_s"] for x in ok]), "validate_s_median": med([x["validate_s"] for x in ok]),
            "validate_s_min": round(min(x["validate_s"] for x in ok), 5) if ok else None, "validate_s_max": round(max(x["validate_s"] for x in ok), 5) if ok else None,
            "total_wall_s_median": med([x["wall_s"] for x in ok]), "peak_rss_mb_median": med([x["peak_rss_mb"] for x in ok]),
            "heap_peak_mb_median": med([x["heap_peak_mb"] for x in h if x.get("ok")]) if h else None, "reports": ok[0]["reports"] if ok else None}


def write(started, spec, man, results, agg, cap, link, perf, extra, reports_all):
    rows = []
    for m in METHODS:
        for sev in ("ERROR", "WARNING"):
            a = agg[m][sev]
            rows.append({"method": m, "severity": sev, **{k: a[k] for k in ("tp", "fp", "fn", "tn", "precision", "recall", "f1")},
                         "events_total": agg[m][f"events_{sev}"]["total"], "events_detected": agg[m][f"events_{sev}"]["detected_any"],
                         "fp_on_clean_and_pass": agg[m]["fp_on_clean_and_pass"] if sev == "ERROR" else "",
                         "rules_implemented": agg[m]["rule_coverage"]["implemented_rules"],
                         "rules_detected": agg[m]["rule_coverage"]["rules_detected_at_least_once"], "rules_with_expected": agg[m]["rule_coverage"]["rules_with_expected_items"]})
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
        (OUT / "perf.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    (OUT / "scores.json").write_text(json.dumps({"aggregate": agg, "datasets": results, "capacity_check": cap, "e02_link": link, "extra": extra},
                                                ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    (OUT / "reports.json").write_text(json.dumps(reports_all, ensure_ascii=False, indent=0, default=str) + "\n", encoding="utf-8", newline="\n")
    params = D.load_gt()["parameters"]
    (OUT / "queries.sql").write_text(SQ.all_sql_text(params), encoding="utf-8", newline="\n")
    (OUT / "complexity.json").write_text(json.dumps(complexity(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    from importlib.metadata import version
    import sqlite3
    meta = {"experiment_id": "E05", "status": "RUNNING", "run_timestamp": started, "python": sys.version.split()[0],
            "packages": {"pydantic": version("pydantic"), "psutil": version("psutil"), "sqlite": sqlite3.sqlite_version},
            "inputs": {"ground_truth_v2_sha256": D.GT_SHA256, "eval_set_sha256": man["eval_set_sha256"], "datasets": man["counts"], "expected_items": man["expected_items"]},
            "code_sha256": {f: sha(ROOT / "scripts" / f) for f in ("e05_dataset.py", "e05_validate_python.py", "e05_validate_sql.py", "e05_score.py", "e05_run.py",
                                                                   "e05_build_eval_set.py", "e01_models.py")},
            "rules_sha256": sha(ROOT / "configs" / "e05_validation_rules.json"),
            "measurement": "자식 프로세스 3회 중앙값. load_s = SQLite 적재(Python은 0, 이미 dict), validate_s = 규칙 실행, 피크 RSS = 런처+인터프리터(psutil 5ms), heap = tracemalloc(별도 3회)",
            "scales": {"S": 1, "M": 10, "L": 50}, "external_calls": 0,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}
    (OUT / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (OUT / "failures.md").write_text(failures_md(results, agg, extra), encoding="utf-8", newline="\n")
    (OUT / "summary.md").write_text(summary_md(meta, agg, cap, link, perf, extra), encoding="utf-8", newline="\n")


def failures_md(results, agg, extra):
    L = ["# E05 실패·오탐·미탐 기록 (자동 생성, scripts/e05_run.py)", "",
         "판정 기준: scripts/e05_score.py. 수동 조정 없음. 정답셋 정의 한계로 보이는 항목도 판정대로 남긴다.", ""]
    for m in METHODS:
        a = agg[m]
        L += [f"## {m}", "", f"- ERROR TP/FP/FN: {a['ERROR']['tp']}/{a['ERROR']['fp']}/{a['ERROR']['fn']}, WARNING TP/FP/FN: {a['WARNING']['tp']}/{a['WARNING']['fp']}/{a['WARNING']['fn']}",
              f"- 보고 분류: {a['classes']}", f"- 한 번도 검출하지 못한 기대 규칙: {', '.join(a['rule_coverage']['never_detected']) or '없음'}"]
        if m == "sql_constraints":
            casc = sum(r.get("fp_cascade_from_rejected_parent", 0) for r in results[m])
            L.append(f"- 오탐 중 연쇄 거부(부모 행이 먼저 거부되어 자식 FK 실패): {casc}/{a['ERROR']['fp'] + a['WARNING']['fp']}")
            rej = {k: v for k, v in extra["constraint_rejections"].items() if v["rejected_rows"]}
            L.append(f"- 적재 거부 행 수(데이터셋별, 0 제외): {rej}")
        L.append("")
        fps = [(r["dataset_id"], f) for r in results[m] for f in r["false_positives"]]
        if fps:
            L += ["### 오탐", "", "| 데이터셋 | 규칙 | 엔터티 | 필드 | 건수 |", "|---|---|---|---|---|"]
            cnt = {}
            for did, f in fps:
                k = (did, f["rule_id"], f["entity"], f["field"])
                cnt[k] = cnt.get(k, 0) + 1
            L += [f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | {v} |" for k, v in sorted(cnt.items())]
            L.append("")
        fns = [(r["dataset_id"], x) for r in results[m] for sev in ("ERROR", "WARNING") for x in r["by_severity"][sev]["fn_items"]]
        if fns:
            L += ["### 미탐지", "", "| 데이터셋 | 규칙 | 필드 | record_uid |", "|---|---|---|---|"]
            L += [f"| {d} | {x['rule']} | {x['field']} | {x['uid']} |" for d, x in fns]
            L.append("")
        parts = [(r["dataset_id"], p) for r in results[m] for p in r["partial"]]
        if parts:
            L += ["### 부분 탐지 (기대 레코드에 다른 규칙·필드로 보고)", ""] + [f"- {d}: {p['rule_id']} {p['entity']}.{p['field']}" for d, p in parts] + [""]
    return "\n".join(L)


def summary_md(meta, agg, cap, link, perf, extra):
    L = ["# E05 결과 요약 (자동 생성)", "", f"- 상태: {meta['status']} (검토 전). 실행: {meta['run_timestamp']}, Python {meta['python']}, pydantic {meta['packages']['pydantic']}, SQLite {meta['packages']['sqlite']}",
         f"- 입력: ground_truth_v2 {meta['inputs']['ground_truth_v2_sha256'][:12]}…, eval_set_v1 {meta['inputs']['eval_set_sha256'][:12]}…, 데이터셋 {meta['inputs']['datasets']}, 기대 항목 {meta['inputs']['expected_items']}",
         "- 외부 API 호출 0. 합성 데이터만 사용.",
         "- **해석 주의**: 평가셋(정답)과 검증기를 같은 규칙 카탈로그로 같은 작성자가 만들었다. 정답은 검증기 출력과 독립으로 정했지만, "
         "100% 수치는 '카탈로그에 적은 규칙을 구현이 그대로 잡는가'(구현 일치도)이며 처음 보는 오류 유형·실제 데이터에 대한 일반화 성능이 아니다.",
         "", "## 정확도 (규칙 단위, 심각도별)", "",
         "| 방식 | 심각도 | TP | FP | FN | Precision | Recall | F1 | 사건 검출 | 규칙 검출/기대 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m in METHODS:
        for sev in ("ERROR", "WARNING"):
            a, e, c = agg[m][sev], agg[m][f"events_{sev}"], agg[m]["rule_coverage"]
            L.append(f"| {m} | {sev} | {a['tp']} | {a['fp']} | {a['fn']} | {a['precision']} | {a['recall']} | {a['f1']} | {e['detected_any']}/{e['total']} | "
                     f"{c['rules_detected_at_least_once']}/{c['rules_with_expected_items']} |")
    L += ["", "TN은 (규칙, 레코드) 쌍 근사이므로 참고값이다. 정상·경계 통과 데이터 오탐: " + ", ".join(f"{m} {agg[m]['fp_on_clean_and_pass']}" for m in METHODS), "",
          "## 오류 유형별 사건 검출 (단일 주입)", "", "| 오류 코드 | " + " | ".join(METHODS) + " |", "|---|" + "---|" * len(METHODS)]
    for code in agg["python_full"]["event_recall_by_error_code"]:
        L.append(f"| {code} | " + " | ".join(agg[m]["event_recall_by_error_code"].get(code, "-") for m in METHODS) + " |")
    L += ["", "## 생산능력(V13) 계산 대조 — GT plan_evaluation", ""] + [f"- {m}: {v}" for m, v in cap.items()]
    L += ["", "## E02 이관 오류 4건 (E02 파서 출력 레코드 사용)", "", "| 오류 | 기대 규칙 | E02 레코드 | python_full | sql_queries |", "|---|---|---|---|---|"]
    L += [f"| {x['error_id']} | {x['expected_rule']} | {x['e02_record_found']} | {x['python_full_detected']} | {x['sql_queries_detected']} |" for x in link]
    probe = extra.get("format_probe", [])
    L += ["", "## 보조 관찰: 형식 경계 문자열 (평가셋 밖, 채점 안 함)", "", "| 엔터티.필드 | 값 | python_full | sql_queries | 일치 |", "|---|---|---|---|---|"]
    L += [f"| {p['entity']}.{p['field']} | `{p['value']!r}` | {','.join(p['python_full']) or '-'} | {','.join(p['sql_queries']) or '-'} | {p['agree']} |" for p in probe]
    if perf:
        L += ["", "## 성능 (자식 프로세스 3회 중앙값)", "", "| 방식 | 배율 | 계층 | 레코드 | 적재 s | 검증 s | 전체 s | 피크 RSS MB | heap MB |", "|---|---|---|---|---|---|---|---|---|"]
        L += [f"| {p['method']} | {p['scale']} | {p['layers']} | {p['records']} | {p['load_s_median']} | {p['validate_s_median']} | {p['total_wall_s_median']} | "
              f"{p['peak_rss_mb_median']} | {p['heap_peak_mb_median'] if p['heap_peak_mb_median'] is not None else '미측정'} |" for p in perf]
        L += ["", "heap(tracemalloc)은 Python 할당만 잡는다. pydantic-core(Rust)·SQLite(C) 내부 할당은 포함되지 않으므로 방식 간 비교 지표로 쓰지 않는다."]
    else:
        L += ["", "## 성능", "", "미측정 (--skip-perf)"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
