"""E03 외부 문서 독립 채점기: 공통 중간 JSON(0.2) 출력 ↔ 외부 정답 v1 (data/canonical/external/e03_external_truth_v1.json).

파서 코드(src/parsers)를 import하지 않는다. 분모 0 = NOT_MEASURED. 각 지표에 그 지표가 기대는 정답 상태(truth_status)를 붙인다.
PROVISIONAL 정답에 대한 점수는 '잠정'이며 100%여도 검증된 정확도로 보고하지 않는다.

규칙 (실행 전 확정, 2026-10-20)
- 텍스트 비교: strict = 연속 공백을 한 칸으로 바꾼 뒤 완전 일치 / loose = 모든 공백 제거 후 일치 (PDF 셀은 줄바꿈·하이픈 뒤 공백 차이가 있어 loose를 주 지표로 쓴다)
- 문자 수준: difflib.SequenceMatcher(autojunk=False)로 정답·출력 문자열(공백 제거)의 일치 문자 수 → 재현율 = 일치/정답 길이, 정밀도 = 일치/출력 길이
- 표 매칭: PDF = 같은 page + 표 bbox IoU ≥ 0.5 / PPTX = slide_index + shape_id / DOCX = 셀 내용 일치가 가장 큰 표 (한 표는 한 번만, 일치 셀 1개 이상)
- 셀 위치 정렬: (행, 열) 격자 정렬 + (PDF) 셀 bbox IoU ≥ 0.5 정렬을 따로 잰다
- 빈 정답 셀과 NEEDS_MANUAL_REVIEW 셀은 텍스트 지표에서 빼고 개수만 기록
"""

from __future__ import annotations

import difflib
import itertools
import re
from collections import defaultdict

IOU_MIN = 0.5


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def nows(s):
    return re.sub(r"\s+", "", s or "")


def rate(n, d, truth_status=None, note=None):
    out = {"numerator": n, "denominator": d, "rate": None if d == 0 else round(n / d, 4),
           "status": "NOT_MEASURED" if d == 0 else ("PASS" if n == d else "PARTIAL" if n else "FAIL")}
    if truth_status:
        out["truth_status"] = truth_status
    if note:
        out["note"] = note
    return out


def nm(reason, truth_status="NOT_MEASURED"):
    return {"numerator": 0, "denominator": 0, "rate": None, "status": "NOT_MEASURED", "truth_status": truth_status, "note": reason}


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def char_scores(truth_text: str, out_text: str, truth_status: str) -> dict:
    a, b = nows(truth_text), nows(out_text)
    if not a:
        return {"recall": nm("정답 텍스트 없음"), "precision": nm("정답 텍스트 없음")}
    m = sum(x.size for x in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return {"recall": rate(m, len(a), truth_status), "precision": rate(m, len(b), truth_status) if b else rate(0, 0, truth_status, "출력 없음")}


def pairwise(expected: list, pos: dict, truth_status: str) -> dict:
    matched = [x for x in expected if x in pos]
    pairs = list(itertools.combinations(matched, 2))
    return {"matched_elements": rate(len(matched), len(expected), truth_status),
            "pairwise_order": rate(sum(pos[a] < pos[b] for a, b in pairs), len(pairs), truth_status)}


def table_cells_score(t_cells, ir_table, truth_status, use_loose=True):
    """격자 정렬 셀 지표. 반환: dict of counters."""
    got = {(c["row"], c["col"]): c for c in (ir_table["cells"] if ir_table else [])}
    k = defaultdict(int)
    for c in t_cells:
        a = got.get((c["row"], c["col"]))
        if c.get("status") == "NEEDS_MANUAL_REVIEW":
            k["review_excluded"] += 1
        elif nows(c["text"]):
            k["text_tot"] += 1
            k["text_strict"] += a is not None and norm(a["text"]) == norm(c["text"])
            k["text_loose"] += a is not None and nows(a["text"]) == nows(c["text"])
            if c.get("is_column_header"):
                k["hdr_tot"] += 1
                k["hdr_ok"] += a is not None and nows(a["text"]) == nows(c["text"])
                k["hdr_flag"] += a is not None and bool(a.get("is_header"))
            if c.get("is_projected_row_header"):
                k["prh_tot"] += 1
                k["prh_ok"] += a is not None and nows(a["text"]) == nows(c["text"]) and a["colspan"] == c["colspan"]
        else:
            k["empty"] += 1
        if c["rowspan"] > 1 or c["colspan"] > 1:
            k["merge_tot"] += 1
            k["merge_ok"] += a is not None and (a["rowspan"], a["colspan"]) == (c["rowspan"], c["colspan"])
    truth_pos = {(c["row"], c["col"]): c for c in t_cells}
    for (r, cc), a in got.items():
        if a["rowspan"] > 1 or a["colspan"] > 1:
            t = truth_pos.get((r, cc))
            k["false_merge"] += t is None or (t["rowspan"], t["colspan"]) != (a["rowspan"], a["colspan"])
    return k


# =================== 형식별 ===================

def grade_pdf(ir, truth):
    tt = truth["tables"]
    irt = ir["tables"]
    used, match, rows = set(), {}, []
    for t in tt:
        cands = [(iou(x["location"]["bbox"], t["bbox"]), x) for x in irt
                 if x["table_id"] not in used and x["location"].get("page") == t["page"] and "bbox" in x["location"]]
        cands = [c for c in cands if c[0] >= IOU_MIN]
        best = max(cands, key=lambda c: c[0], default=None)
        if best:
            used.add(best[1]["table_id"])
            match[t["table_id"]] = best[1]
        rows.append({"table_id": t["table_id"], "page": t["page"], "truth_shape": [t["n_rows"], t["n_cols"]],
                     "matched_ir_table": best[1]["table_id"] if best else None, "table_bbox_iou": round(best[0], 3) if best else None,
                     "ir_shape": [best[1]["n_rows"], best[1]["n_cols"]] if best else None,
                     "ir_tables_on_page": sum(1 for x in irt if x["location"].get("page") == t["page"])})
    K = defaultdict(int)
    bbox_hit = bbox_tot = 0
    bbox_ious = []
    page_text = defaultdict(str)
    for b in ir["blocks"]:
        page_text[b["location"].get("page")] += nows(b["text"])
    for x in irt:
        page_text[x["location"].get("page")] += "".join(nows(c["text"]) for c in x["cells"])
    found = found_tot = 0
    for t in tt:
        k = table_cells_score(t["cells"], match.get(t["table_id"]), "VERIFIED_OFFICIAL")
        for a, v in k.items():
            K[a] += v
        ir_t = match.get(t["table_id"])
        for c in t["cells"]:
            if not nows(c["text"]) or c.get("status") == "NEEDS_MANUAL_REVIEW":
                continue
            found_tot += 1
            found += nows(c["text"]) in page_text[t["page"]]
            bbox_tot += 1
            if ir_t:
                best = max(((iou(a["location"]["bbox"], c["bbox"]), a) for a in ir_t["cells"] if "bbox" in a.get("location", {})), key=lambda z: z[0], default=(0, None))
                if best[0] >= IOU_MIN:
                    bbox_ious.append(best[0])
                    bbox_hit += nows(best[1]["text"]) == nows(c["text"])
    O = "VERIFIED_OFFICIAL"
    no_tab = "IR에 표 없음 (파서 미지원 또는 미검출)" if not irt else None
    return {
        "table_detection": {"recall": rate(len(match), len(tt), O), "precision": rate(len(match), len(irt), O, "출력 표 0개" if not irt else None),
                            "table_bbox_iou_mean": round(sum(r["table_bbox_iou"] for r in rows if r["table_bbox_iou"]) / len(match), 3) if match else None},
        "structure": {"rows_cols_equal": rate(sum(1 for r in rows if r["ir_shape"] == r["truth_shape"]), len(tt), O)},
        "cells": {"text_loose_grid": rate(K["text_loose"], K["text_tot"], O, no_tab), "text_strict_grid": rate(K["text_strict"], K["text_tot"], O, no_tab),
                  "text_loose_bbox_aligned": rate(bbox_hit, bbox_tot, O, no_tab),
                  "cell_bbox_iou_ge_0_5": rate(len(bbox_ious), bbox_tot, O, no_tab),
                  "cell_bbox_iou_mean": round(sum(bbox_ious) / len(bbox_ious), 3) if bbox_ious else None,
                  "merge_spans": rate(K["merge_ok"], K["merge_tot"], O, no_tab), "false_merges": K["false_merge"],
                  "column_header_text": rate(K["hdr_ok"], K["hdr_tot"], O, no_tab),
                  "column_header_flag": rate(K["hdr_flag"], K["hdr_tot"], O, "출력이 헤더 여부를 표시한 비율"),
                  "projected_row_header": rate(K["prh_ok"], K["prh_tot"], O, no_tab),
                  "text_found_ignoring_structure": rate(found, found_tot, O, "같은 쪽 추출 텍스트 어딘가에 포함 (공백 무시, 짧은 값은 우연 일치 가능 — 상한값)"),
                  "empty_truth_cells": K["empty"], "review_excluded_cells": K["review_excluded"]},
        "tables": rows,
        "body_text": nm("PDF 본문 정답 없음 (PubTables는 표만 주석)"), "reading_order": nm("PDF 읽기 순서 정답 없음"),
    }


def docx_ir_parts(ir):
    body = [b for b in ir["blocks"] if b["location"].get("part", "body") == "body"]
    seq = ir["format_specific"].get("reading_sequence") or [b["block_id"] for b in ir["blocks"]]
    pos = {x: i for i, x in enumerate(seq)}
    return sorted(body, key=lambda b: pos.get(b["block_id"], 1e9)), pos


def match_tables_by_content(truth_tables, ir_tables):
    scores = []
    for t in truth_tables:
        tc = {(c["row"], c["col"]): nows(c["text"]) for c in t["cells"] if nows(c["text"])}
        for x in ir_tables:
            got = {(c["row"], c["col"]): nows(c["text"]) for c in x["cells"]}
            s = sum(1 for p, v in tc.items() if got.get(p) == v)
            if s:
                scores.append((s, t["table_id"], x["table_id"]))
    match, ut, ui = {}, set(), set()
    for s, a, b in sorted(scores, reverse=True):
        if a not in ut and b not in ui:
            match[a] = b
            ut.add(a)
            ui.add(b)
    return match


def grade_docx(ir, truth, items, d_rec):
    body_ir, pos = docx_ir_parts(ir)
    tb = truth["blocks"]
    st_text = items["body_text"]
    exact = sum(1 for b in tb if any(norm(x["text"]) == norm(b["text"]) for x in body_ir))
    official = [b for b in tb if b.get("text_status") == "VERIFIED_OFFICIAL"]
    out = {"body_paragraph_exact": rate(exact, len(tb), "PROVISIONAL" if not official else "MIXED"),
           "body_char": char_scores("".join(b["text"] for b in tb), "".join(x["text"] for x in body_ir), "PROVISIONAL")}
    if official:
        out["body_paragraph_exact_official_only"] = rate(sum(1 for b in official if any(norm(x["text"]) == norm(b["text"]) for x in body_ir)),
                                                         len(official), "VERIFIED_OFFICIAL", "source.md와 일치하는 문단만")
    irt = {x["table_id"]: x for x in ir["tables"]}
    m = match_tables_by_content(truth["tables"], ir["tables"])
    K = defaultdict(int)
    shape_eq = 0
    for t in truth["tables"]:
        x = irt.get(m.get(t["table_id"]))
        for a, v in table_cells_score(t["cells"], x, "PROVISIONAL").items():
            K[a] += v
        shape_eq += bool(x) and (x["n_rows"], x["n_cols"]) == (t["n_rows"], t["n_cols"])
    P = "PROVISIONAL"
    out.update({
        "table_detection": {"recall": rate(len(m), len(truth["tables"]), P), "precision": rate(len(m), len(ir["tables"]), P),
                            "missed_tables_in_containers": sum(1 for t in truth["tables"] if t["table_id"] not in m and "sdt" in t["container"])},
        "structure": {"rows_cols_equal": rate(shape_eq, len(truth["tables"]), P)},
        "cells": {"text_strict_grid": rate(K["text_strict"], K["text_tot"], P), "text_loose_grid": rate(K["text_loose"], K["text_tot"], P),
                  "merge_spans": rate(K["merge_ok"], K["merge_tot"], P), "false_merges": K["false_merge"], "empty_truth_cells": K["empty"]},
    })
    # 읽기 순서 (본문 문단·표)
    ipos = {}
    for b in tb:
        hit = next((x for x in body_ir if norm(x["text"]) == norm(b["text"])), None)
        if hit:
            ipos[b["block_id"]] = pos[hit["block_id"]]
    for tid, xid in m.items():
        ipos[tid] = pos.get(xid, 1e9)
    out["reading_order"] = pairwise(truth["body_order"], ipos, P)
    all_text = nows(" ".join(b["text"] for b in ir["blocks"]) + " ".join(c["text"] for x in ir["tables"] for c in x["cells"]))
    out["footnotes"] = rate(sum(nows(f["text"]) in all_text for f in truth["footnotes"]), len(truth["footnotes"]), P) if truth["footnotes"] else nm("정답에 각주 없음", P)
    ins, dels = truth["tracked_changes"]["insertions"], truth["tracked_changes"]["deletions"]
    out["tracked_insertions_included"] = rate(sum(nows(t) in all_text for t in ins), len(ins), P) if ins else nm("삽입 변경 없음", P)
    out["tracked_deletions_excluded"] = rate(sum(nows(t) not in all_text for t in dels), len(dels), P) if dels else nm("삭제 변경 없음", P)
    hf = [("header", h["text"]) for h in truth["headers"]] + [("footer", f["text"]) for f in truth["footers"]]
    out["header_footer"] = rate(sum(any(x["location"].get("part") == part and norm(x["text"]) == norm(t) for x in ir["blocks"]) for part, t in hf), len(hf), P) if hf else nm("머리말·꼬리말 없음", P)
    out["source_location"] = nm("외부 DOCX 정답에 body_index 체계 위치를 만들지 않음 (콘텐츠 컨트롤 등 컨테이너 때문에 정의가 갈림)", P)
    return out


def grade_pptx(ir, truth, items):
    P = "PROVISIONAL"
    blocks = ir["blocks"]
    by_key = {(b["location"].get("slide_index"), b["location"].get("shape_id")): b for b in blocks if b["location"].get("part", "slide") == "slide"}
    slide_text = defaultdict(str)
    for b in blocks:
        slide_text[b["location"].get("slide_index")] += nows(b["text"])
    for x in ir["tables"]:
        slide_text[x["location"].get("slide_index")] += "".join(nows(c["text"]) for c in x["cells"])
    shp = [(s["slide_index"], x) for s in truth["slides"] for x in s["shapes"] if x["kind"] in ("sp", "cxnSp") and x["text"].strip()]
    exact = sum(1 for si, x in shp if (b := by_key.get((si, x["shape_id"]))) and norm(b["text"]) == norm(x["text"]))
    located = sum(1 for si, x in shp if any(b["location"].get("slide_index") == si and norm(b["text"]) == norm(x["text"]) and b["location"].get("shape_id") == x["shape_id"] for b in blocks))
    grouped = [(si, x) for si, x in shp if len(x["nested_path"]) > 1]
    g_found = sum(1 for si, x in grouped if nows(x["text"]) in slide_text[si])
    g_path = sum(1 for si, x in grouped if (b := by_key.get((si, x["shape_id"]))) and b["location"].get("nested_path") == x["nested_path"])
    all_truth = "".join(x["text"] for s in truth["slides"] for x in s["shapes"])
    out = {"slides_count_equal": (ir["document"].get("units_of_division") or {}).get("slides") == len(truth["slides"]),
           "shape_text_exact": rate(exact, len(shp), P), "shape_char": char_scores(all_truth, "".join(b["text"] for b in blocks if b["location"].get("part") != "notes"), P),
           "shape_location_slide_and_id": rate(located, len(shp), P),
           "group_child_text_found": rate(g_found, len(grouped), P) if grouped else nm("그룹 안 텍스트 도형 없음", P),
           "group_nested_path_equal": rate(g_path, len(grouped), P) if grouped else nm("그룹 안 텍스트 도형 없음", P)}
    # 표
    irt = {(x["location"].get("slide_index"), x["location"].get("shape_id")): x for x in ir["tables"]}
    tts = [(s["slide_index"], t) for s in truth["slides"] for t in s["tables"]]
    K = defaultdict(int)
    shape_eq = det = 0
    struct_status = "VERIFIED_OFFICIAL" if any(t.get("structure_status") for _, t in tts) else P
    for si, t in tts:
        x = irt.get((si, t["shape_id"]))
        det += x is not None
        shape_eq += bool(x) and (x["n_rows"], x["n_cols"]) == (t["n_rows"], t["n_cols"])
        for a, v in table_cells_score(t["cells"], x, P).items():
            K[a] += v
    out.update({"table_detection": {"recall": rate(det, len(tts), P), "precision": rate(det, len(ir["tables"]), P)},
                "structure": {"rows_cols_equal": rate(shape_eq, len(tts), struct_status)},
                "cells": {"text_strict_grid": rate(K["text_strict"], K["text_tot"], P), "text_loose_grid": rate(K["text_loose"], K["text_tot"], P),
                          "merge_spans": rate(K["merge_ok"], K["merge_tot"], struct_status), "false_merges": K["false_merge"], "empty_truth_cells": K["empty"]}})
    # SmartArt·차트·노트
    sa = [(s["slide_index"], n) for s in truth["slides"] for d in s["smartart"] for n in (d.get("node_texts_official") or d["node_texts"])]
    sa_status = "VERIFIED_OFFICIAL" if any(d.get("node_texts_official") for s in truth["slides"] for d in s["smartart"]) else P
    out["smartart_node_text_found"] = rate(sum(nows(n) in slide_text[si] for si, n in sa), len(sa), sa_status) if sa else nm("SmartArt 없음", P)
    ch = [(s["slide_index"], t) for s in truth["slides"] for c in s["charts"] for t in c["texts"]]
    out["chart_text_found"] = rate(sum(nows(t) in slide_text[si] for si, t in ch), len(ch), P) if ch else nm("차트 없음", P)
    notes = [(s["slide_index"], s["notes"]) for s in truth["slides"] if s["notes"].strip()]
    out["notes_exact"] = rate(sum(any(b["location"].get("part") == "notes" and b["location"].get("slide_index") == si and norm(b["text"]) == norm(n) for b in blocks)
                                  for si, n in notes), len(notes), P) if notes else nm("노트 텍스트 없음", P)
    out["reading_order"] = nm("PPTX 논리 읽기 순서 정답 없음 (수동 검수 필요)")
    return out


def grade(ir: dict | None, doc: dict) -> dict:
    if doc.get("truth") is None:
        return {"doc_id": doc["doc_id"], "status": "NOT_MEASURED", "reason": "정답 없음"}
    if ir is None:
        return {"doc_id": doc["doc_id"], "status": "PARSER_FAILED", "reason": "파서 출력 없음 (실행 실패)"}
    fmt = doc["format"]
    body = grade_pdf(ir, doc["truth"]) if fmt == "pdf" else grade_docx(ir, doc["truth"], doc["items"], doc) if fmt == "docx" else grade_pptx(ir, doc["truth"], doc["items"])
    return {"doc_id": doc["doc_id"], "status": "MEASURED", "format": fmt, "parser": ir["parser"]["name"], "metrics": body,
            "ir_diagnostics": [f"{d['code']}: {d['message']}" for d in ir.get("diagnostics", [])]}
