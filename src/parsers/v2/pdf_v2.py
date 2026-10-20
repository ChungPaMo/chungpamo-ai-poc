"""PDF 직접 파서 v2 (pdfplumber) → 공통 중간 JSON 0.2.

v1 대비 변경 (외부 문서 Baseline에서 확인한 실패 유형, 규칙은 dev 묶음으로만 조정):
1. 선 기반 검출(find_tables) 결과 정리: 셀 텍스트를 '글자 중심점이 셀 안'인 글자로 읽고(v1은 글자 상자 완전 포함),
   텍스트 없는 행·열을 지우며(음영 띠 경계로 생긴 빈 행), 텍스트 셀 2개 미만·1행·1열 표는 버린다(그림·장식 선 오검출)
2. 세로선 없는 표: 길이가 비슷한 가로 괘선 묶음(위·중간·아래 괘선)으로 표 영역을 잡고,
   단어 정렬로 열(본문 행의 빈 x 구간), 줄로 행을 만든다. 여러 열에 걸친 구절은 colspan, 첫 내부 괘선 위 행은 머리 행,
   첫 열에만 텍스트가 있는 본문 행은 행 머리(행 전체 span)로 표시. 영역 바로 위 열 정렬된 줄은 머리 행으로 포함
3. 블록·읽기 순서·표 조각 연결은 v1과 같은 규칙
한계: 줄바꿈된 셀(한 셀이 두 줄)은 두 행으로 나뉜다. 괘선이 없는 표는 검출하지 않는다.
"""

from __future__ import annotations

from importlib.metadata import version

from ..doc_common import diag, finalize_order, link_fragments, new_ir
from ..doc_pdf import _cluster, _idx, _r
from . import IMPL_VERSION

EDGE_TOL = 1.0
PARA_GAP_RATIO = 0.6
RULE_MAX_THICK = 2.5     # 괘선으로 볼 최대 두께 (pt)
RULE_MIN_LEN = 60        # 표 괘선으로 볼 최소 길이 (pt)
RULE_JOIN_GAP = 3.0      # 같은 높이 조각 괘선 잇기 허용 간격
CHUNK_GAP = 4.5          # 한 줄 안에서 이보다 넓은 빈칸은 다른 칸
PROSE_WORDS, PROSE_MAX_GAP = 6, 4.0
WRAP_MERGE = True        # 본문에서 첫 열이 빈 줄은 앞 행에 합침


def _center_text(chars, bbox):
    from pdfplumber.utils import extract_text
    x0, y0, x1, y1 = bbox
    sel = [c for c in chars if x0 <= (c["x0"] + c["x1"]) / 2 <= x1 and y0 <= (c["top"] + c["bottom"]) / 2 <= y1]
    return extract_text(sel, x_tolerance=1.5, y_tolerance=3) if sel else ""


def _drop_empty(cells, n_rows, n_cols):
    """텍스트 없는 행·열 제거 후 다시 번호 매김 (span 셀은 남은 행·열 수로 줄임)."""
    def keep_axis(axis, n):
        keep = []
        for i in range(1, n + 1):
            on = [c for c in cells if c[axis] <= i < c[axis] + c["rowspan" if axis == "row" else "colspan"]]
            if any(c["text"].strip() for c in on):
                keep.append(i)
        return keep
    kr, kc = keep_axis("row", n_rows), keep_axis("col", n_cols)
    rmap, cmap = {r: i + 1 for i, r in enumerate(kr)}, {c: i + 1 for i, c in enumerate(kc)}
    out = []
    for c in cells:
        rows = [r for r in range(c["row"], c["row"] + c["rowspan"]) if r in rmap]
        cols = [k for k in range(c["col"], c["col"] + c["colspan"]) if k in cmap]
        if not rows or not cols:
            continue
        out.append({**c, "row": rmap[rows[0]], "col": cmap[cols[0]], "rowspan": len(rows), "colspan": len(cols)})
    return out, len(kr), len(kc)


def _rule_segments(page):
    segs = [(ln["x0"], ln["x1"], ln["top"]) for ln in page.lines if abs(ln["top"] - ln["bottom"]) <= RULE_MAX_THICK]
    segs += [(r["x0"], r["x1"], (r["top"] + r["bottom"]) / 2) for r in page.rects if r["height"] <= RULE_MAX_THICK]
    return segs


def _rules(page):
    segs = _rule_segments(page)
    segs.sort(key=lambda s: (round(s[2]), s[0]))
    merged = []
    for x0, x1, y in segs:
        last = merged[-1] if merged else None
        if last and abs(last[2] - y) <= 1.0 and x0 <= last[1] + RULE_JOIN_GAP:
            merged[-1] = (last[0], max(last[1], x1), last[2])
        else:
            merged.append((x0, x1, y))
    return sorted((r for r in merged if r[1] - r[0] >= RULE_MIN_LEN), key=lambda r: r[2])


def _piece(ws):
    return {"x0": min(w["x0"] for w in ws), "x1": max(w["x1"] for w in ws), "top": min(w["top"] for w in ws),
            "bottom": max(w["bottom"] for w in ws), "text": " ".join(w["text"] for w in ws), "words": ws}


def _text_lines(words):
    """세로로 충분히 겹치는 단어를 한 줄로 (아래·위 첨자가 별도 줄로 갈라지지 않게)."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines:
            ln = lines[-1]
            h = min(w["bottom"] - w["top"], ln["base_h"])
            if min(w["bottom"], ln["bottom"]) - max(w["top"], ln["top"]) >= 0.4 * h:
                ln["words"].append(w)
                ln["bottom"] = max(ln["bottom"], w["bottom"])
                ln["top"] = min(ln["top"], w["top"])
                continue
        lines.append({"top": w["top"], "bottom": w["bottom"], "base_h": w["bottom"] - w["top"], "words": [w]})
    for ln in lines:
        ln["words"].sort(key=lambda w: w["x0"])
        ln["x0"], ln["x1"] = ln["words"][0]["x0"], max(w["x1"] for w in ln["words"])
        chunks = []
        for w in ln["words"]:
            if chunks and w["x0"] - chunks[-1]["x1"] <= CHUNK_GAP:
                chunks[-1]["words"].append(w)
                chunks[-1]["x1"] = max(chunks[-1]["x1"], w["x1"])
            else:
                chunks.append({"x0": w["x0"], "x1": w["x1"], "words": [w]})
        for c in chunks:
            c.update(_piece(c["words"]))
        ln["chunks"] = chunks
        gaps = [b["x0"] - a["x1"] for a, b in zip(ln["words"], ln["words"][1:])]
        ln["prose"] = len(ln["words"]) >= PROSE_WORDS and (max(gaps) if gaps else 0) <= PROSE_MAX_GAP
    return lines


def _overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def _lines_in(words, x0, x1):
    """영역 가로 범위 안 단어만으로 줄을 만든다 (2단 조판에서 옆 단 텍스트가 같은 줄로 섞이지 않게)."""
    return _text_lines([w for w in words if w["x0"] >= x0 - 2 and w["x1"] <= x1 + 2])


def _rule_regions(page, words, taken):
    rules = _rules(page)
    groups = []
    for r in rules:
        g = groups[-1] if groups else None
        if g:
            gx0, gx1 = min(x[0] for x in g), max(x[1] for x in g)
            ov = _overlap(gx0, gx1, r[0], r[1]) / max(1.0, max(gx1 - gx0, r[1] - r[0]))   # 긴 쪽 기준: 짧은 각주 구분선·머리 밑줄은 다른 묶음
            between = [ln for ln in _lines_in(words, min(gx0, r[0]), max(gx1, r[1])) if g[-1][2] < (ln["top"] + ln["bottom"]) / 2 < r[2]]
            prose = sum(ln["prose"] for ln in between)
            if ov >= 0.6 and prose < 2 and r[2] - g[-1][2] > 1.0:
                g.append(r)
                continue
            if ov >= 0.6 and r[2] - g[-1][2] <= 1.0:
                continue
        groups.append([r])
    regions = []
    for g in groups:
        if len(g) < 2:
            continue
        x0, x1, top, bottom = min(r[0] for r in g), max(r[1] for r in g), g[0][2], g[-1][2]
        if any(_overlap(x0, x1, t[0], t[2]) > 0 and _overlap(top, bottom, t[1], t[3]) > 0.5 * (bottom - top) for t in taken):
            continue
        lines = _lines_in(words, x0, x1)
        inside = [ln for ln in lines if top < (ln["top"] + ln["bottom"]) / 2 < bottom]
        if len(inside) < 2 or not any(len(ln["chunks"]) >= 2 for ln in inside):
            continue
        # 영역 위 머리 줄: 바로 위(4pt 이내)이거나 사이에 부분 괘선(그룹 머리 밑줄)만 있는 열 정렬 줄, 최대 3줄
        segs = [s for s in _rule_segments(page) if x0 - 2 <= s[0] and s[1] <= x1 + 2 and s[1] - s[0] < 0.9 * (x1 - x0)]
        above, cur = [], top
        for ln in sorted((ln for ln in lines if ln["bottom"] <= top + 0.5 and _overlap(ln["x0"], ln["x1"], x0, x1) > 0), key=lambda l: -l["bottom"]):
            underlined = any(ln["bottom"] - 1 <= s[2] <= cur + 1 and _overlap(s[0], s[1], ln["x0"], ln["x1"]) > 0 for s in segs)
            near = 0 <= cur - ln["bottom"] <= 6.0 or (0 <= cur - ln["bottom"] <= 12.0 and underlined)
            if near and (len(ln["chunks"]) >= 2 or underlined) and not ln["prose"] and len(above) < 3:
                above.append(ln)
                cur = ln["top"]
            else:
                break
        internal = [r[2] for r in g[1:-1]]
        header_y = top if above else (internal[0] if internal else None)
        # 머리 영역의 부분 괘선(그룹 머리 아래 밑줄): 같은 높이 조각을 잇기 전 원래 조각 단위로 둔다
        hdr_top = above[-1]["top"] if above else top
        partial = [s for s in segs if header_y is not None and hdr_top - 1 <= s[2] < header_y - 0.5]
        regions.append({"x0": x0, "x1": x1, "lines": list(reversed(above)) + inside, "header_y": header_y, "rules": [r[2] for r in g],
                        "partial_rules": partial})
    return regions


def _region_table(reg):
    lines = reg["lines"]
    hy = reg["header_y"]
    body = [ln for ln in lines if hy is None or (ln["top"] + ln["bottom"]) / 2 > hy]
    first_x = min(c["x0"] for ln in lines for c in ln["chunks"])
    cover = []
    for ln in body:
        if len(ln["chunks"]) == 1 and abs(ln["chunks"][0]["x0"] - first_x) < 3 and len(body) > 2:
            continue   # 행 머리 후보 줄은 열 경계 계산에서 뺀다
        cover += [(c["x0"], c["x1"]) for c in ln["chunks"]]
    if not cover:
        return None
    cover.sort()
    bounds, cur_end = [], cover[0][1]
    for a, b in cover[1:]:
        if a > cur_end + 2.0:
            bounds.append((cur_end + a) / 2)
        cur_end = max(cur_end, b)
    cols = [reg["x0"]] + bounds + [reg["x1"]]
    n_cols = len(cols) - 1
    if n_cols < 2:
        return None
    col_of = lambda x: max(0, min(n_cols - 1, next((i for i in range(n_cols) if x < cols[i + 1]), n_cols - 1)))
    centers = [(cols[i] + cols[i + 1]) / 2 for i in range(n_cols)]

    def pieces(ln, is_hdr):
        """줄을 칸 조각으로: 열 경계가 단어 사이 빈칸에 있으면 그 자리에서 나눈다. (c0, c1, piece)"""
        out = []
        for ch in ln["chunks"]:
            if is_hdr and any(-1 <= s[2] - ch["bottom"] <= 6 and _overlap(s[0], s[1], ch["x0"], ch["x1"]) > 0 for s in reg.get("partial_rules", [])):
                out.append(_piece(ch["words"]))   # 밑줄 있는 그룹 머리 글자는 열 경계에서 나누지 않는다
                continue
            cur = [ch["words"][0]]
            for a, b in zip(ch["words"], ch["words"][1:]):
                if any(a["x1"] < cb < b["x0"] for cb in bounds):
                    out.append(_piece(cur))
                    cur = []
                cur.append(b)
            out.append(_piece(cur))
        res = [[col_of(p["x0"]), col_of(p["x1"] - 0.5), p] for p in out]
        if is_hdr:   # 머리 글자 아래 부분 괘선: 괘선 아래 열을 그 위 머리 글자 중 가장 가까운 것에 배정
            for s in reg.get("partial_rules", []):
                above = [x for x in res if -1 <= s[2] - x[2]["bottom"] <= 6 and _overlap(s[0], s[1], x[2]["x0"], x[2]["x1"]) > 0]
                if not above:
                    continue
                for ci, cx in enumerate(centers):
                    if s[0] - 1 <= cx <= s[1] + 1:
                        best = min(above, key=lambda x: abs((x[2]["x0"] + x[2]["x1"]) / 2 - cx))
                        best[0], best[1] = min(best[0], ci), max(best[1], ci)
        return res

    # 논리 행: 본문에서 첫 열이 빈 줄은 앞 행의 줄바꿈 / 머리에서 앞 행의 단일 열 텍스트 칸 아래에만 있는 줄은 머리 줄바꿈
    rows = []
    for ln in lines:
        hdr = hy is not None and (ln["top"] + ln["bottom"]) / 2 < hy
        ps = pieces(ln, hdr)
        if rows and rows[-1]["hdr"] == hdr:
            prev = rows[-1]
            if WRAP_MERGE and not hdr and ps[0][0] != 0:
                prev["lines"].append(ln)
                prev["pieces"] += ps
                continue
            if hdr:
                single = {p[0] for p in prev["pieces"] if p[0] == p[1] and p[2]["text"].strip()}
                spanned = {c for p in prev["pieces"] if p[1] > p[0] for c in range(p[0], p[1] + 1)}
                if all(p[0] == p[1] and p[0] in single and p[0] not in spanned for p in ps):
                    prev["lines"].append(ln)
                    prev["pieces"] += ps
                    continue
        rows.append({"hdr": hdr, "lines": [ln], "pieces": ps})
    # 열 내용 범위 (셀 bbox용): 단일 열 조각의 x 범위 합집합
    col_ext = {}
    for rw in rows:
        for c0, c1, p in rw["pieces"]:
            if c0 == c1:
                e = col_ext.get(c0)
                col_ext[c0] = (min(e[0], p["x0"]), max(e[1], p["x1"])) if e else (p["x0"], p["x1"])
    cells = []
    for r, rw in enumerate(rows, start=1):
        is_hdr = rw["hdr"]
        ytop, ybot = rw["lines"][0]["top"], rw["lines"][-1]["bottom"]
        row_cells = {}
        for c0, c1, p in rw["pieces"]:
            hit = next((k for k, v in row_cells.items() if not (c1 < k or c0 > k + v["colspan"] - 1)), None)
            if hit is not None:
                v = row_cells.pop(hit)
                lo, hi = min(hit, c0), max(hit + v["colspan"] - 1, c1)
                row_cells[lo] = {"text": v["text"] + " " + p["text"], "colspan": hi - lo + 1}
            else:
                row_cells[c0] = {"text": p["text"], "colspan": c1 - c0 + 1}
        if not is_hdr and len(row_cells) == 1 and 0 in row_cells and len(rows) > 2 and n_cols > 1:
            row_cells[0]["colspan"] = n_cols
            row_cells[0]["projected_row_header"] = True
        occupied = set()
        for c0, v in row_cells.items():
            occupied |= set(range(c0, c0 + v["colspan"]))
        for c in range(n_cols):
            if c not in occupied:
                row_cells[c] = {"text": "", "colspan": 1}
        for c0, v in sorted(row_cells.items()):
            if any(c0 > k and c0 < k + w["colspan"] for k, w in row_cells.items()):
                continue
            c_last = c0 + v["colspan"] - 1
            x0 = col_ext.get(c0, (cols[c0], cols[c0 + 1]))[0]
            x1 = col_ext.get(c_last, (cols[c_last], cols[c_last + 1]))[1]
            cells.append({"row": r, "col": c0 + 1, "rowspan": 1, "colspan": v["colspan"], "text": v["text"], "raw": v["text"], "is_header": is_hdr,
                          "is_projected_row_header": bool(v.get("projected_row_header")), "bbox": [x0, ytop, x1, ybot]})
    top, bottom = lines[0]["top"], lines[-1]["bottom"]
    return {"bbox": [reg["x0"], top, reg["x1"], bottom], "cells": cells, "n_rows": len(rows), "n_cols": n_cols,
            "header_rows": sum(1 for rw in rows if rw["hdr"]) or None}


def parse_pdf_pdfplumber_v2(path, rel: str) -> dict:
    import pdfplumber

    opts = {"lines_tables": "find_tables 기본값 + 빈 행·열 제거 + 글자 중심점 셀 배정 + 빈 표 제외",
            "rule_tables": {"rule_max_thick": RULE_MAX_THICK, "rule_min_len": RULE_MIN_LEN, "chunk_gap": CHUNK_GAP},
            "paragraph_rule": f"같은 x0(±{EDGE_TOL}pt)이고 줄 간격 < 줄 높이×{PARA_GAP_RATIO}"}
    ir = new_ir(path, rel, "pdf", {"name": "pdfplumber", "version": version("pdfplumber"), "impl_version": IMPL_VERSION,
                                   "backend": {"pdfminer.six": version("pdfminer.six")}, "options": opts})
    seq, nb, nt = [], 0, 0
    stats = {"lines_tables_kept": 0, "lines_tables_dropped": 0, "rule_tables": 0}
    with pdfplumber.open(str(path)) as pdf:
        n_pages, total_chars = len(pdf.pages), 0
        for pi, page in enumerate(pdf.pages, start=1):
            chars = page.chars
            total_chars += len(chars)
            items, taken = [], []
            for t in page.find_tables():
                xs = _cluster([c[0] for c in t.cells] + [c[2] for c in t.cells])
                ys = _cluster([c[1] for c in t.cells] + [c[3] for c in t.cells])
                cells = []
                for cb in t.cells:
                    r0, r1, c0, c1 = _idx(ys, cb[1]), _idx(ys, cb[3]), _idx(xs, cb[0]), _idx(xs, cb[2])
                    text = _center_text(chars, cb)
                    cells.append({"row": r0 + 1, "col": c0 + 1, "rowspan": max(1, r1 - r0), "colspan": max(1, c1 - c0), "text": text, "raw": text,
                                  "is_header": None, "bbox": list(cb)})
                cells, n_rows, n_cols = _drop_empty(cells, len(ys) - 1, len(xs) - 1)
                if n_rows < 2 or n_cols < 2 or sum(1 for c in cells if c["text"].strip()) < 2:
                    stats["lines_tables_dropped"] += 1
                    continue
                stats["lines_tables_kept"] += 1
                taken.append(t.bbox)
                items.append((t.bbox[1], t.bbox[0], "table", {"bbox": t.bbox, "cells": cells, "n_rows": n_rows, "n_cols": n_cols, "detection": "lines", "header_rows": None}))
            words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
            for reg in _rule_regions(page, words, taken):
                tb = _region_table(reg)
                if tb is None:
                    continue
                stats["rule_tables"] += 1
                taken.append(tb["bbox"])
                items.append((tb["bbox"][1], tb["bbox"][0], "table", {**tb, "detection": "rules_text"}))
            inside = lambda ln: any(tb[0] - 1 <= (ln["x0"] + ln["x1"]) / 2 <= tb[2] + 1 and tb[1] - 1 <= (ln["top"] + ln["bottom"]) / 2 <= tb[3] + 1 for tb in taken)
            lines = [ln for ln in page.extract_text_lines(x_tolerance=3, y_tolerance=3) if ln["text"].strip() and not inside(ln)]
            paras = []
            for ln in sorted(lines, key=lambda l: (l["top"], l["x0"])):
                prev = paras[-1][-1] if paras else None
                h = ln["bottom"] - ln["top"]
                if prev and abs(prev["x0"] - ln["x0"]) <= EDGE_TOL and 0 <= ln["top"] - prev["bottom"] < h * PARA_GAP_RATIO:
                    paras[-1].append(ln)
                else:
                    paras.append([ln])
            for para in paras:
                bbox = [min(l["x0"] for l in para), min(l["top"] for l in para), max(l["x1"] for l in para), max(l["bottom"] for l in para)]
                items.append((bbox[1], bbox[0], "block", {"text": " ".join(l["text"].strip() for l in para), "bbox": bbox, "lines": len(para)}))
            for _, _, kind, p in sorted(items, key=lambda i: (round(i[0], 1), i[1])):
                if kind == "table":
                    nt += 1
                    tid = f"t{nt:03d}"
                    cells = [{"row": c["row"], "col": c["col"], "rowspan": c["rowspan"], "colspan": c["colspan"], "text": c["text"], "raw": c["raw"],
                              "is_header": c.get("is_header"), **({"is_projected_row_header": True} if c.get("is_projected_row_header") else {}),
                              "location": {"format": "pdf", "page": pi, "bbox": _r(c["bbox"]), "bbox_unit": "pt", "bbox_origin": "top-left"}} for c in p["cells"]]
                    ir["tables"].append({"table_id": tid, "location": {"format": "pdf", "page": pi, "bbox": _r(p["bbox"]), "bbox_unit": "pt", "bbox_origin": "top-left"},
                                         "n_rows": p["n_rows"], "n_cols": p["n_cols"], "header_rows": p.get("header_rows"), "cells": cells,
                                         "continuation": None, "caption_block_id": None, "detection": "inferred",
                                         "format_specific": {"detector": p["detection"]}})
                    seq.append(tid)
                else:
                    nb += 1
                    bid = f"b{nb:04d}"
                    ir["blocks"].append({"block_id": bid, "type": "paragraph", "order": None, "text": p["text"],
                                         "location": {"format": "pdf", "page": pi, "bbox": _r(p["bbox"]), "bbox_unit": "pt", "bbox_origin": "top-left", "lines": p["lines"]},
                                         "level": None})
                    seq.append(bid)
    finalize_order(ir, seq)
    links = link_fragments(ir, "page")
    ir["document"]["units_of_division"] = {"pages": n_pages}
    ir["document"]["is_scanned"] = {"value": total_chars == 0, "method": "pdfplumber 페이지 문자 객체 수"}
    if total_chars == 0:
        diag(ir, "EXT-EMPTY", "텍스트 레이어 없음", severity="error")
    diag(ir, "EXT-UNSUPPORTED", "블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph")
    diag(ir, "EXT-UNSUPPORTED", "괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔")
    ir["format_specific"].update({"location_index_base": {"page": 1, "row": 1, "col": 1}, "text_layer": total_chars > 0,
                                  "table_detectors": stats, "reading_order_basis": "페이지별 위→아래, 왼쪽→오른쪽",
                                  "continuation_links": {"count": links, "method": "header_repeat_rule (pdfplumber 자체 기능 아님)"}})
    return ir
