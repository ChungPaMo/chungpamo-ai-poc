"""개인 사전 PoC 최종 정합성 검사 — 보고서에 쓴 핵심 수치를 원본 결과 파일에서 다시 읽어 대조한다 (결과 파일은 읽기만 함).

    .\\.venv\\Scripts\\python.exe scripts\\poc_consistency_check.py

결과: results/poc_final/consistency_check.json. 불일치는 고치지 않고 기록한다.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUT = R / "poc_final"


def J(p):
    return json.loads((R / p).read_text(encoding="utf-8"))


def frac_sum(rows, col):
    n = d = 0
    for r in rows:
        a, b = r[col].split("/")
        n, d = n + int(a), d + int(b)
    return f"{n}/{d}"


def main() -> int:
    checks = []

    def c(exp, report, claim, actual, expected):
        checks.append({"experiment": exp, "report": report, "claim": claim, "actual": str(actual), "expected": str(expected), "ok": str(actual) == str(expected)})

    # E03 — holdout PDF (공식 정답) pdfplumber v2
    rows = [r for r in csv.DictReader((R / "E03_document_parsers/external_holdout_v2/metrics.csv").open(encoding="utf-8")) if r["parser"] == "pdfplumber"]
    c("E03", "e09 §2·§4", "holdout 표 재현율", frac_sum(rows, "table_detection.recall"), "6/6")
    c("E03", "e09 §2·§4", "holdout 셀 텍스트(격자)", frac_sum(rows, "cells.text_loose_grid"), "625/676")
    c("E03", "e09 §2·§4", "holdout 병합", frac_sum(rows, "cells.merge_spans"), "23/30")
    # E04 — 기존 Upstage 2회
    pre = J("E04_upstage_preflight/preflight_summary.json")
    c("E04", "e04 §2", "P-02 Upstage 호출 수·시간", f"{pre['call']['count']}회 {pre['call']['elapsed_seconds']}s", "1회 7.904s")
    cells = pre["comparison_vs_e03_truth"]["cells_all_fragments"]
    c("E04", "e04 §2", "P-02 Upstage 셀", f"{cells['numerator']}/{cells['denominator']}" if isinstance(cells, dict) else cells, "248/248")
    diag = J("E03_document_parsers/upstage_diag/X-DV-P04_comparison.json")
    c("E04", "e04 §3", "X-DV-P04 Upstage HTML 병합", diag["metrics"]["upstage_standard_html"]["병합 셀"], "4/6")
    c("E04", "e04 §3", "X-DV-P04 직접 v2 병합", diag["metrics"]["direct_v2_pdfplumber"]["병합 셀"], "2/6")
    c("E04", "e04 §3", "X-DV-P04 호출 시간", diag["call"]["elapsed_seconds"], "9.845")
    # E05
    s5 = J("E05_schema_sql/scores.json")["aggregate"]
    for m, exp in (("python_full", "99/0/0"), ("sql_queries", "99/0/0"), ("python_pydantic_only", "31/0/68"), ("sql_constraints", "50/114/49")):
        e = s5[m]["ERROR"]
        c("E05", "e05 report §5·§6", f"{m} TP/FP/FN", f"{e['tp']}/{e['fp']}/{e['fn']}", exp)
    # E06
    a6 = J("E06_rdf_shacl/accuracy.json")
    e = a6["aggregate"]["shacl_pyshacl"]["ERROR"]
    c("E06", "e06 report §4", "pyshacl TP/FP/FN", f"{e['tp']}/{e['fp']}/{e['fn']}", "99/0/0")
    c("E06", "e06 report §4", "E05 Python과 차이 데이터셋", len(a6["e05_comparison"]["python_full"]["datasets_differing_from_shacl"]), 0)
    c("E06", "e06 report §4", "Core 비교 제약 중단 데이터셋", len(a6["core_compare_crashes"]), 2)
    perf = {(p["method"], p["scale"]): p for p in J("E06_rdf_shacl/perf_v2/perf.json")}
    c("E06", "e06 report §8", "L pyshacl 검증 s", perf[("shacl_pyshacl", 50)]["validate_s"], "4188.9484")
    c("E06", "e06 report §8", "L pyshacl 피크 MB(자체)", perf[("shacl_pyshacl", 50)]["self_peak_mb"], "727.1")
    c("E06", "e06 report §8", "L hybrid 검증 s", perf[("shacl_hybrid", 50)]["validate_s"], "1540.2522")
    c("E06", "e06 report §8", "L Python 검증 s", perf[("python_full", 50)]["validate_s"], "0.2013")
    c("E06", "e06 report §8", "L SQLite 검증 s", perf[("sql_queries", 50)]["validate_s"], "0.3148")
    c("E06", "e06 report §8", "L 트리플", perf[("shacl_pyshacl", 50)]["triples"], 231193)
    c("E06", "e06 report §8", "성능 3회 성공", all(p["runs_ok"] == "3/3" for p in perf.values()), True)
    q = J("E06_rdf_shacl/queries.json")
    c("E06", "e06 report §6", "Q1~Q5 정답 (세 방식)", all(all(v["correct"] == v["expected_items"] for v in q["methods"][m]["score"].values()) for m in ("python", "sqlite", "sparql")), True)
    c("E06", "e06 report §6", "판별 사례 naive 오답", q["discrimination_inactive_bom"]["answers"]["sparql_naive"], ["P0"])
    # E10
    v1 = J("E10_erp_mapping/results.json")
    for pol in ("ideal", "rubber_stamp"):
        w = v1[pol]["score"]["wrong_value_commit_rate"]
        c("E10", "e10_m13_fix §3", f"v1 평가셋 잘못된 반영 ({pol})", f"{w['wrong']}/{w['committed']}", "1/7")
        c("E10", "e10_m13_fix §3", f"v1 안전성 ({pol})", f"{v1[pol]['score']['safety_tests']['passed']}/{v1[pol]['score']['safety_tests']['total']}", "13/13")
    for d in ("v2_eval_review", "v2_eval_auto", "v2_conflict_review", "v2_conflict_auto"):
        r = J(f"E10_erp_mapping/{d}/results.json")
        for pol in ("ideal", "rubber_stamp"):
            s = r[pol]["score"]
            c("E10", "e10_m13_fix §3", f"{d} 잘못된 반영 ({pol})", s["wrong_value_commit_rate"]["wrong"], 0)
            c("E10", "e10_m13_fix §3", f"{d} 오류 있는 후보 자동 승인 ({pol})", s["auto_approved_with_issues"], 0)
            c("E10", "e10_m13_fix §3", f"{d} 승인 없는 본 테이블 행 ({pol})", s["master_rows_without_approval_or_history"], 0)
    vc = J("E10_erp_mapping/v1_conflict/results.json")["ideal"]["score"]["wrong_value_commit_rate"]
    c("E10", "e10_m13_fix §3", "v1 충돌 세트 잘못된 반영", f"{vc['wrong']}/{vc['committed']}", "1/4")
    er = J("E10_erp_mapping/v2_eval_review/results.json")["ideal"]["score"]["state_checks"]
    c("E10", "e10_m13_fix §3 †", "v2 기본 정책 상태 검사 (X02 실패 1건 기록)", f"{er['passed']}/{er['total']}", "23/24")
    # E11
    e11 = J("E11_contract/results.json")
    c("E11", "e11 report §2", "계약 검증", f"{e11['summary']['passed']}/{e11['summary']['total']}", "11/11")
    c("E11", "e11 report §2", "T-01 계산", e11["t01"]["calc"], {"required_production": "900", "required_material_kg": "1800", "material_shortage_kg": "300",
                                                                  "capacity_shortfall_units": "100"})
    c("E11", "e11 report §2", "E01 계획안 판정", [p["evaluation"]["feasibility"] for p in e11["e01_plans"]], ["INFEASIBLE"] * 3)
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"checked": len(checks), "mismatches": [x for x in checks if not x["ok"]], "checks": checks}
    (OUT / "consistency_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print({"checked": len(checks), "mismatches": len(res["mismatches"])})
    for x in res["mismatches"]:
        print("MISMATCH", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
