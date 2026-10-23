"""E12 집계 — results.json을 읽어 분할(합성 / holdout / blind8 / dev)별 합계와 성능 요약을 만든다 (results.json은 읽기만).

    .\\.venv\\Scripts\\python.exe scripts\\e12_summary.py

결과: results/E12_officecli/summary.json. 보고서 표의 수치는 이 파일에서 옮긴다.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "E12_officecli"

SYN_KEYS = ["text.block.exact", "text.caption.exact", "table_detection.recall", "table_detection.precision", "cells.text", "cells.header_text", "cells.merge_spans",
            "cells.fine_location", "linkage.recall", "reading_order.pairwise_order"]
EXT_KEYS = ["body_paragraph_exact", "body_char.recall", "body_char.precision", "table_detection.recall", "table_detection.precision", "structure.rows_cols_equal",
            "cells.text_strict_grid", "cells.text_loose_grid", "cells.merge_spans", "footnotes", "header_footer", "reading_order.pairwise_order",
            "shape_text_exact", "shape_char.recall", "shape_location_slide_and_id", "group_text_found", "smartart_node_text_found", "chart_text_found", "notes_found"]


def add(acc, k, v):
    if not isinstance(v, str) or "/" not in v:
        return
    a, b = v.split("/")
    n, d = acc.get(k, (0, 0))
    acc[k] = (n + int(a), d + int(b))


def agg(rows, keys):
    out = {}
    for tool in ("baseline_v2", "officecli"):
        acc = {}
        for r in rows:
            for k in keys:
                add(acc, k, r[tool].get(k))
        out[tool] = {k: f"{n}/{d}" for k, (n, d) in acc.items()}
    return out


def main() -> int:
    r = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    s = {"source": "results/E12_officecli/results.json", "pdf": r["pdf"]["status"]}
    s["xlsx"] = {f: {t: v["metrics"] for t, v in r["xlsx"][f].items()} for f in ("X12-01", "X12-02_no_formula_cache")}
    s["xlsx"]["e02_vendor_agreement"] = [{k: a[k] for k in ("file", "cells_compared", "same", "merges_equal")} for a in r["xlsx"]["e02_vendor_agreement"]]
    s["synthetic"] = {"truth": "GENERATED", "documents": [d["doc_id"] for d in r["synthetic"]], **agg(r["synthetic"], SYN_KEYS)}
    s["external"] = {}
    for split in ("holdout", "blind8", "dev"):
        rows = [d for d in r["external"] if d["split"] == split]
        s["external"][split] = {"truth": "PROVISIONAL", "documents": [d["doc_id"] for d in rows], **agg(rows, EXT_KEYS),
                                "differing_documents": sorted({d["doc_id"] for d in rows if any(d["officecli"].get(k) != d["baseline_v2"].get(k) for k in d["officecli"])})}
    runs = r["synthetic"] + r["external"]
    s["officecli_runs"] = {"documents": len(runs), "failed": sum(not d["officecli_run"]["ok"] for d in runs),
                           "source_changed": sum(not d["officecli_run"]["source_unchanged"] for d in runs),
                           "temp_copy_rewritten_by_batch": sum(bool(d["officecli_run"]["copy_rewritten_by_batch"]) for d in runs)}
    perf = []
    for p in r["perf"]:
        b, o = p["baseline"], p["officecli"]
        perf.append({"doc": p["doc"].split("/")[-1] if not p["doc"].startswith("data/raw/") else "external:" + p["doc"].split("/")[-1], "format": p["format"],
                     "baseline_first_s": b["wall_s"]["first"], "baseline_repeat_median_s": b["wall_s"]["repeat_median"], "baseline_peak_mb": b["peak_rss_mb"],
                     "officecli_first_s": o["wall_s"]["first"], "officecli_repeat_median_s": o["wall_s"]["repeat_median"], "officecli_peak_mb": o["peak_rss_mb"],
                     "ratio_all_median": round(o["wall_s"]["all_median"] / b["wall_s"]["all_median"], 1), "failed": b["failed"] + o["failed"], "officecli_cli_calls": o["cli_calls"]})
    s["perf"] = perf
    s["perf_overall"] = {"ratio_median": statistics.median(x["ratio_all_median"] for x in perf), "ratio_min": min(x["ratio_all_median"] for x in perf),
                         "ratio_max": max(x["ratio_all_median"] for x in perf), "failed_runs": sum(x["failed"] for x in perf)}
    s["network"] = r["network"]
    (OUT / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(s, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
