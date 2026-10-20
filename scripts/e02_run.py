"""E02 실행: 입력 해시 검증 → 파싱(정상·오류 입력) → 3회 반복 성능 측정 → 채점 → 결과 기록 → pytest.

    .\\.venv\\Scripts\\python.exe scripts\\e02_run.py

상태는 RUNNING으로 기록한다 (ChatGPT·사용자 검토 대기). 입력 해시가 E01 매니페스트와 다르면 즉시 중단한다.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "results" / "E02_tabular_parsing"
GT_SHA256 = "262dbe75dbfaf8c0c32003144d62e0b2057c61187dce4b548a457cf8819fc48e"
REPEATS = 3

from parsers.vendor_parser import load_config, parse_vendor  # noqa: E402

import check_environment as ce  # noqa: E402
import e02_grade as G  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_inputs() -> list[dict]:
    """E01 매니페스트와 입력 파일 해시 대조. 하나라도 다르면 중단."""
    rows = list(csv.DictReader(open(ROOT / "results" / "E01_dataset" / "dataset_manifest.csv", encoding="utf-8")))
    checked, bad = [], []
    for r in rows:
        if not r["path"].startswith(("data/vendor_", "data/invalid/", "data/canonical/")) or r["git_tracked"] != "예":
            continue
        actual = sha(ROOT / r["path"])
        checked.append({"path": r["path"], "sha256": actual, "matches_e01_manifest": actual == r["sha256"]})
        if actual != r["sha256"]:
            bad.append(r["path"])
    gt = sha(ROOT / "data" / "canonical" / "ground_truth_v2.json")
    if gt != GT_SHA256:
        bad.append(f"ground_truth_v2.json ({gt})")
    if bad:
        raise SystemExit(f"입력 해시 불일치 → 실험 중단: {bad}")
    return checked


def perf(vendor: str, dataset: str, trace: bool) -> dict:
    cmd = [sys.executable, str(ROOT / "scripts" / "e02_parse_one.py"), vendor, dataset] + (["--trace-mem"] if trace else [])
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc = psutil.Process(p.pid)
    peak = 0
    # Windows venv의 python.exe는 실제 인터프리터를 자식 프로세스로 띄우는 런처이므로 자식까지 합산한다
    while p.poll() is None:
        try:
            total = proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True))
            peak = max(peak, total)
        except psutil.Error:
            pass
        time.sleep(0.005)
    out, err = p.communicate()
    wall = time.perf_counter() - t0
    if p.returncode != 0:
        return {"ok": False, "error": err.decode("utf-8", "replace")[-500:]}
    res = json.loads(out.decode("utf-8"))
    res.update({"ok": True, "process_wall_seconds": wall, "peak_rss_bytes": peak})
    return res


def main() -> int:
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = verify_inputs()
    cfg_path = ROOT / "configs" / "e02_vendor_mapping.json"
    cfg = load_config(cfg_path)
    outputs = {}
    for ds in ("clean", "invalid"):
        outputs[ds] = {v: parse_vendor(cfg, v, ROOT / "data", invalid=(ds == "invalid")) for v in ("A", "B")}
        for v, o in outputs[ds].items():
            p = OUT / "output" / f"{ds}_vendor_{v.lower()}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    # 성능 (3회 × 시간/RSS, 3회 × Python 힙)
    perf_runs = {}
    for ds in ("clean", "invalid"):
        for v in ("A", "B"):
            perf_runs[(ds, v)] = {"time": [perf(v, ds, False) for _ in range(REPEATS)],
                                  "mem": [perf(v, ds, True) for _ in range(REPEATS)]}
    # 채점
    T = G.Truth()
    graded = {ds: G.grade_dataset(T, outputs[ds], ds) for ds in ("clean", "invalid")}
    headers = G.grade_headers(outputs["clean"])
    det = {}
    for ds in ("clean", "invalid"):
        # 오탐률 분모: 원본 행에 대응하는 레코드(BOM 헤더처럼 여러 행을 묶은 레코드 제외)와 그 셀 수
        recs = [r for o in outputs[ds].values() for rows in o["entities"].values() for r in rows if "cells" in r["source"]]
        cells = sum(len(r["source"].get("cells", {})) for r in recs)
        det[ds] = G.grade_detection(T, outputs[ds], ds, cells, len(recs))
    # metrics.csv
    rows = []
    for ds in ("clean", "invalid"):
        for m in graded[ds]["per_file"]:
            label = m["file"].split("/", 1)[1] + (f":{m['sheet']}" if m["sheet"] else "")
            pr = perf_runs[(ds, m["vendor"])]
            t = [r["per_file"][label]["seconds"] for r in pr["time"] if r["ok"] and label in r["per_file"]]
            h = [r["per_file"][label]["py_heap_peak_bytes"] for r in pr["mem"] if r["ok"] and label in r["per_file"]]
            rss = [r["peak_rss_bytes"] for r in pr["time"] if r["ok"]]
            g = lambda k: m.get(k, 0)
            rows.append({
                "dataset": ds, "vendor": m["vendor"], "file": m["file"], "sheet": m["sheet"], "entity": m["entity"],
                "run_ok": m["run_ok"], "output_generated": m["output_generated"],
                "encoding_detected": m["encoding_detected"], "encoding_expected": m["encoding_expected"], "delimiter": m["delimiter"],
                "records_expected": g("records_expected"), "records_parsed": g("records_parsed"), "records_missing": g("records_missing"),
                "records_duplicate": g("records_duplicate"), "records_extra": g("records_extra"),
                "required_match": g("required_match"), "required_total": g("required_total"),
                "required_match_rate": G.rate(g("required_match"), g("required_total")),
                "fields_match": g("fields_match"), "fields_total": g("fields_total"),
                "qty_unit_match": g("qty_unit_match"), "qty_unit_total": g("qty_unit_total"),
                "qty_unit_preservation": G.rate(g("qty_unit_match"), g("qty_unit_total")),
                "number_match": g("number_match"), "number_total": g("number_total"),
                "number_preservation": G.rate(g("number_match"), g("number_total")),
                "date_match": g("date_match"), "date_total": g("date_total"),
                "date_preservation": G.rate(g("date_match"), g("date_total")),
                "id_match": g("id_match"), "id_total": g("id_total"), "id_mapping_accuracy": G.rate(g("id_match"), g("id_total")),
                "trace_success": g("trace_success"), "trace_total": g("trace_total"),
                "trace_success_rate": G.rate(g("trace_success"), g("trace_total")),
                "time_median_s": f"{statistics.median(t):.6f}" if len(t) == REPEATS else "측정실패",
                "time_min_s": f"{min(t):.6f}" if t else "측정실패", "time_max_s": f"{max(t):.6f}" if t else "측정실패",
                "py_heap_peak_median_mb": f"{statistics.median(h) / 1048576:.3f}" if len(h) == REPEATS else "측정실패",
                "bundle_peak_rss_median_mb": f"{statistics.median(rss) / 1048576:.1f}" if len(rss) == REPEATS else "측정실패",
                "repeats": REPEATS,
            })
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    (OUT / "metrics.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    # pytest
    xml_path = OUT / "pytest_report.xml"
    xml_path.unlink(missing_ok=True)
    py = subprocess.run([sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider", f"--junitxml={xml_path}"], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / "pytest_output.txt").write_text(ce.mask_sensitive(py.stdout + ("\n--- stderr ---\n" + py.stderr if py.stderr else "")),
                                           encoding="utf-8", newline="\n")
    tests = None
    if xml_path.exists():
        suite = ET.parse(xml_path).getroot()
        suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
        t = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
        tests = {"total": t["tests"], "passed": t["tests"] - t["failures"] - t["errors"] - t["skipped"], "failed": t["failures"],
                 "errors": t["errors"], "skipped": t["skipped"]}
        xml_path.write_text(ce.sanitize_junit_xml(xml_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        ET.parse(xml_path)
    # 설정 작업량
    codes = sum(len(t) for v in cfg["vendors"].values() for t in v["codes"].values())
    colspecs = sum(len(f.get("columns", {})) for v in cfg["vendors"].values() for f in v["files"])
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    git_status = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--short"], cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8").stdout.splitlines()
    meta = {
        "experiment_id": "E02", "experiment_name": "CSV/Excel 직접 파싱 (1차 Baseline: 표준 csv + openpyxl)",
        "status": "RUNNING",
        "status_note": "1차 Baseline(표준 csv + openpyxl) 완료 — 2026-10-20 사용자 승인(DEC-20261020-09). E02 전체는 RUNNING "
                       "(pandas 비교는 D-016 보류)",
        "phases": {"phase1_baseline_csv_openpyxl": "COMPLETED", "phase2_pandas_comparison": "보류 (D-016, pandas 미설치)"},
        "scope_note": "주입 오류 13건 중 9건이 파서 범위, 4건(E01-ERR-009~012)은 업무 규칙 오류로 E05 검증 대상. "
                      "경고(ERR-UNRESOLVED)는 정탐·오탐과 별도 집계",
        "mapping_note": "코드 매핑 41항목은 수작업 설정이며, ID 매핑 정확도는 설정 적용 정확도다. 자동 매핑 정확도는 측정하지 않음",
        "run_timestamp": started, "python": sys.version.split()[0],
        "packages": {"openpyxl": __import__("openpyxl").__version__, "psutil": psutil.__version__},
        "git": {"base_commit": git_head, "uncommitted_changes": git_status},
        "inputs": {"ground_truth_v2_sha256": GT_SHA256, "files_verified_against_e01_manifest": len(inputs),
                   "all_match": all(i["matches_e01_manifest"] for i in inputs), "files": inputs},
        "config": {"file": "configs/e02_vendor_mapping.json", "sha256": sha(cfg_path), "code_mapping_entries": codes,
                   "column_specs": colspecs, "source": cfg["_meta"]["source"], "limitation": cfg["_meta"]["limitation"]},
        "measurement": {"repeats": REPEATS,
                        "time": "자식 프로세스 안에서 파일별 time.perf_counter (tracemalloc 미사용 실행 3회의 중앙값)",
                        "py_heap": "tracemalloc 파일별 피크 − 파일 시작 시점 사용량 (별도 3회 실행의 중앙값, Python 힙만 — C 확장 내부 메모리 일부 미포함)",
                        "rss": "업체·데이터셋 묶음 프로세스의 피크 RSS = venv 런처 + 실제 인터프리터 자식 프로세스 합 (psutil 5ms 폴링, "
                               "인터프리터·라이브러리 적재 포함, 파일별 분리 불가)"},
        "perf_bundles": {f"{ds}_{v}": {"total_seconds_median": statistics.median(r["total_seconds"] for r in pr["time"] if r["ok"]),
                                       "peak_rss_mb_median": statistics.median(r["peak_rss_bytes"] for r in pr["time"] if r["ok"]) / 1048576,
                                       "failed_runs": sum(not r["ok"] for r in pr["time"] + pr["mem"])}
                         for (ds, v), pr in perf_runs.items()},
        "headers": headers,
        "detection": {ds: {k: det[ds][k] for k in ("reports", "warnings", "warning_codes", "by_type", "field_fp", "record_fp")}
                      for ds in det},
        "tests": tests,
    }
    (OUT / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    (OUT / "detection_detail.json").write_text(json.dumps(det, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    (OUT / "failures.md").write_text(failures_md(graded, det), encoding="utf-8", newline="\n")
    (OUT / "summary.md").write_text(summary_md(meta, rows, det, headers), encoding="utf-8", newline="\n")
    print(json.dumps({"tests": tests, "detection_invalid": det["invalid"]["by_type"],
                      "clean_reports": det["clean"]["reports"]}, ensure_ascii=False))
    return 0 if tests and not tests["failed"] and not tests["errors"] else 1


def failures_md(graded: dict, det: dict) -> str:
    L = ["# E02 실패·미탐지·오탐 사례", "", "> scripts/e02_run.py가 채점 결과로 자동 생성. 원인 설명 중 '추정'은 검증 전 가설이다.", "",
         "## 1. 정상 입력 변환 불일치", ""]
    mism = [(m["vendor"], m["file"], m["sheet"], x) for m in graded["clean"]["per_file"] for x in m["_mismatches"]]
    for v, f, s, x in mism:
        detail = x["issue"] if "issue" in x else f"{x['field']}: 파서={x['got']} / 정답={x['want']}"
        L.append(f"- {v} `{f}` {s} 행 {x.get('row')}: {x['entity']} {x['key']} — {detail}")
    if not mism:
        L.append("- 없음")
    L += ["", "## 2. 실행 실패 (run_ok = False)", ""]
    fails = [m for ds in graded for m in graded[ds]["per_file"] if not m["run_ok"]]
    L += [f"- {m['dataset']} {m['vendor']} `{m['file']}` {m['sheet']}" for m in fails] or ["- 없음"]
    L += ["", "## 3. 주입 오류 미탐지", "", "| 오류 ID | 유형 | 파일 | 행 | 필드 | 범위 | 원인 |", "|---|---|---|---|---|---|---|"]
    for p in det["invalid"]["per_error"]:
        if not p["detected"]:
            cause = p["e05_reason"] or "파서 진단 규칙 미흡 (조사 필요)"
            L.append(f"| {p['error_id']} | {p['error_code']} | `{p['file']}` {p['sheet']} | {p['row']} | {p['field']} | {p['scope']} | {cause} |")
    L += ["", "## 4. 오탐 (주입 목록에 대응하지 않는 오류 보고)", ""]
    for ds in ("clean", "invalid"):
        fps = det[ds]["false_positives"]
        L.append(f"- {ds}: {len(fps)}건")
        L += [f"  - `{d['file']}` {d['sheet']} 행 {d['row']} {d['column']} {d['error_code']}: {d['message']}" for d in fps]
    L += ["", "## 5. 경고 (오류로 채점하지 않음)", ""]
    for ds in ("clean", "invalid"):
        L.append(f"- {ds}: {det[ds]['warnings']}건 {det[ds]['warning_codes']}")
    if det["invalid"]["warnings"]:
        L.append("  - 원인: 자재 시트 헤더 손상(E01-ERR-006)으로 자재 마스터를 읽지 못해, 공급조건 시트의 최소주문량 단위를 확정할 수 없음 (파생 영향)")
    L += ["", "## 6. 부분 탐지·중복 보고", ""]
    L += [f"- {p['error_id']}: 정탐 보고 {p['reports']}건 (중복 {p['duplicate_reports']}), 부분 탐지 {p['partial']}건"
          for p in det["invalid"]["per_error"] if p["duplicate_reports"] or p["partial"]] or ["- 없음"]
    L += ["", "## 7. 시험 실행 중 수정 이력 (본 측정 전)", "",
          "- 1차 시험 채점에서 E01-ERR-004(ERR-UNIT, A bom.csv 21행)는 파서가 오류를 감지했지만 수량 열(`qty_per`)에 기록해 "
          "'부분 탐지'로 채점됨. 실제로 바뀐 값은 단위 열(`uom`)이므로, 단위 차원 불일치를 단위 열에 기록하도록 파서를 수정한 뒤 본 측정을 실행함.",
          "- 이 수정은 주입 목록을 보고 한 것이므로, 같은 유형의 새 오류에 대한 일반화 성능은 E02 결과만으로 확인되지 않는다.",
          "- 측정 방식 수정: 첫 본 측정에서 피크 RSS가 3.3MB로 나와 조사한 결과, Windows venv의 python.exe가 실제 인터프리터를 "
          "자식 프로세스로 띄우는 런처여서 런처만 관찰하고 있었다. 자식 프로세스 RSS를 합산하도록 고쳤다 (약 28MB).",
          "- 측정 방식 수정: 파일별 Python 힙 피크가 앞 파일 결과를 포함해 누적되어 있어, 파일 시작 시점 사용량을 뺀 증가분으로 바꿨다."]
    return "\n".join(L) + "\n"


def summary_md(meta: dict, rows: list[dict], det: dict, headers: list[dict]) -> str:
    L = ["# E02 결과 요약 — CSV/Excel 직접 파싱 (1차 Baseline)", "",
         f"> 자동 생성. 상태 **{meta['status']}** ({meta['status_note']}). 실행 {meta['run_timestamp']}, 기준 커밋 `{meta['git']['base_commit']}`", "",
         f"- 파서: 표준 csv + openpyxl {meta['packages']['openpyxl']} (pandas 미사용)",
         f"- 입력: E01 매니페스트 대조 {meta['inputs']['files_verified_against_e01_manifest']}개 파일 해시 일치 = {meta['inputs']['all_match']}, 정답셋 v2 `{GT_SHA256[:12]}…`",
         f"- 설정: `{meta['config']['file']}` — 코드 대응 {meta['config']['code_mapping_entries']}항목, 열 정의 {meta['config']['column_specs']}개 (수작업)",
         f"- **매핑 한계**: {meta['mapping_note']}",
         f"- **오류 범위**: {meta['scope_note']}",
         f"- 단계: 1차 Baseline = {meta['phases']['phase1_baseline_csv_openpyxl']}, 2차 pandas 비교 = {meta['phases']['phase2_pandas_comparison']}", "",
         "## 1. 정상 입력 파일별 정확도", "",
         "| 업체 | 파일 | 시트 | 실행 | 출력 | 인코딩(감지/기대) | 레코드(기대/파싱/누락/중복) | 필수 필드 | 숫자·단위 | 숫자 | 날짜 | ID 매핑 | 위치 역추적 | 시간 중앙값(s) | 힙 피크(MB) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["dataset"] != "clean":
            continue
        L.append(f"| {r['vendor']} | {r['file']} | {r['sheet']} | {r['run_ok']} | {r['output_generated']} | {r['encoding_detected'] or '-'}/{r['encoding_expected'] or '-'} | "
                 f"{r['records_expected']}/{r['records_parsed']}/{r['records_missing']}/{r['records_duplicate']} | {r['required_match_rate']} | "
                 f"{r['qty_unit_preservation']} | {r['number_preservation']} | {r['date_preservation']} | {r['id_mapping_accuracy']} | "
                 f"{r['trace_success_rate']} | {r['time_median_s']} | {r['py_heap_peak_median_mb']} |")
    L += ["", "## 2. 병합 헤더 복원 (Vendor B xlsx)", "", "| 시트 | 헤더 행 수 | 정확 셀 |", "|---|---|---|"]
    L += [f"| {h['sheet']} | {h['header_rows']} | {G.rate(h['cells_correct'], h['cells_total'])} |" for h in headers]
    inv = det["invalid"]
    L += ["", "## 3. 오류 입력 탐지 (주입 13건)", "", "| 유형 | 주입 | 탐지 | E02 범위 | E02 범위 탐지율 | 오탐 보고 |", "|---|---|---|---|---|---|"]
    for k, t in inv["by_type"].items():
        L.append(f"| {k} | {t.get('injected', 0)} | {t.get('detected', 0)} | {t.get('in_e02_scope', 0)} | "
                 f"{G.rate(t.get('detected_in_scope', 0), t.get('in_e02_scope', 0))} | {t.get('false_positive_reports', 0)} |")
    tot_in = sum(t.get("in_e02_scope", 0) for t in inv["by_type"].values())
    tot_det = sum(t.get("detected_in_scope", 0) for t in inv["by_type"].values())
    all_det = sum(t.get("detected", 0) for t in inv["by_type"].values())
    L += ["", f"- 전체 탐지율(13건 기준): {G.rate(all_det, 13)} / E02 범위 탐지율: {G.rate(tot_det, tot_in)} / E05 이관: {13 - tot_in}건",
          f"- 오탐률 (오류 입력): 필드 수준 {G.rate(inv['field_fp']['numerator'], inv['field_fp']['denominator'])}, "
          f"레코드 수준 {G.rate(inv['record_fp']['numerator'], inv['record_fp']['denominator'])}",
          f"- 오탐률 (정상 입력): 필드 수준 {G.rate(det['clean']['field_fp']['numerator'], det['clean']['field_fp']['denominator'])}, "
          f"레코드 수준 {G.rate(det['clean']['record_fp']['numerator'], det['clean']['record_fp']['denominator'])}",
          f"- 경고(정탐·오탐과 별도, 채점 제외): 정상 {det['clean']['warnings']}건, 오류 입력 {inv['warnings']}건 {inv['warning_codes']} "
          "— 자재 시트 헤더 손상(E01-ERR-006)의 파생 영향으로 공급조건 최소주문량 단위 미확정", "",
          "## 4. 성능 (3회 반복)", "", "| 묶음 | 전체 처리시간 중앙값(s) | 피크 RSS 중앙값(MB) | 실패 실행 |", "|---|---|---|---|"]
    L += [f"| {k} | {v['total_seconds_median']:.4f} | {v['peak_rss_mb_median']:.1f} | {v['failed_runs']} |" for k, v in meta["perf_bundles"].items()]
    L += ["", f"- 측정 방식: {meta['measurement']['time']} / {meta['measurement']['py_heap']} / {meta['measurement']['rss']}", "",
          "## 5. 테스트", "", f"- pytest: {meta['tests']}", "", "상세: `metrics.csv`, `failures.md`, `detection_detail.json`, `output/`", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
