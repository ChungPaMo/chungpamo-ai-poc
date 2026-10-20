"""외부 PPTX 정답(XML 직접 판독, PROVISIONAL)을 제3자 판독(ts-pptx inspect-surface 스냅숏)과 대조 — 교차 확인 기록만, 정답 상태는 바꾸지 않는다.

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_truth_crosscheck.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"
SNAP = ROOT / "data" / "raw" / "external_documents" / "truth_sources" / "ts-pptx_inspect-surface.snapshot.json"
OUT = ROOT / "results" / "E03_document_parsers" / "external_truth_v1" / "pptx_snapshot_crosscheck.json"


def nows(s):
    return re.sub(r"\s+", "", s or "")


def main() -> int:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    rows = []
    for d in truth["documents"]:
        if d["format"] != "pptx" or d["file"] not in snap:
            continue
        s_slides = snap[d["file"]]["slides"]
        agree = total = only_truth = only_snap = 0
        diffs = []
        for ts, ss in zip(d["truth"]["slides"], s_slides):
            mine = {x["shape_id"]: nows(x["text"]) for x in ts["shapes"] if x["kind"] in ("sp", "cxnSp") and nows(x["text"])}
            theirs = {e["id"]: nows(e.get("text")) for e in ss["elements"] if nows(e.get("text")) and e.get("kind") not in ("table", "chart", "diagram", "graphicFrame")}
            for k in set(mine) | set(theirs):
                if k in mine and k in theirs:
                    total += 1
                    agree += mine[k] == theirs[k]
                    if mine[k] != theirs[k]:
                        diffs.append({"slide": ts["slide_index"], "shape_id": k, "kind": "텍스트 다름"})
                elif k in mine:
                    only_truth += 1
                    diffs.append({"slide": ts["slide_index"], "shape_id": k, "kind": "스냅숏에 없음"})
                else:
                    only_snap += 1
                    diffs.append({"slide": ts["slide_index"], "shape_id": k, "kind": "정답에 없음"})
        rows.append({"doc_id": d["doc_id"], "split": d["split"], "slides_truth": len(d["truth"]["slides"]), "slides_snapshot": len(s_slides),
                     "text_shapes_both": total, "text_equal": agree, "only_in_truth": only_truth, "only_in_snapshot": only_snap, "differences": diffs[:20]})
    OUT.write_text(json.dumps({"note": "제3자 판독과의 일치는 교차 확인일 뿐 사람 검수가 아니다 — 정답 상태는 PROVISIONAL 유지. "
                                       "스냅숏은 자리표시자(제목 등) 도형을 요소 목록에 넣지 않으므로 '스냅숏에 없음'은 자리표시자 도형이다 (2026-10-20 확인)",
                               "snapshot": "ts-pptx test/read/fixtures/inspect-surface.snapshot.json @11611de", "documents": rows},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps([{k: r[k] for k in ("doc_id", "text_shapes_both", "text_equal", "only_in_truth", "only_in_snapshot")} for r in rows], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
