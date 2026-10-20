"""holdout v2(pdfplumber) 셀 불일치·병합 오류 유형 집계 — 분석 전용 (파서·정답·결과 불변). 텍스트는 기록하지 않는다.

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_error_types.py [결과 폴더=external_holdout_v2]

이 분석을 한 뒤 holdout은 '개발에 참고된 데이터'로 본다 (이후 일반화 평가에는 새 미사용 자료가 필요).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import e03_grade_external as G

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "results" / "E03_document_parsers"


def main() -> int:
    run = sys.argv[1] if len(sys.argv) > 1 else "external_holdout_v2"
    truth = {d["doc_id"]: d for d in json.loads((ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json").read_text(encoding="utf-8"))["documents"]}
    res = json.loads((B / run / "grading.json").read_text(encoding="utf-8"))["results"]
    cell_types, merge_types, per_table = Counter(), Counter(), []
    for r in res:
        if r["parser"] != "pdfplumber" or r["grade"]["status"] != "MEASURED":
            continue
        ir = json.loads((B / run / "outputs" / "first_run" / f"{r['doc_id']}__pdfplumber.json").read_text(encoding="utf-8"))
        for row in r["grade"]["metrics"]["tables"]:
            t = next(x for x in truth[r["doc_id"]]["truth"]["tables"] if x["table_id"] == row["table_id"])
            x = next((y for y in ir["tables"] if y["table_id"] == row["matched_ir_table"]), None)
            got = {(c["row"], c["col"]): c for c in (x["cells"] if x else [])}
            shape_ok = row["ir_shape"] == row["truth_shape"]
            tc = Counter()
            for c in t["cells"]:
                if not G.nows(c["text"]) or c.get("status") == "NEEDS_MANUAL_REVIEW":
                    continue
                a = got.get((c["row"], c["col"]))
                if a is not None and G.nows(a["text"]) == G.nows(c["text"]):
                    continue
                kind = ("표 미검출" if x is None else
                        "행·열 수 불일치 표의 격자 어긋남" if not shape_ok else
                        "해당 위치 출력 셀 없음(병합 셀에 덮임)" if a is None else
                        "출력 셀이 빈 칸" if not G.nows(a["text"]) else
                        "출력이 정답+다른 텍스트(이웃 칸·줄 합쳐짐)" if G.nows(c["text"]) in G.nows(a["text"]) else
                        "출력이 정답 일부(칸·줄 나뉨)" if G.nows(a["text"]) in G.nows(c["text"]) else "텍스트 다름")
                kind += " / 머리 셀" if c.get("is_column_header") else " / 행 머리" if c.get("is_projected_row_header") else " / 본문"
                tc[kind] += 1
            mc = Counter()
            for c in t["cells"]:
                if c["rowspan"] > 1 or c["colspan"] > 1:
                    a = got.get((c["row"], c["col"]))
                    if a is not None and (a["rowspan"], a["colspan"]) == (c["rowspan"], c["colspan"]):
                        continue
                    where = "머리" if c.get("is_column_header") else "행 머리" if c.get("is_projected_row_header") else "본문"
                    axis = "가로" if c["colspan"] > 1 and c["rowspan"] == 1 else "세로" if c["rowspan"] > 1 and c["colspan"] == 1 else "가로·세로"
                    kind = ("표 미검출" if x is None else "행·열 수 불일치 표" if not shape_ok else
                            "출력 셀 없음" if a is None else
                            "병합 안 됨(span 1)" if (a["rowspan"], a["colspan"]) == (1, 1) else "span 크기 다름")
                    mc[f"{kind} / {where} / {axis} 병합"] += 1
            cell_types.update(tc)
            merge_types.update(mc)
            per_table.append({"doc_id": r["doc_id"], "table_id": row["table_id"], "truth_shape": row["truth_shape"], "ir_shape": row["ir_shape"],
                              "cell_mismatches": sum(tc.values()), "merge_errors": sum(mc.values())})
    out = {"run": run, "note": "분석 전용. 이후 holdout은 개발 참고 데이터로 간주 — 새 일반화 평가에는 미사용 자료 필요",
           "cell_mismatch_total": sum(cell_types.values()), "cell_mismatch_types": dict(cell_types.most_common()),
           "merge_error_total": sum(merge_types.values()), "merge_error_types": dict(merge_types.most_common()), "per_table": per_table}
    (B / run / "error_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
