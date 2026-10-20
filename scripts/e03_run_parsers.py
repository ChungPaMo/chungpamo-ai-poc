"""E03 직접 문서 파서 Baseline 실행: 입력 해시 검증 → 파싱(IR 0.2) → 3회 반복 성능 측정 → 독립 채점 → 결과 기록 → pytest.

    .\\.venv\\Scripts\\python.exe scripts\\e03_run_parsers.py

결과: results/E03_document_parsers/parser_baseline/ (E03 샘플 단계 결과 파일은 건드리지 않는다)
- P-01·P-02(로컬 전용 보류 문서)가 없으면 해당 조합은 NOT_MEASURED로 기록하고 재생성하지 않는다.
- 입력 해시가 sample_manifest.csv와 다르면 즉시 중단한다.
- Upstage API를 호출하지 않는다. P-02 비교는 results/E04_upstage_preflight/preflight_summary.json(기존 예비 결과)만 읽는다.
상태는 RUNNING으로 기록한다.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "results" / "E03_document_parsers" / "parser_baseline"
MANIFEST = ROOT / "results" / "E03_document_parsers" / "sample_manifest.csv"
PREFLIGHT = ROOT / "results" / "E04_upstage_preflight" / "preflight_summary.json"
TRUTH_SHA = "982af3be7af0b4f512851a3a2cba2d68578b8e046540d94f0efe1170b0cf554a"
LOCS_SHA = "0fd368dfa9fae65e4dd8fa978afd7dcc110a75796cb5532c9abb4c74af515159"
REPEATS = 3
FURNITURE = {"CS1": ("CS1-b02",), "CS2": ("CS2-b04",)}  # 문서에 따라 머리말(문서번호)·꼬리말로 렌더링되는 블록 (관찰 기록용)

from parsers.doc_registry import PARSERS  # noqa: E402

import check_environment as ce  # noqa: E402
import e03_grade_parsers as G  # noqa: E402
from e03_parse_doc import ir_digest  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_inputs() -> list[dict]:
    bad, docs = [], []
    for name, want in ((G.TRUTH, TRUTH_SHA), (G.LOCS, LOCS_SHA)):
        if sha(name) != want:
            bad.append(name.name)
    for r in csv.DictReader(open(MANIFEST, encoding="utf-8")):
        p = ROOT / r["file"]
        present = p.exists()
        actual = sha(p) if present else None
        if present and actual != r["sha256"]:
            bad.append(r["file"])
        docs.append({**{k: r[k] for k in ("doc_id", "file", "format", "content_set", "sha256", "bytes")}, "present": present,
                     "sha256_matches_manifest": (actual == r["sha256"]) if present else None})
    if bad:
        raise SystemExit(f"입력 해시 불일치 → 실험 중단: {bad}")
    return docs


def perf(name: str, rel: str, trace: bool) -> dict:
    cmd = [sys.executable, str(ROOT / "scripts" / "e03_parse_doc.py"), name, rel] + (["--trace-mem"] if trace else [])
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc, peak = psutil.Process(p.pid), 0
    # Windows venv의 python.exe는 실제 인터프리터를 자식 프로세스로 띄우는 런처이므로 자식까지 합산 (E02와 같은 방식)
    while p.poll() is None:
        try:
            peak = max(peak, proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True)))
        except psutil.Error:
            pass
        time.sleep(0.005)
    out, err = p.communicate()
    wall = time.perf_counter() - t0
    if p.returncode != 0:
        return {"ok": False, "error": ce.mask_sensitive(err.decode("utf-8", "replace")[-500:])}
    res = json.loads(out.decode("utf-8"))
    res.update({"ok": True, "process_wall_seconds": wall, "peak_rss_bytes": peak})
    return res


def med(xs, scale=1.0, fmt="{:.4f}"):
    return fmt.format(statistics.median(xs) / scale) if len(xs) == REPEATS else "측정실패"


def main() -> int:
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    docs = verify_inputs()
    truth, locs = G.load_truth()
    (OUT / "output").mkdir(parents=True, exist_ok=True)
    runs = []
    for name, (fmt, fn) in PARSERS.items():
        for d in (x for x in docs if x["format"] == fmt):
            run = {"parser": name, "doc": d, "ir": None, "error": None, "perf": None}
            outp = OUT / "output" / f"{d['doc_id']}__{name}.json"
            if not d["present"]:
                run["error"] = "입력 문서 없음 (로컬 전용 보류 문서, D-020) — 재생성하지 않음"
                outp.unlink(missing_ok=True)
            else:
                try:
                    run["ir"] = fn(ROOT / d["file"], d["file"])
                    outp.write_text(json.dumps(run["ir"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
                except Exception as e:  # 실패는 기록하고 계속 (성공 처리하지 않음)
                    run["error"] = f"{type(e).__name__}: {ce.mask_sensitive(str(e))[:300]}"
                    outp.unlink(missing_ok=True)
            if run["ir"] is not None:
                t = [perf(name, d["file"], False) for _ in range(REPEATS)]
                m = [perf(name, d["file"], True) for _ in range(REPEATS)]
                digests = {r.get("ir_sha256") for r in t + m if r["ok"]} | {ir_digest(run["ir"])}
                run["perf"] = {"time_runs": t, "mem_runs": m, "failed_runs": sum(not r["ok"] for r in t + m),
                               "output_identical_across_runs": len(digests) == 1 and all(r["ok"] for r in t + m), "ir_sha256": ir_digest(run["ir"])}
            run["grade"] = G.grade(run["ir"], d, truth, locs)
            runs.append(run)
    # P-02: 예비 분석과 같은 정의로 나란히 비교
    pre = json.loads(PREFLIGHT.read_text(encoding="utf-8")) if PREFLIGHT.exists() else None
    p02 = {r["parser"]: G.preflight_compatible(r["ir"], truth, locs) for r in runs if r["doc"]["doc_id"] == "P-02"}
    rows = [metric_row(r) for r in runs]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    (OUT / "metrics.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    grading = {"definition": G.__doc__, "results": [{"parser": r["parser"], "doc_id": r["doc"]["doc_id"], "error": r["error"], **r["grade"]} for r in runs],
               "p02_preflight_compatible": {"direct_parsers": p02, "upstage_standard_preflight": upstage_view(pre)}}
    (OUT / "grading.json").write_text(json.dumps(grading, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    tests = run_pytest()
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    git_status = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--short"], cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8").stdout.splitlines()
    from importlib.metadata import version
    meta = {
        "experiment_id": "E03", "experiment_name": "DOCX·PDF·PPTX 직접 문서 파서 Baseline", "status": "RUNNING",
        "status_note": "직접 파서 Baseline 측정 완료, 사용자·ChatGPT 검토 대기. HWP/HWPX·OCR·E04 본 실험 미착수",
        "run_timestamp": started, "python": sys.version.split()[0],
        "packages": {p: version(p) for p in ("python-docx", "python-pptx", "pypdf", "pdfplumber", "pdfminer.six", "pypdfium2", "psutil")},
        "git": {"base_commit": git_head, "uncommitted_changes": git_status},
        "inputs": {"truth_sha256": TRUTH_SHA, "locations_sha256": LOCS_SHA, "manifest": "results/E03_document_parsers/sample_manifest.csv", "documents": docs},
        "measurement": {"repeats": REPEATS,
                        "time": "자식 프로세스 안 time.perf_counter — import_seconds(파서 모듈·라이브러리 import), parse_seconds(파일 열기~IR 완성). tracemalloc 미사용 3회의 중앙값",
                        "py_heap": "tracemalloc 파싱 중 피크 (별도 3회 실행 중앙값, Python 힙만 — C 확장·pdfium 내부 메모리 미포함)",
                        "rss": "자식 프로세스 피크 RSS = venv 런처 + 인터프리터 합 (psutil 5ms 폴링, 인터프리터·라이브러리 적재 포함)",
                        "determinism": "6회 실행(시간 3 + 메모리 3)과 결과 저장용 실행의 IR SHA-256(키 정렬 JSON) 동일 여부"},
        "runs": [{"parser": r["parser"], "doc_id": r["doc"]["doc_id"], "error": r["error"],
                  "perf": None if not r["perf"] else {"failed_runs": r["perf"]["failed_runs"], "output_identical_across_runs": r["perf"]["output_identical_across_runs"],
                                                      "ir_sha256": r["perf"]["ir_sha256"],
                                                      "parse_seconds": [x.get("parse_seconds") for x in r["perf"]["time_runs"]],
                                                      "import_seconds": [x.get("import_seconds") for x in r["perf"]["time_runs"]],
                                                      "peak_rss_mb": [round(x.get("peak_rss_bytes", 0) / 1048576, 1) for x in r["perf"]["time_runs"]],
                                                      "py_heap_peak_mb": [round(x.get("py_heap_peak_bytes", 0) / 1048576, 3) for x in r["perf"]["mem_runs"]]}}
                 for r in runs],
        "upstage": {"api_calls_this_run": 0, "source": "results/E04_upstage_preflight/preflight_summary.json (기존 예비 호출 1회 결과)"},
        "tests": tests,
    }
    (OUT / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    (OUT / "failures.md").write_text(failures_md(runs), encoding="utf-8", newline="\n")
    (OUT / "summary.md").write_text(summary_md(meta, rows, runs, p02, pre), encoding="utf-8", newline="\n")
    print(json.dumps({"tests": tests, "runs": [(r["parser"], r["doc"]["doc_id"], r["grade"]["status"]) for r in runs]}, ensure_ascii=False))
    return 0 if tests and not tests["failed"] and not tests["errors"] else 1


def run_pytest() -> dict | None:
    xml_path = OUT / "pytest_report.xml"
    xml_path.unlink(missing_ok=True)
    py = subprocess.run([sys.executable, "-m", "pytest", "-v", "-rs", "-p", "no:cacheprovider", f"--junitxml={xml_path}"], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / "pytest_output.txt").write_text(ce.mask_sensitive(py.stdout + ("\n--- stderr ---\n" + py.stderr if py.stderr else "")),
                                           encoding="utf-8", newline="\n")
    if not xml_path.exists():
        return None
    suite = ET.parse(xml_path).getroot()
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    t = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
    skipped = [{"test": f"{c.get('classname')}::{c.get('name')}", "reason": c.find("skipped").get("message")}
               for c in suite.iter("testcase") if c.find("skipped") is not None]
    xml_path.write_text(ce.sanitize_junit_xml(xml_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    ET.parse(xml_path)
    return {"total": t["tests"], "passed": t["tests"] - t["failures"] - t["errors"] - t["skipped"], "failed": t["failures"],
            "errors": t["errors"], "skipped": t["skipped"], "skipped_detail": ce.mask_sensitive(skipped),
            "note": "skipped는 통과로 세지 않는다"}


def fr(x: dict) -> str:
    return "미측정" if x["status"] == "NOT_MEASURED" else f"{x['numerator']}/{x['denominator']}"


def metric_row(r: dict) -> dict:
    g, p = r["grade"], r["perf"]
    row = {"doc_id": r["doc"]["doc_id"], "format": r["doc"]["format"], "parser": r["parser"], "status": g["status"], "error": r["error"] or ""}
    if g["status"] != "MEASURED":
        return row | {k: "미측정" for k in METRIC_KEYS}
    tm, mm = [x for x in p["time_runs"] if x["ok"]], [x for x in p["mem_runs"] if x["ok"]]
    vals = {
        "block_exact": fr(g["text"]["block"]["exact"]), "block_found_ignoring_whitespace": fr(g["text"]["block"]["found_ignoring_whitespace"]),
        "block_fine_location": fr(g["text"]["block"]["fine_location"]), "caption_exact": fr(g["text"]["caption"]["exact"]),
        "table_recall": fr(g["table_detection"]["recall"]), "table_precision": fr(g["table_detection"]["precision"]),
        "cell_text": fr(g["cells"]["text"]), "header_cell_text": fr(g["cells"]["header_text"]), "merge_spans": fr(g["cells"]["merge_spans"]),
        "cell_fine_location": fr(g["cells"]["fine_location"]), "cell_text_found_ignoring_structure": fr(g["cells"]["text_found_ignoring_structure"]),
        **{f"value_{k}": fr(v) for k, v in g["values"].items()},
        "order_matched": fr(g["reading_order"]["matched_elements"]), "order_pairwise": fr(g["reading_order"]["pairwise_order"]),
        "link_recall": fr(g["linkage"]["recall"]), "link_precision": fr(g["linkage"]["precision"]), "link_false": g["linkage"]["false_links"],
        "parse_s_median": med([x["parse_seconds"] for x in tm]), "parse_s_min": f"{min(x['parse_seconds'] for x in tm):.4f}" if tm else "측정실패",
        "parse_s_max": f"{max(x['parse_seconds'] for x in tm):.4f}" if tm else "측정실패",
        "import_s_median": med([x["import_seconds"] for x in tm]),
        "py_heap_peak_mb_median": med([x["py_heap_peak_bytes"] for x in mm], 1048576, "{:.3f}"),
        "peak_rss_mb_median": med([x["peak_rss_bytes"] for x in tm], 1048576, "{:.1f}"),
        "failed_runs": p["failed_runs"], "output_identical_across_runs": p["output_identical_across_runs"], "repeats": REPEATS,
    }
    return row | vals


METRIC_KEYS = ["block_exact", "block_found_ignoring_whitespace", "block_fine_location", "caption_exact", "table_recall", "table_precision", "cell_text",
               "header_cell_text", "merge_spans", "cell_fine_location", "cell_text_found_ignoring_structure", "value_id", "value_quantity", "value_money", "value_unit", "value_date",
               "value_block_date", "value_block_qty_unit", "order_matched", "order_pairwise", "link_recall", "link_precision", "link_false",
               "parse_s_median", "parse_s_min", "parse_s_max", "import_s_median", "py_heap_peak_mb_median", "peak_rss_mb_median", "failed_runs",
               "output_identical_across_runs", "repeats"]


def upstage_view(pre: dict | None) -> dict | None:
    if not pre:
        return None
    c = pre["comparison_vs_e03_truth"]
    return {"source": "results/E04_upstage_preflight/preflight_summary.json", "model": pre["response"]["model"], "mode": "standard",
            "text_blocks": c["text_blocks"], "table_captions": c["table_captions"],
            "tables": [{k: t.get(k) for k in ("table_id", "fragment_index", "api_rows", "expected_rows", "api_cols", "expected_cols", "table_bbox_iou")} for t in c["tables"]],
            "cells_all_fragments": c["cells_all_fragments"], "header_cells": c["header_cells"], "merged_cells_spans": c["merged_cells_spans"],
            "product_material_codes": c["product_material_codes"], "values_by_field": c["values_by_field"],
            "multipage_link": c["multipage_table_link"], "elapsed_seconds_incl_network": pre["call"]["elapsed_seconds"]}


def failures_md(runs: list[dict]) -> str:
    L = ["# E03 직접 파서 실패·미측정·오류 사례", "", "> scripts/e03_run_parsers.py가 채점 결과로 자동 생성.", "", "## 1. 실행 실패·미측정 조합", ""]
    L += [f"- {r['parser']} × {r['doc']['doc_id']}: {r['error']}" for r in runs if r["error"]] or ["- 없음"]
    L += ["", "## 2. 지표별 불일치 (분모 대비 미달)", ""]
    any_miss = False
    for r in runs:
        g = r["grade"]
        if g["status"] != "MEASURED":
            continue
        misses = []
        for path, m in flatten_rates(g):
            if m["status"] in ("PARTIAL", "FAIL"):
                misses.append(f"{path} {m['numerator']}/{m['denominator']}" + (f" ({m['note']})" if m.get("note") else ""))
        if g["linkage"]["false_links"]:
            misses.append(f"잘못된 표 연결 {g['linkage']['false_links']}건")
        if misses:
            any_miss = True
            L.append(f"- **{r['parser']} × {r['doc']['doc_id']}**: " + "; ".join(misses))
        for o in g["text_occurrences"]:
            if not o["exact"]:
                L.append(f"  - 블록 불일치: {o['kind']} {o['id']} (단위 {o['unit']}) — 공백 무시 포함 여부 {o['found_ignoring_whitespace']}")
    if not any_miss:
        L.append("- 없음")
    L += ["", "## 3. 머리말·꼬리말의 쪽·슬라이드 안 위치 (읽기 순서 채점에서 제외한 요소의 관찰값)", ""]
    furniture_obs = []
    for r in runs:
        if r["grade"]["status"] != "MEASURED":
            continue
        for o in r["grade"]["text_occurrences"]:
            if o["kind"] == "block" and o["rank_in_unit"] and o["id"] in FURNITURE.get(r["doc"]["content_set"], ()):
                furniture_obs.append(f"- {r['parser']} × {r['doc']['doc_id']} {o['id']} (단위 {o['unit']}): {o['rank_in_unit'][0]}번째 / {o['rank_in_unit'][1]}개 요소")
    L += furniture_obs or ["- 해당 없음"]
    L += ["", "## 4. 파서가 보고한 지원 범위 밖 정보 (IR diagnostics)", ""]
    for r in runs:
        if r["grade"]["status"] == "MEASURED" and r["grade"]["ir_diagnostics"]:
            L.append(f"- {r['parser']} × {r['doc']['doc_id']}: " + " / ".join(r["grade"]["ir_diagnostics"]))
    L += ["", "## 5. 분모 0 (미측정) 지표", ""]
    for r in runs:
        if r["grade"]["status"] == "MEASURED":
            nm = [p for p, m in flatten_rates(r["grade"]) if m["status"] == "NOT_MEASURED"]
            if nm:
                L.append(f"- {r['parser']} × {r['doc']['doc_id']}: {', '.join(nm)}")
    return "\n".join(L) + "\n"


def flatten_rates(g: dict, prefix: str = ""):
    for k, v in g.items():
        if k in ("text_occurrences", "table_fragments", "reading_order") and not prefix:
            if k == "reading_order":
                yield "reading_order.matched_elements", v["matched_elements"]
                yield "reading_order.pairwise_order", v["pairwise_order"]
            continue
        if isinstance(v, dict) and {"numerator", "denominator", "status"} <= set(v):
            yield prefix + k, v
        elif isinstance(v, dict):
            yield from flatten_rates(v, prefix + k + ".")


def summary_md(meta: dict, rows: list[dict], runs: list[dict], p02: dict, pre: dict | None) -> str:
    L = ["# E03 직접 문서 파서 Baseline — 결과 요약", "",
         f"> 자동 생성. 상태 **{meta['status']}** ({meta['status_note']}). 실행 {meta['run_timestamp']}, 기준 커밋 `{meta['git']['base_commit']}`", "",
         "- 파서: " + ", ".join(f"{k} {v}" for k, v in meta["packages"].items() if k != "psutil"),
         f"- 입력: E03 샘플 6개 (매니페스트 SHA-256 대조), 정답 명세 `{TRUTH_SHA[:12]}…`, 위치 `{LOCS_SHA[:12]}…`",
         "- 문서 없음: " + (", ".join(d["doc_id"] for d in meta["inputs"]["documents"] if not d["present"]) or "없음"),
         "- 상태 표기: PASS=분모 전부 일치, PARTIAL=일부, FAIL=전무, 미측정=분모 0 또는 문서 없음. **채택 기준이 아니다** (정량 목표는 팀 합의 필요)", "",
         "## 1. 문서·파서별 정확도", "",
         "| 문서 | 파서 | 블록 완전일치 | 블록 텍스트(공백무시) | 캡션 | 표 재현율 | 표 정밀도 | 셀 텍스트 | 헤더 셀 | 병합 span | 셀 텍스트(구조 무시) | 읽기 순서(요소/쌍) | 표 연결(재현/오연결) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] != "MEASURED":
            L.append(f"| {r['doc_id']} | {r['parser']} | 미측정 — {r['error']} ||||||||||| |")
            continue
        L.append(f"| {r['doc_id']} | {r['parser']} | {r['block_exact']} | {r['block_found_ignoring_whitespace']} | {r['caption_exact']} | {r['table_recall']} | "
                 f"{r['table_precision']} | {r['cell_text']} | {r['header_cell_text']} | {r['merge_spans']} | {r['cell_text_found_ignoring_structure']} | "
                 f"{r['order_matched']} / {r['order_pairwise']} | {r['link_recall']} / {r['link_false']} |")
    L += ["", "- 셀 텍스트(구조 무시): 정답 셀 텍스트가 같은 쪽·슬라이드의 추출 텍스트 어딘가에 있는지(공백 무시). 짧은 값('1', 'EA')은 우연 일치가 가능해 상한값이다.",
          "- 읽기 순서: 본문 요소만 (머리말·꼬리말 제외, 쪽 넘김 표는 첫 조각). '요소' = 순서를 매길 수 있었던 정답 요소 수, '쌍' = 그중 순서가 맞는 쌍"]
    L += ["", "## 2. 숫자·단위·날짜·코드 (표 셀 원문 보존) 와 원본 위치", "",
          "| 문서 | 파서 | 코드 | 수량 | 금액 | 단위 | 날짜 | 블록 안 날짜 | 블록 안 수량+단위 | 블록 위치 | 셀 위치 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] == "MEASURED":
            L.append(f"| {r['doc_id']} | {r['parser']} | {r['value_id']} | {r['value_quantity']} | {r['value_money']} | {r['value_unit']} | {r['value_date']} | "
                     f"{r['value_block_date']} | {r['value_block_qty_unit']} | {r['block_fine_location']} | {r['cell_fine_location']} |")
    L += ["", "- 위치 기준: DOCX = part·body_index / 표 table_index·행·열, PDF = page + bbox IoU ≥ 0.5, PPTX = slide·shape_id / 표 행·열. pypdf는 bbox를 주지 않아 세부 위치 0",
          "", "## 3. 처리시간·메모리 (3회 반복 중앙값)", "",
          "| 문서 | 파서 | 파싱(s) 중앙값 [최소~최대] | import(s) | Python 힙 피크(MB) | 프로세스 피크 RSS(MB) | 실패 실행 | 반복 출력 동일 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] == "MEASURED":
            L.append(f"| {r['doc_id']} | {r['parser']} | {r['parse_s_median']} [{r['parse_s_min']}~{r['parse_s_max']}] | {r['import_s_median']} | "
                     f"{r['py_heap_peak_mb_median']} | {r['peak_rss_mb_median']} | {r['failed_runs']} | {r['output_identical_across_runs']} |")
    L += ["", f"- 측정 방식: {meta['measurement']['time']} / {meta['measurement']['py_heap']} / {meta['measurement']['rss']}", "",
          "## 4. P-02: 기존 Upstage Standard 예비 결과와 같은 정의로 비교", ""]
    if not p02 or all(v is None for v in p02.values()) or not pre:
        L.append("- 비교 불가: P-02 문서(로컬 전용) 또는 예비 결과 파일이 없음")
    else:
        up = upstage_view(pre)
        cols = [k for k, v in p02.items() if v]
        L += ["| 항목 (예비 분석 정의) | " + " | ".join(cols) + " | Upstage standard (예비 1회) |", "|---" * (len(cols) + 2) + "|"]
        for key, label in (("cells_all_fragments", "셀 텍스트 (전 조각)"), ("header_cells", "헤더 셀"), ("merged_cells_spans", "병합 셀 span"),
                           ("product_material_codes", "제품·자재 코드")):
            L.append(f"| {label} | " + " | ".join(fr(p02[c][key]) for c in cols) + f" | {fr(up[key])} |")
        for f in sorted(up["values_by_field"]):
            L.append(f"| 값 `{f}` | " + " | ".join(fr(p02[c]['values_by_field'][f]) for c in cols) + f" | {fr(up['values_by_field'][f])} |")
        for i, t in enumerate(up["tables"]):
            L.append(f"| 표 bbox IoU {t['table_id']}#{t['fragment_index']} | " + " | ".join(str(p02[c]['tables'][i]['table_bbox_iou']) for c in cols) + f" | {t['table_bbox_iou']} |")
        for i, b in enumerate(up["text_blocks"]):
            L.append(f"| 블록 {b['block_id']} 검출(출현) | " + " | ".join(f"{p02[c]['text_blocks'][i]['found_occurrences']}/{p02[c]['text_blocks'][i]['expected_occurrences']}" for c in cols)
                     + f" | {b['found_occurrences']}/{b['expected_occurrences']} |")
            L.append(f"| 블록 {b['block_id']} bbox IoU | " + " | ".join(str(p02[c]['text_blocks'][i]['bbox_iou_per_occurrence'] or '좌표 없음') for c in cols)
                     + f" | {b['bbox_iou_per_occurrence']} |")
        L.append("| 표 캡션 검출 | " + " | ".join(str(sum(p02[c]['table_captions_found'].values())) + "/2" for c in cols)
                 + f" | {sum(x['found'] for x in up['table_captions'])}/2 |")
        L.append("| 쪽 넘김 표 연결 | " + " | ".join(("연결됨 (공통 후처리 규칙)" if p02[c]['multipage_link'] and p02[c]['multipage_link'][0]['linked'] else "연결 안 됨") for c in cols)
                 + " | 연결 정보 없음 (두 표로 반환, merge_multipage_tables 미사용) |")
        L += ["", "**비교 불가 항목** (공통 조건 미충족):",
              f"- 처리시간: 로컬 파싱 시간 vs API 왕복 {up['elapsed_seconds_incl_network']}s(네트워크·서버 포함, 1회) — 조건이 달라 비교 불가",
              "- 메모리: API는 서버 측 → 비교 불가 / 비용: 직접 파서 0, Upstage 3쪽 과금(추정 $0.03) — 비용 구조가 달라 같은 지표로 비교하지 않음",
              "- 읽기 순서·셀 단위 위치·블록 유형: 예비 분석에 같은 정의의 지표가 없고, 응답 원문 재분석은 이번 범위 밖 → 비교 불가 (Upstage는 셀 좌표 미제공 — 예비 결과 기록)",
              "- 쪽 넘김 연결: 직접 파서 쪽 연결은 라이브러리 기능이 아닌 공통 후처리 규칙 결과이므로 기능 비교가 아님",
              "- P-02 1개 문서·Upstage 1회 호출 결과이며 일반화하지 않는다"]
    L += ["", "## 5. 한계 (결과 해석 시 반드시 함께 볼 것)", "",
          "- **같은 라이브러리 계열 왕복**: DOCX·PPTX 샘플은 python-docx·python-pptx로 만들었고 같은 라이브러리로 읽었다. PDF는 reportlab이 그린 선 있는 표다. "
          "높은 일치율은 '생성 도구와 같은 구조를 다시 읽을 수 있다'는 뜻이며, Word·PowerPoint·한글·스캔 등 실제 문서에 대한 정확도를 뜻하지 않는다.",
          "- pdfplumber 표 검출은 그려진 선에 의존한다 (선 없는 표·이미지 표 미시험). 문단 묶기 규칙(같은 x0·줄 간격)은 이 샘플을 보며 정했다.",
          "- 표 조각 연결 규칙(header_repeat_rule)은 이 샘플(쪽 넘김 2건, 같은 헤더의 서로 다른 표 1쌍)을 알고 설계한 공통 후처리다. 일반화 성능은 미검증. 라이브러리 자체 연결 기능은 세 파서 모두 없음.",
          "- 블록 유형(제목·캡션·머리말)은 PDF 파서 2종이 구분하지 않고(모두 paragraph), DOCX는 스타일 이름으로만 구분한다. 캡션·각주는 일반 문단으로 나온다. 유형 정확도는 채점하지 않음(grading.json의 block_type_pairs 참고).",
          "- DOCX는 쪽 위치를 주지 않는다 (파일에 쪽 나눔 결과가 없음). pypdf는 표 구조·좌표·문단을 주지 않는다.",
          "- PDF 2건(P-01·P-02)은 공개 보류 문서로 로컬에서만 측정했다. 새 클론에서는 미측정으로 기록된다.",
          "- 처리시간·메모리는 이 PC 1대, 소형 문서(1~4쪽) 기준이다.", "",
          "## 6. 테스트", "", f"- pytest: 전체 {meta['tests']['total']}, 통과 {meta['tests']['passed']}, 실패 {meta['tests']['failed']}, 오류 {meta['tests']['errors']}, "
          f"스킵 {meta['tests']['skipped']} (스킵은 통과로 세지 않음)" if meta["tests"] else "- pytest: 실행 결과 없음"]
    if meta["tests"]:
        L += [f"  - 스킵: {s['test']} — {s['reason']}" for s in meta["tests"]["skipped_detail"]]
    L += ["", "상세: `metrics.csv`, `grading.json`, `failures.md`, `run_meta.json`, `output/` (IR)", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
