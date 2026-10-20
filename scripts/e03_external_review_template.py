"""외부 DOCX·PPTX 잠정 정답(PROVISIONAL)의 사람 검수 목록 생성 — 위치·항목만 쓰고 텍스트는 쓰지 않는다 (검수자는 로컬 정답 파일과 뷰어를 대조).

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_review_template.py

출력: results/E03_document_parsers/external_truth_v1/manual_review_template.csv (검수 결과 칸은 비워 둔다)
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"
OUT = ROOT / "results" / "E03_document_parsers" / "external_truth_v1" / "manual_review_template.csv"
COLS = ["review_id", "doc_id", "split", "format", "item", "viewer_location", "truth_json_path", "current_status",
        "author", "independent_reviewer", "result(MATCH/MISMATCH/UNDECIDABLE)", "corrected_value_ref", "note", "reviewed_at"]


def main() -> int:
    t = json.loads(TRUTH.read_text(encoding="utf-8"))
    rows = []

    def add(d, item, where, path, status="PROVISIONAL"):
        rows.append({"review_id": f"R{len(rows) + 1:04d}", "doc_id": d["doc_id"], "split": d["split"], "format": d["format"], "item": item,
                     "viewer_location": where, "truth_json_path": path, "current_status": status})
    for di, d in enumerate(t["documents"]):
        tr, base = d.get("truth"), f"documents[{di}].truth"
        if not tr or d["format"] == "pdf":
            continue
        if d["format"] == "docx":
            for i, b in enumerate(tr["blocks"]):
                if b.get("text_status") == "VERIFIED_OFFICIAL":
                    continue
                add(d, "본문 문단 텍스트", f"본문 {i + 1}번째 비어 있지 않은 문단 (컨테이너 {b['in_container'] or '없음'})", f"{base}.blocks[{i}].text")
            add(d, "본문 읽기 순서 (문단·표)", "문서 처음부터 끝까지", f"{base}.body_order")
            for ti, tb in enumerate(tr["tables"]):
                add(d, "표 행·열 수", f"문서 순서 {ti + 1}번째 표 ({tb['n_rows']}×{tb['n_cols']}, 위치 {'/'.join(tb['container'])})", f"{base}.tables[{ti}]")
                for ci, c in enumerate(tb["cells"]):
                    add(d, "셀 텍스트·병합", f"표 {ti + 1} 행 {c['row']} 열 {c['col']} (span {c['rowspan']}×{c['colspan']})", f"{base}.tables[{ti}].cells[{ci}]")
            for k in ("headers", "footers", "footnotes", "endnotes"):
                for i, _ in enumerate(tr.get(k, [])):
                    add(d, {"headers": "머리말", "footers": "꼬리말", "footnotes": "각주", "endnotes": "미주"}[k], f"{k} {i + 1}", f"{base}.{k}[{i}]")
            for k in ("insertions", "deletions"):
                for i, _ in enumerate(tr["tracked_changes"][k]):
                    add(d, "변경 추적 " + ("삽입" if k == "insertions" else "삭제"), f"변경 추적 {k} {i + 1} (수락 상태 기준)", f"{base}.tracked_changes.{k}[{i}]")
        else:
            for si, s in enumerate(tr["slides"]):
                for xi, x in enumerate(s["shapes"]):
                    if x["text"].strip():
                        add(d, "도형 텍스트·그룹 경로", f"슬라이드 {s['slide_index']} 도형 id {x['shape_id']} (중첩 깊이 {len(x['nested_path'])})", f"{base}.slides[{si}].shapes[{xi}]")
                for ti, tb in enumerate(s["tables"]):
                    official = bool(tb.get("structure_status"))
                    add(d, "표 행·열 수·병합", f"슬라이드 {s['slide_index']} 표 도형 id {tb['shape_id']}", f"{base}.slides[{si}].tables[{ti}]",
                        "VERIFIED_OFFICIAL (확인 선택)" if official else "PROVISIONAL")
                    for ci, c in enumerate(tb["cells"]):
                        if c.get("status") == "VERIFIED_OFFICIAL":
                            continue
                        add(d, "셀 텍스트", f"슬라이드 {s['slide_index']} 표 id {tb['shape_id']} 행 {c['row']} 열 {c['col']}", f"{base}.slides[{si}].tables[{ti}].cells[{ci}]")
                for ai, a in enumerate(s["smartart"]):
                    if not a.get("node_texts_official"):
                        add(d, "SmartArt 노드 텍스트", f"슬라이드 {s['slide_index']} SmartArt id {a['shape_id']} (노드 {len(a['node_texts'])}개)", f"{base}.slides[{si}].smartart[{ai}]")
                for ci, c in enumerate(s["charts"]):
                    add(d, "차트 텍스트(제목·항목·계열)", f"슬라이드 {s['slide_index']} 차트 id {c['shape_id']} (문자열 {len(c['texts'])}개)", f"{base}.slides[{si}].charts[{ci}]")
                if s["notes"].strip():
                    add(d, "발표자 노트", f"슬라이드 {s['slide_index']} 노트", f"{base}.slides[{si}].notes")
            add(d, "논리 읽기 순서 (현재 정답 없음 → 검수자가 순서 정의)", "슬라이드별", "(신규 작성)", "NOT_MEASURED")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n", restval="")
    w.writeheader()
    w.writerows(rows)
    OUT.write_text(buf.getvalue(), encoding="utf-8-sig", newline="\n")
    from collections import Counter
    print(json.dumps({"rows": len(rows), "by_doc": dict(Counter(r["doc_id"] for r in rows))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
