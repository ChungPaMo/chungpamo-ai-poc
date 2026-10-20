"""외부 문서 평가 결과 비교 집계: 묶음(blind8·dev·holdout) × 파서 버전(v1·v2)별 분자·분모 합. 묶음끼리 합치지 않는다.

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_compare.py

출력: results/E03_document_parsers/external_comparison.json, external_comparison.md (텍스트 없는 공개용)
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results" / "E03_document_parsers"
RUNS = [("blind8", "v1", "external_baseline_v1"), ("blind8", "v2", "external_blind8_v2"), ("dev", "v1", "external_dev_v1"),
        ("dev", "v2", "external_dev_v2"), ("holdout", "v1", "external_holdout_v1"), ("holdout", "v2", "external_holdout_v2")]
METRICS = {
    "pdf": [("table_detection.recall", "표 재현율"), ("table_detection.precision", "표 정밀도"), ("structure.rows_cols_equal", "행·열 수 일치"),
            ("cells.text_loose_grid", "셀 텍스트(격자)"), ("cells.text_loose_bbox_aligned", "셀 텍스트(bbox 정렬)"), ("cells.cell_bbox_iou_ge_0_5", "셀 bbox IoU≥0.5"),
            ("cells.merge_spans", "병합"), ("cells.column_header_text", "헤더 셀"), ("cells.projected_row_header", "행 머리")],
    "docx": [("body_paragraph_exact", "본문 문단"), ("table_detection.recall", "표 재현율"), ("cells.text_strict_grid", "셀 텍스트"), ("cells.merge_spans", "병합"),
             ("reading_order.pairwise_order", "읽기 순서(쌍)"), ("footnotes", "각주"), ("tracked_insertions_included", "변경 추적 삽입")],
    "pptx": [("shape_text_exact", "도형 텍스트"), ("table_detection.recall", "표 재현율"), ("cells.text_strict_grid", "셀 텍스트"), ("cells.merge_spans", "병합"),
             ("smartart_node_text_found", "SmartArt"), ("chart_text_found", "차트")],
}
PDF_PARSER = "pdfplumber"


def get(m, path):
    for k in path.split("."):
        m = (m or {}).get(k)
    return m


def main() -> int:
    out = {}
    for split, ver, folder in RUNS:
        g = json.loads((BASE / folder / "grading.json").read_text(encoding="utf-8"))["results"]
        rec = {"folder": folder, "parser_failures": [f"{r['doc_id']}×{r['parser']}" for r in g if r["grade"]["status"] == "PARSER_FAILED"]}
        for fmt, keys in METRICS.items():
            rows = [r for r in g if r["grade"].get("format") == fmt and (fmt != "pdf" or r["parser"] == PDF_PARSER)]
            agg = {}
            for k, label in keys:
                n = d = 0
                ts = set()
                for r in rows:
                    v = get(r["grade"]["metrics"], k)
                    if isinstance(v, dict) and v.get("denominator"):
                        n += v["numerator"]
                        d += v["denominator"]
                        ts.add(v.get("truth_status") or "VERIFIED_OFFICIAL")
                agg[label] = {"numerator": n, "denominator": d, "rate": round(n / d, 4) if d else None, "truth_status": sorted(ts)}
            agg["_documents"] = len(rows)
            rec[fmt] = agg
        perf = {}
        for r in g:
            p = r["perf"]
            if p and [x for x in p["parse_seconds"] if x is not None]:
                perf.setdefault(r["parser"], []).append({"parse_s": statistics.median([x for x in p["parse_seconds"] if x is not None]),
                                                         "rss_mb": statistics.median(p["peak_rss_mb"]), "heap_mb": statistics.median(p["py_heap_peak_mb"])})
        rec["perf"] = {k: {"docs": len(v), "parse_s_median_of_docs": round(statistics.median(x["parse_s"] for x in v), 4),
                           "parse_s_max": round(max(x["parse_s"] for x in v), 4), "rss_mb_max": max(x["rss_mb"] for x in v),
                           "heap_mb_max": max(x["heap_mb"] for x in v)} for k, v in perf.items()}
        out[f"{split}|{ver}"] = rec
    (BASE / "external_comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    L = ["# E03 외부 문서 v1·v2 비교 (묶음별, 합산하지 않음)", "",
         "> 자동 생성 (scripts/e03_external_compare.py). PDF는 pdfplumber만 (pypdf는 표 기능 없음, v1·v2 같은 구현). "
         "† = 잠정 정답(PROVISIONAL) 기준. blind8의 v2 수치는 실패 분석 후 측정한 회귀 결과이고, 일반화 성능은 holdout만 본다.", ""]
    for fmt, keys in METRICS.items():
        L += [f"## {fmt.upper()}", "", "| 지표 | " + " | ".join(f"{s} {v}" for s, v, _ in RUNS) + " |", "|---|" + "---|" * len(RUNS)]
        for _, label in keys:
            cells = []
            for s, v, _ in RUNS:
                a = out[f"{s}|{v}"][fmt][label]
                tag = "†" if any(t != "VERIFIED_OFFICIAL" for t in a["truth_status"]) else ""
                cells.append("미측정" if not a["denominator"] else f"{a['numerator']}/{a['denominator']}{tag}")
            L.append(f"| {label} | " + " | ".join(cells) + " |")
        L.append("| (문서 수) | " + " | ".join(str(out[f"{s}|{v}"][fmt]["_documents"]) for s, v, _ in RUNS) + " |")
        L.append("")
    L += ["## 파싱 실패", ""] + [f"- {k}: {', '.join(v['parser_failures']) or '없음'}" for k, v in out.items()]
    L += ["", "## 처리시간·메모리 (문서별 3회 중앙값의 요약)", "", "| 묶음·버전 | 파서 | 문서 | 파싱 s (문서 중앙값) | 파싱 s 최대 | 피크 RSS 최대(MB) | Python 힙 최대(MB) |", "|---|---|---|---|---|---|---|"]
    for k, v in out.items():
        for p, s in v["perf"].items():
            L.append(f"| {k} | {p} | {s['docs']} | {s['parse_s_median_of_docs']} | {s['parse_s_max']} | {s['rss_mb_max']} | {s['heap_mb_max']} |")
    (BASE / "external_comparison.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("written external_comparison.json / .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
