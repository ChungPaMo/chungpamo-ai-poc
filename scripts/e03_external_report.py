"""외부 문서 평가 결과 폴더(metrics.csv·grading.json·run_meta.json)로 summary.md·failures.md 작성 (텍스트 없는 공개용 요약).

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_report.py <결과 폴더 이름> [<비교 기준 결과 폴더 이름>]

평가 결과 파일은 바꾸지 않고 summary.md·failures.md만 (다시) 쓴다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results" / "E03_document_parsers"

KEYS = {
    "pdf": [("table_detection.recall", "표 재현율"), ("table_detection.precision", "표 정밀도"), ("structure.rows_cols_equal", "행·열 수 일치"),
            ("cells.text_loose_grid", "셀 텍스트(격자, 공백무시)"), ("cells.text_loose_bbox_aligned", "셀 텍스트(bbox 정렬)"),
            ("cells.cell_bbox_iou_ge_0_5", "셀 bbox IoU≥0.5"), ("cells.merge_spans", "병합"), ("cells.column_header_text", "헤더 셀"),
            ("cells.projected_row_header", "행 머리"), ("cells.text_found_ignoring_structure", "셀 텍스트(구조 무시)")],
    "docx": [("body_paragraph_exact", "본문 문단 일치"), ("body_char.recall", "본문 문자 재현율"), ("body_char.precision", "본문 문자 정밀도"),
             ("table_detection.recall", "표 재현율"), ("table_detection.precision", "표 정밀도"), ("structure.rows_cols_equal", "행·열 수 일치"),
             ("cells.text_strict_grid", "셀 텍스트"), ("cells.merge_spans", "병합"), ("reading_order.pairwise_order", "읽기 순서(쌍)"),
             ("footnotes", "각주"), ("tracked_insertions_included", "변경 추적 삽입 포함"), ("tracked_deletions_excluded", "삭제 텍스트 제외"), ("header_footer", "머리말·꼬리말")],
    "pptx": [("shape_text_exact", "도형 텍스트 일치"), ("shape_char.recall", "문자 재현율"), ("shape_location_slide_and_id", "위치(슬라이드·도형ID)"),
             ("group_child_text_found", "그룹 안 텍스트"), ("group_nested_path_equal", "그룹 경로"), ("table_detection.recall", "표 재현율"),
             ("structure.rows_cols_equal", "행·열 수 일치"), ("cells.text_strict_grid", "셀 텍스트"), ("cells.merge_spans", "병합"),
             ("smartart_node_text_found", "SmartArt 노드"), ("chart_text_found", "차트 텍스트"), ("notes_exact", "노트")],
}


def get(m, path):
    for k in path.split("."):
        m = (m or {}).get(k)
    return m


def fmt(x):
    if x is None:
        return "—"
    if isinstance(x, dict) and "status" in x:
        if x["status"] == "NOT_MEASURED":
            return "미측정"
        tag = "" if x.get("truth_status") in (None, "VERIFIED_OFFICIAL") else "†"
        return f"{x['numerator']}/{x['denominator']}{tag}"
    return str(x)


def main() -> int:
    name = sys.argv[1]
    cmp = sys.argv[2] if len(sys.argv) > 2 else None
    d = BASE / name
    g = json.loads((d / "grading.json").read_text(encoding="utf-8"))["results"]
    meta = json.loads((d / "run_meta.json").read_text(encoding="utf-8"))
    base = {(r["doc_id"], r["parser"]): r for r in json.loads((BASE / cmp / "grading.json").read_text(encoding="utf-8"))["results"]} if cmp else {}
    L = [f"# E03 외부 문서 평가 — {name}", "",
         f"> 자동 생성 (scripts/e03_external_report.py). 파서 {meta['parser_version']}, 문서 묶음 `{meta['set']}`, 실행 {meta['run_timestamp']}, 상태 RUNNING.",
         f"> 정답 `{meta['truth']['sha256'][:12]}…` (사람 뷰어 검수 {'함' if meta['truth']['manual_review_performed'] else '안 함'}). "
         "† = 잠정 정답(PROVISIONAL, XML 직접 판독) 기준 점수 — 검증된 정확도가 아님. 표기 없는 수치는 공식 정답(VERIFIED_OFFICIAL) 기준.",
         f"> Upstage 호출 {meta['upstage_api_calls']}회." + (f" 비교 기준: `{cmp}` (괄호 안)" if cmp else ""), ""]
    for fmt_name in ("pdf", "docx", "pptx"):
        rs = [r for r in g if (r["grade"].get("format") or "") == fmt_name or (r["grade"]["status"] != "MEASURED" and r["doc_id"].split("-")[-1][0] == {"pdf": "P", "docx": "D", "pptx": "T"}[fmt_name])]
        if not rs:
            continue
        cols = KEYS[fmt_name]
        L += [f"## {fmt_name.upper()}", "", "| 문서 | 파서 | " + " | ".join(c[1] for c in cols) + " |", "|---|---|" + "---|" * len(cols)]
        for r in rs:
            if r["grade"]["status"] != "MEASURED":
                L.append(f"| {r['doc_id']} | {r['parser']} | {r['grade']['status']}: {r['grade'].get('reason', '')} |" + " |" * (len(cols) - 1))
                continue
            cells = []
            for k, _ in cols:
                v = fmt(get(r["grade"]["metrics"], k))
                if cmp and (b := base.get((r["doc_id"], r["parser"]))) and b["grade"]["status"] == "MEASURED":
                    v += f" ({fmt(get(b['grade']['metrics'], k))})"
                cells.append(v)
            L.append(f"| {r['doc_id']} | {r['parser']} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## 처리시간·메모리 (3회 중앙값)", "", "| 문서 | 파서 | 파싱(s) | import(s) | 피크 RSS(MB) | Python 힙(MB) | 성공 실행 | 반복 출력 동일 |", "|---|---|---|---|---|---|---|---|"]
    import statistics
    for r in g:
        p = r["perf"]
        if not p:
            continue
        md = lambda xs, f="{:.3f}": f.format(statistics.median([x for x in xs if x is not None])) if [x for x in xs if x is not None] else "—"
        L.append(f"| {r['doc_id']} | {r['parser']} | {md(p['parse_seconds'])} | {md(p['import_seconds'])} | {md(p['peak_rss_mb'], '{:.1f}')} | "
                 f"{md(p['py_heap_peak_mb'])} | {p['ok_runs']}/{p['total_runs']} | {p['output_identical_across_runs']} |")
    (d / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    F = [f"# 실패·미측정 — {name}", "", "> 자동 생성. 텍스트 내용은 쓰지 않는다 (위치·개수만). 원인 분석은 docs/e03_external_generalization_report.md", ""]
    for r in g:
        gr = r["grade"]
        if gr["status"] != "MEASURED":
            F.append(f"- **{r['doc_id']} × {r['parser']}**: {gr['status']} — {gr.get('reason')}" + (f" / 오류 {r['perf']['errors']}" if r["perf"] and r["perf"]["errors"] else ""))
            continue
        bad = []

        def walk(m, pre=""):
            for k, v in m.items():
                if isinstance(v, dict) and "status" in v and "numerator" in v:
                    if v["status"] in ("PARTIAL", "FAIL"):
                        bad.append(f"{pre}{k} {v['numerator']}/{v['denominator']}" + ("†" if v.get("truth_status") not in (None, "VERIFIED_OFFICIAL") else ""))
                elif isinstance(v, dict):
                    walk(v, pre + k + ".")
        walk(gr["metrics"])
        fm = gr["metrics"].get("cells", {}).get("false_merges")
        if fm:
            bad.append(f"잘못된 병합 {fm}")
        if bad:
            F.append(f"- **{r['doc_id']} × {r['parser']}**: " + "; ".join(bad))
        if gr.get("ir_diagnostics"):
            F.append(f"  - 파서 진단: {' / '.join(gr['ir_diagnostics'])}")
        if gr["metrics"].get("tables"):
            for t in gr["metrics"]["tables"]:
                if t["matched_ir_table"] is None or t["ir_shape"] != t["truth_shape"]:
                    F.append(f"  - 표 {t['table_id']} (쪽 {t['page']}): 정답 {t['truth_shape']} / 출력 {t['ir_shape']} / IoU {t['table_bbox_iou']} / 그 쪽 출력 표 {t['ir_tables_on_page']}개")
    (d / "failures.md").write_text("\n".join(F) + "\n", encoding="utf-8", newline="\n")
    print(f"written {d.relative_to(ROOT)}/summary.md, failures.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
