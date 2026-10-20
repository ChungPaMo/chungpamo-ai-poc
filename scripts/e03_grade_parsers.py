"""E03 직접 파서 독립 채점기: 공통 중간 JSON(0.2) 출력을 E03 정답 명세·위치 메타데이터와 대조.

파서 코드(src/parsers)를 import하지 않는다. 입력은 IR JSON(dict)뿐이다.
분모가 0이면 NOT_MEASURED. 상태 PASS/PARTIAL/FAIL은 '분모 전부 일치/일부/전무'를 뜻하는 사실 표기이며 채택 기준이 아니다.

공통 규칙
- 텍스트 비교: 공백 연속을 한 칸으로 바꾸고 앞뒤 공백 제거 후 완전 일치 (E04 예비 분석과 같은 규칙)
- 표 매칭: DOCX = table_index, PPTX = slide_index + shape_id, PDF = 같은 page + 표 영역 IoU ≥ 0.5 (임시 기준, intermediate_representation.md §7)
- 표 조각의 IR 행 i ↔ 정답 조각의 logical_rows[i-1] (E04 예비 분석과 같은 정렬)
"""

from __future__ import annotations

import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data" / "canonical" / "e03_document_truth_v1.json"
LOCS = ROOT / "data" / "canonical" / "e03_document_locations_v1.json"
IOU_MIN = 0.5
FIELD_GROUPS = {"component_id": "id", "order_id": "id", "qty_per": "quantity", "order_qty": "quantity", "on_hand_qty": "quantity",
                "planned_qty": "quantity", "unit_cost": "money", "inventory_value_krw": "money", "due_date": "date"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOKEN_RES = {"date": re.compile(r"\d{4}-\d{2}-\d{2}"), "qty_unit": re.compile(r"\d[\d,]*(?:\.\d+)?\s?(?:kg|g|EA)\b")}


def norm(s) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def nows(s) -> str:
    return re.sub(r"\s+", "", s or "")


def rate(n: int, d: int, note: str | None = None) -> dict:
    out = {"numerator": n, "denominator": d, "rate": None if d == 0 else round(n / d, 4),
           "status": "NOT_MEASURED" if d == 0 else ("PASS" if n == d else "PARTIAL" if n else "FAIL")}
    if note:
        out["note"] = note
    return out


def iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def load_truth() -> tuple[dict, dict]:
    return json.loads(TRUTH.read_text(encoding="utf-8")), json.loads(LOCS.read_text(encoding="utf-8"))["documents"]


# ---- 위치 단위·세부 위치 ----

def unit_of(loc: dict, fmt: str):
    if fmt == "pdf":
        return loc.get("page")
    if fmt == "pptx":
        return (loc.get("slide_index"), loc.get("part", "slide"))
    return loc.get("part", "body")


def fine_match(ir_loc: dict, t_loc: dict, fmt: str) -> bool:
    if ir_loc is None:
        return False
    if fmt == "pdf":
        return ir_loc.get("page") == t_loc["page"] and "bbox" in ir_loc and iou(ir_loc["bbox"], t_loc["bbox"]) >= IOU_MIN
    if fmt == "pptx":
        if t_loc.get("part") == "notes":
            return ir_loc.get("part") == "notes" and ir_loc.get("slide_index") == t_loc["slide_index"]
        return ir_loc.get("slide_index") == t_loc["slide_index"] and ir_loc.get("shape_id") == t_loc["shape_id"]
    keys = [k for k in ("part", "body_index", "section_index", "paragraph_index") if k in t_loc]
    return all(ir_loc.get(k) == t_loc[k] for k in keys)


# ---- 문서 1개 채점 ----

def grade(ir: dict | None, doc: dict, truth: dict, locs: dict) -> dict:
    """doc: 매니페스트 행(doc_id, format, content_set). ir None이면 미측정."""
    doc_id = doc["doc_id"]
    if ir is None:
        return {"doc_id": doc_id, "status": "NOT_MEASURED", "reason": "입력 문서 없음 (로컬 전용 보류 문서) 또는 파서 실패 — IR 없음"}
    fmt = {"docx": "docx", "pptx": "pptx", "pdf_text": "pdf"}[doc["format"]]
    cs = truth["content_sets"][doc["content_set"]]
    tblocks = {b["block_id"]: b for b in cs["blocks"]}
    ttables = {t["table_id"]: t for t in cs["tables"]}
    L = locs[doc_id]
    tdoc = next(d for d in truth["documents"] if d["doc_id"] == doc_id)
    blocks, tables = ir["blocks"], ir["tables"]
    seq = ir["format_specific"].get("reading_sequence") or [b["block_id"] for b in sorted(blocks, key=lambda b: b["order"])]
    pos = {x: i for i, x in enumerate(seq)}
    by_unit = defaultdict(list)
    for b in sorted(blocks, key=lambda b: pos.get(b["block_id"], 1e9)):
        by_unit[unit_of(b["location"], fmt)].append(b)

    # 1. 텍스트 블록·캡션 (출현 단위)
    occ = [("block", bid, tblocks[bid]["text"], l) for bid, ls in L["blocks"].items() for l in ls]
    for tid, tl in L["tables"].items():
        caps = [tl["caption_location"]] if "caption_location" in tl else [f.get("caption_location") for f in tl["fragments"]]
        occ += [("caption", tid, ttables[tid]["caption"], {**c, "format": fmt}) for c in caps if c]
    unit_seq = defaultdict(list)   # 단위(page/slide/part) 안의 IR 요소 순서 (블록·표)
    for x in seq:
        e = next((b for b in blocks if b["block_id"] == x), None) or next(t for t in tables if t["table_id"] == x)
        unit_seq[unit_of(e["location"], fmt)].append(x)
    occ_rows = []
    for kind, eid, text, tl in occ:
        u = unit_of(tl if fmt != "docx" else {"part": tl.get("part", "body")}, fmt)
        same = by_unit.get(u, [])
        exact = [b for b in same if norm(b["text"]) == norm(text)]
        found = nows(text) in nows("".join(b["text"] for b in same))
        located = any(fine_match(b["location"], tl, fmt) for b in exact)
        occ_rows.append({"kind": kind, "id": eid, "unit": str(u), "exact": bool(exact), "found_ignoring_whitespace": found, "fine_location": located,
                         "ir_types": sorted({b["type"] for b in exact}),
                         "rank_in_unit": [unit_seq[u].index(exact[0]["block_id"]) + 1, len(unit_seq[u])] if exact else None})
    sel = lambda k: [o for o in occ_rows if o["kind"] == k]
    text_metrics = {}
    for k in ("block", "caption"):
        rows = sel(k)
        text_metrics[k] = {"exact": rate(sum(o["exact"] for o in rows), len(rows)),
                           "found_ignoring_whitespace": rate(sum(o["found_ignoring_whitespace"] for o in rows), len(rows)),
                           "fine_location": rate(sum(o["fine_location"] for o in rows), len(rows))}

    # 2. 표 검출 (조각 단위 매칭)
    frags = [(tid, f) for tid, tl in L["tables"].items() for f in tl["fragments"]]
    used, match, frag_rows = set(), {}, []
    for tid, f in frags:
        cands = []
        for t in tables:
            tl = t["location"]
            if t["table_id"] in used:
                continue
            if fmt == "docx" and tl.get("table_index") == f["table_index"]:
                cands.append((1.0, t))
            elif fmt == "pptx" and tl.get("slide_index") == f["slide_index"] and tl.get("shape_id") == f["shape_id"]:
                cands.append((1.0, t))
            elif fmt == "pdf" and tl.get("page") == f["page"]:
                v = iou(tl["bbox"], f["bbox"])
                if v >= IOU_MIN:
                    cands.append((v, t))
        best = max(cands, key=lambda x: x[0], default=None)
        row = {"table_id": tid, "fragment_index": f["fragment_index"], "matched_ir_table": best[1]["table_id"] if best else None}
        if fmt == "pdf":
            row["table_bbox_iou"] = round(best[0], 3) if best else None
        if best:
            used.add(best[1]["table_id"])
            match[(tid, f["fragment_index"])] = best[1]
            row.update({"ir_rows": best[1]["n_rows"], "expected_rows": len(f["logical_rows"]), "ir_cols": best[1]["n_cols"], "expected_cols": ttables[tid]["n_cols"]})
        frag_rows.append(row)
    detection = {"recall": rate(len(match), len(frags)), "precision": rate(len(match), len(tables)), "ir_tables": len(tables), "truth_fragments": len(frags)}

    # 3~4. 셀 텍스트·병합·셀 위치 / 값 조회표
    cell_hit = cell_tot = head_hit = head_tot = merge_hit = merge_tot = cell_loc_hit = 0
    value_at = {}
    for tid, f in frags:
        t = ttables[tid]
        tcells = {(c["row"], c["col"]): c for c in t["cells"]}
        ir_t = match.get((tid, f["fragment_index"]))
        got = {(c["row"], c["col"]): c for c in ir_t["cells"]} if ir_t else {}
        for i, lr in enumerate(f["logical_rows"], start=1):
            for c in range(1, t["n_cols"] + 1):
                tc = tcells.get((lr, c))
                if tc is None:
                    continue
                a = got.get((i, c))
                hit = a is not None and norm(a["text"]) == norm(tc["text"])
                cell_tot += 1
                cell_hit += hit
                if a is not None and (tid, lr, c) not in value_at:
                    value_at[(tid, lr, c)] = a
                if tc["is_header"]:
                    head_tot += 1
                    head_hit += hit
                if tc["rowspan"] > 1 or tc["colspan"] > 1:
                    merge_tot += 1
                    merge_hit += a is not None and (a["rowspan"], a["colspan"]) == (tc["rowspan"], tc["colspan"])
                cl = f["cells"].get(f"{lr},{c}")
                if a is not None and cl is not None:
                    if fmt == "pdf":
                        cell_loc_hit += a.get("location", {}).get("page") == cl["page"] and iou(a["location"]["bbox"], cl["bbox"]) >= IOU_MIN
                    elif fmt == "pptx":
                        cell_loc_hit += (a.get("location", {}).get("row"), a.get("location", {}).get("col")) == (cl["table_row"], cl["table_col"]) \
                            and a["location"].get("shape_id") == f["shape_id"]
                    else:
                        cell_loc_hit += (a.get("location", {}).get("row"), a.get("location", {}).get("col")) == (cl["row"], cl["col"]) \
                            and a["location"].get("table_index") == f["table_index"]
    # 구조 무시 텍스트 보존: 정답 셀 텍스트가 같은 단위(page/slide/part)의 IR 텍스트(블록 + 표 셀) 안에 있는가 (공백 무시)
    unit_text = defaultdict(str)
    for b in blocks:
        unit_text[unit_of(b["location"], fmt)] += nows(b["text"])
    for t in tables:
        unit_text[unit_of(t["location"], fmt)] += "".join(nows(c["text"]) for c in t["cells"])
    found_tot = found_hit = 0
    for tid, f in frags:
        tcells = {(c["row"], c["col"]): c for c in ttables[tid]["cells"]}
        u = unit_of(f, fmt) if fmt != "docx" else "body"
        for lr in f["logical_rows"]:
            for c in range(1, ttables[tid]["n_cols"] + 1):
                tc = tcells.get((lr, c))
                if tc is not None and nows(tc["text"]):
                    found_tot += 1
                    found_hit += nows(tc["text"]) in unit_text[u]
    no_table_note = "IR에 표 구조 없음 (표 미검출·파서 미지원)" if not tables else None
    cells = {"text": rate(cell_hit, cell_tot, no_table_note), "header_text": rate(head_hit, head_tot, no_table_note),
             "merge_spans": rate(merge_hit, merge_tot, no_table_note), "fine_location": rate(cell_loc_hit, cell_tot, no_table_note),
             "text_found_ignoring_structure": rate(found_hit, found_tot, "구조 무시·공백 무시 포함 여부 (짧은 값은 다른 위치 텍스트와 우연히 일치할 수 있어 상한값)")}

    # 5. 숫자·단위·날짜 (표 셀 원문 보존) + 블록 안 토큰
    groups = defaultdict(lambda: [0, 0])
    for v in cs["extracted_values"]:
        s = v["source"]
        a = value_at.get((s["table_id"], s["row"], s["col"]))
        g = FIELD_GROUPS.get(v["field"], "money" if v["field"].startswith("cost_") else "other")
        groups[g][1] += 1
        groups[g][0] += a is not None and norm(a["text"]) == norm(v["raw"])
        if v["unit"] and v["unit"] in v["raw"]:
            groups["unit"][1] += 1
            groups["unit"][0] += a is not None and norm(a["text"]) == norm(v["raw"])
    for tid, tl in L["tables"].items():
        t = ttables[tid]
        unit_cols = {c["col"] for c in t["cells"] if c["is_header"] and norm(c["text"]).startswith("단위")}
        rows_here = {lr for f in tl["fragments"] for lr in f["logical_rows"]}
        for c in t["cells"]:
            if c["row"] not in rows_here:
                continue
            if c["col"] in unit_cols and not c["is_header"]:
                a = value_at.get((tid, c["row"], c["col"]))
                groups["unit"][1] += 1
                groups["unit"][0] += a is not None and norm(a["text"]) == norm(c["text"])
            if c["is_header"] and DATE_RE.match(norm(c["text"])):
                a = value_at.get((tid, c["row"], c["col"]))
                groups["date"][1] += 1
                groups["date"][0] += a is not None and norm(a["text"]) == norm(c["text"])
    all_text = norm(" ".join(b["text"] for b in blocks))
    for bid in L["blocks"]:
        for kind, rx in TOKEN_RES.items():
            for tok in rx.findall(tblocks[bid]["text"]):
                groups[f"block_{kind}"][1] += 1
                groups[f"block_{kind}"][0] += norm(tok) in all_text
    values = {k: rate(*groups[k]) for k in ("id", "quantity", "money", "unit", "date", "block_date", "block_qty_unit")}

    # 6. 읽기 순서 (본문 요소: 머리말·꼬리말 제외, 다조각 표는 첫 조각)
    furniture = {bid for bid, b in tblocks.items() if b["type"] in ("header", "footer")}
    furniture |= {bid for bid, ls in L["blocks"].items() if any(l.get("part") in ("header", "footer") for l in ls)}
    if tdoc["layout"].get("header_on_each_page"):
        furniture.add(tdoc["layout"]["header_on_each_page"])
    if fmt == "docx":
        expected = [x for x in tdoc["layout"]["body_order"] if x not in furniture]
    else:
        def key(l):
            if fmt == "pdf":
                return (l["page"], l["bbox"][1], l["bbox"][0])
            return (l["slide_index"], l.get("part") == "notes", l.get("top", 0), l.get("left", 0))
        el = [(key(ls[0]), bid) for bid, ls in L["blocks"].items() if bid not in furniture]
        el += [(key(tl["fragments"][0]), tid) for tid, tl in L["tables"].items()]
        expected = [x for _, x in sorted(el)]
    ir_pos, how = {}, {}
    for x in expected:
        if x in ttables:
            t = match.get((x, 0))
            if t:
                ir_pos[x], how[x] = pos[t["table_id"]], "table_match"
            continue
        tl = L["blocks"][x][0]
        same = by_unit.get(unit_of(tl if fmt != "docx" else {"part": tl.get("part", "body")}, fmt), [])
        ex = [b for b in same if norm(b["text"]) == norm(tblocks[x]["text"])]
        pre = [b for b in same if nows(tblocks[x]["text"])[:15] and nows(b["text"]).startswith(nows(tblocks[x]["text"])[:15])]
        if ex or pre:
            ir_pos[x], how[x] = pos[(ex or pre)[0]["block_id"]], "exact" if ex else "prefix15"
    matched = [x for x in expected if x in ir_pos]
    pairs = list(itertools.combinations(matched, 2))
    conc = sum(ir_pos[a] < ir_pos[b] for a, b in pairs)
    order = {"expected_sequence": expected, "ir_sequence": sorted(matched, key=lambda x: ir_pos[x]), "matched_elements": rate(len(matched), len(expected)),
             "pairwise_order": rate(conc, len(pairs)), "match_method": how,
             "exact_sequence": len(matched) == len(expected) and conc == len(pairs)}

    # 7. 표 조각 연결 (페이지·슬라이드)
    link_tot = link_ok = rep_ok = 0
    link_rows = []
    for tid, tl in L["tables"].items():
        fs = tl["fragments"]
        for a, b in zip(fs, fs[1:]):
            link_tot += 1
            ta, tb = match.get((tid, a["fragment_index"])), match.get((tid, b["fragment_index"]))
            ok = bool(ta and tb and (ta.get("continuation") or {}).get("continues_to") == tb["table_id"])
            rep = bool(tb and len(tb.get("repeated_header_rows") or []) == len(b.get("repeated_header_rows") or []) and ok)
            link_ok += ok
            rep_ok += rep
            link_rows.append({"table_id": tid, "from": a["fragment_index"], "to": b["fragment_index"], "linked": ok, "repeated_header_rows_match": rep,
                              "method": (ta.get("continuation") or {}).get("method") if ta else None})
    predicted = [t for t in tables if (t.get("continuation") or {}).get("continues_to")]
    linkage = {"recall": rate(link_ok, link_tot), "precision": rate(link_ok, len(predicted)), "repeated_header": rate(rep_ok, link_tot),
               "predicted_links": len(predicted), "false_links": len(predicted) - link_ok, "links": link_rows,
               "native_library_link_fields": "없음 — 연결은 공통 후처리 규칙(header_repeat_rule) 결과"}

    # 8. 블록 유형 (참고: 채점하지 않음)
    type_pairs = Counter()
    for o in occ_rows:
        if o["kind"] == "block":
            for t in o["ir_types"] or ["(미일치)"]:
                type_pairs[f"{tblocks[o['id']]['type']}→{t}"] += 1

    return {"doc_id": doc_id, "status": "MEASURED", "format": fmt, "parser": ir["parser"]["name"], "parser_version": ir["parser"]["version"],
            "text": text_metrics, "text_occurrences": occ_rows, "table_detection": detection, "table_fragments": frag_rows,
            "cells": cells, "values": values, "reading_order": order, "linkage": linkage,
            "block_type_pairs": dict(type_pairs), "ir_diagnostics": [f"{d['code']}: {d['message']}" for d in ir["diagnostics"]]}


def preflight_compatible(ir: dict | None, truth: dict, locs: dict) -> dict | None:
    """P-02 전용: results/E04_upstage_preflight의 정의를 그대로 따른 지표 (Upstage 예비 결과와 같은 기준으로 나란히 놓기 위함)."""
    if ir is None:
        return None
    cs = truth["content_sets"]["CS2"]
    L = locs["P-02"]
    tables = {t["table_id"]: t for t in cs["tables"]}
    blocks = [b for b in ir["blocks"]]
    out_blocks = []
    for b in cs["blocks"]:
        hits = [x for x in blocks if norm(x["text"]) == norm(b["text"])]
        ious = []
        for l in L["blocks"][b["block_id"]]:
            same = [x for x in hits if x["location"].get("page") == l["page"] and "bbox" in x["location"]]
            if same:
                ious.append(round(max(iou(x["location"]["bbox"], l["bbox"]) for x in same), 3))
        out_blocks.append({"block_id": b["block_id"], "found_occurrences": len(hits), "expected_occurrences": len(L["blocks"][b["block_id"]]),
                           "bbox_iou_per_occurrence": ious})
    captions = {t["table_id"]: any(norm(x["text"]) == norm(t["caption"]) for x in blocks) for t in cs["tables"]}
    g = grade(ir, {"doc_id": "P-02", "format": "pdf_text", "content_set": "CS2"}, truth, locs)
    # 값: 예비 분석은 필드별 (표 셀 원문 == raw)
    frags = [(tid, f) for tid, e in L["tables"].items() for f in e["fragments"]]
    match = {(r["table_id"], r["fragment_index"]): r["matched_ir_table"] for r in g["table_fragments"]}
    irt = {t["table_id"]: t for t in ir["tables"]}
    value_cells = {}
    for tid, f in frags:
        t = irt.get(match.get((tid, f["fragment_index"])))
        if not t:
            continue
        got = {(c["row"], c["col"]): c for c in t["cells"]}
        tc = {(c["row"], c["col"]) for c in tables[tid]["cells"]}
        for i, lr in enumerate(f["logical_rows"], start=1):
            for c in range(1, tables[tid]["n_cols"] + 1):
                if (lr, c) in tc and (i, c) in got:
                    value_cells.setdefault((tid, lr, c), norm(got[(i, c)]["text"]))
    kinds, ok = Counter(), Counter()
    for v in cs["extracted_values"]:
        s = v["source"]
        kinds[v["field"]] += 1
        ok[v["field"]] += value_cells.get((s["table_id"], s["row"], s["col"])) == v["raw"]
    codes = [(t["table_id"], c) for t in cs["tables"] for c in t["cells"] if c["col"] == 2 and not c["is_header"]]
    return {"definition": "scripts/e04_preflight_analyze.py와 같은 정의 (P-02, 텍스트 공백 정규화 후 완전 일치, 표 IoU ≥ 0.5 매칭)",
            "text_blocks": out_blocks, "table_captions_found": captions,
            "tables": [{k: r.get(k) for k in ("table_id", "fragment_index", "matched_ir_table", "ir_rows", "expected_rows", "ir_cols", "expected_cols", "table_bbox_iou")}
                       for r in g["table_fragments"]],
            "cells_all_fragments": g["cells"]["text"], "header_cells": g["cells"]["header_text"], "merged_cells_spans": g["cells"]["merge_spans"],
            "product_material_codes": rate(sum(value_cells.get((tid, c["row"], 2)) == c["text"] for tid, c in codes), len(codes)),
            "values_by_field": {k: rate(ok[k], kinds[k]) for k in sorted(kinds)},
            "multipage_link": g["linkage"]["links"]}
