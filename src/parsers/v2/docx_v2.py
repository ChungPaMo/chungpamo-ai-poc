"""DOCX 직접 파서 v2 (python-docx + 부족한 부분은 패키지 XML 직접 읽기) → 공통 중간 JSON 0.2.

v1 대비 변경 (외부 문서 Baseline에서 확인한 실패 유형):
1. 문단 스타일이 없는 문서(기본 스타일 미정의)에서 중단하지 않음
2. 콘텐츠 컨트롤(w:sdt)·customXml 안의 문단·표도 문서 순서대로 읽음 (location.container_path)
3. 문단 텍스트 = 변경 추적 '수락한 상태': w:ins 안 텍스트 포함, w:del·w:moveFrom 제외 (python-docx Paragraph.text는 w:ins를 읽지 않음)
4. 각주·미주 부품을 읽어 part=footnotes/endnotes 블록으로 출력 (python-docx에 API 없음)
5. 표 행이 콘텐츠 컨트롤로 감싸진 경우(CT_SdtRow)와 w:gridBefore 처리
"""

from __future__ import annotations

from importlib.metadata import version

import docx
from docx.oxml.ns import qn
from lxml import etree

from ..doc_common import diag, finalize_order, new_ir
from . import IMPL_VERSION

W_P, W_TBL, W_TR, W_TC = qn("w:p"), qn("w:tbl"), qn("w:tr"), qn("w:tc")
CONTAINERS = {qn("w:sdt"): "sdt", qn("w:sdtContent"): None, qn("w:customXml"): "customXml", qn("w:smartTag"): "smartTag"}
SKIP = {qn("w:del"), qn("w:moveFrom")}
TEXT_TAGS = {qn("w:t"): None, qn("w:tab"): "\t", qn("w:br"): "\n", qn("w:cr"): "\n"}
LOC_BASE = {"body_index": 0, "table_index": 0, "section_index": 0, "paragraph_index": 0, "row": 1, "col": 1}


def accepted_text(p) -> str:
    """문단 직속 텍스트 (중첩 문단 제외), 변경 추적 수락 상태."""
    out = []
    for e in p.iter(*TEXT_TAGS):
        anc = list(e.iterancestors())
        if any(a.tag in SKIP for a in anc):
            continue
        if next((a for a in anc if a.tag == W_P), None) is not p:
            continue
        out.append((e.text or "") if e.tag == qn("w:t") else TEXT_TAGS[e.tag])
    return "".join(out)


def style_info(p, styles) -> tuple[str, int | None, str | None]:
    ps = p.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    sid = ps.get(qn("w:val")) if ps is not None else None
    name = styles.get(sid, sid) if sid else None
    s = (name or "").lower()
    if s == "title":
        return "heading", 0, name
    if s.startswith("heading"):
        digits = "".join(ch for ch in s if ch.isdigit())
        return "heading", int(digits) if digits else None, name
    if s == "caption":
        return "caption", None, name
    if s.startswith("list") or p.find(f"{qn('w:pPr')}/{qn('w:numPr')}") is not None:
        return "list_item", None, name
    return "paragraph", None, name


def table_rows(tbl):
    for ch in tbl:
        if ch.tag == W_TR:
            yield ch
        elif ch.tag in CONTAINERS:
            yield from table_rows(ch)


def row_cells(tr):
    for ch in tr:
        if ch.tag == W_TC:
            yield ch
        elif ch.tag in CONTAINERS:
            yield from row_cells(ch)


def build_table(tbl, loc_base: dict) -> tuple[list[dict], int, int, list[int], int]:
    cells, open_v, header_rows, n_cols, nested = [], {}, [], 0, 0
    rows = list(table_rows(tbl))
    for r, tr in enumerate(rows, start=1):
        trpr = tr.find(qn("w:trPr"))
        if trpr is not None and trpr.find(qn("w:tblHeader")) is not None:
            header_rows.append(r)
        gb = trpr.find(qn("w:gridBefore")) if trpr is not None else None
        c = 1 + (int(gb.get(qn("w:val"))) if gb is not None else 0)
        for tc in row_cells(tr):
            pr = tc.find(qn("w:tcPr"))
            span, vm = 1, None
            if pr is not None:
                gs = pr.find(qn("w:gridSpan"))
                span = int(gs.get(qn("w:val"))) if gs is not None else 1
                v = pr.find(qn("w:vMerge"))
                vm = (v.get(qn("w:val")) or "continue") if v is not None else None
            nested += len(tc.findall(f".//{W_TBL}"))
            if vm == "continue" and c in open_v:
                open_v[c]["rowspan"] += 1
            else:
                paras = [p for p in tc.iter(W_P) if next(p.iterancestors(W_TC)) is tc]
                text = "\n".join(accepted_text(p) for p in paras)
                cell = {"row": r, "col": c, "rowspan": 1, "colspan": span, "text": text, "raw": text, "is_header": r in header_rows,
                        "location": {**loc_base, "row": r, "col": c}}
                cells.append(cell)
                if vm == "restart":
                    open_v[c] = cell
                else:
                    open_v.pop(c, None)
            c += span
        n_cols = max(n_cols, c - 1)
    grid = tbl.find(qn("w:tblGrid"))
    n_cols = max(n_cols, len(grid.findall(qn("w:gridCol"))) if grid is not None else 0)
    return cells, len(rows), n_cols, header_rows, nested


def parse_docx_v2(path, rel: str) -> dict:
    ir = new_ir(path, rel, "docx", {"name": "python-docx", "version": version("python-docx"), "impl_version": IMPL_VERSION, "options": {}})
    d = docx.Document(str(path))
    styles = {}
    try:
        styles = {s.style_id: s.name for s in d.styles}
    except Exception:  # 스타일 부품 이상 — 스타일 없이 진행
        diag(ir, "EXT-UNSUPPORTED", "스타일 부품을 읽지 못함 — 블록 유형은 paragraph로 둠")
    seq, counters = [], {"b": 0, "t": 0}

    def add_block(text, btype, level, loc, style):
        counters["b"] += 1
        bid = f"b{counters['b']:04d}"
        ir["blocks"].append({"block_id": bid, "type": btype, "order": None, "text": text, "location": loc, "level": level, "style": {"name": style}})
        return bid

    footers, page_field = [], []
    for si, sec in enumerate(d.sections):
        for part, hf in (("header", sec.header), ("footer", sec.footer)):
            if hf.is_linked_to_previous and si > 0:
                continue
            if "PAGE" in hf._element.xml:
                page_field.append({"part": part, "section_index": si})
            for pi, p in enumerate(hf._element.findall(W_P)):
                t = accepted_text(p)
                if t.strip():
                    loc = {"format": "docx", "part": part, "section_index": si, "paragraph_index": pi}
                    if part == "header":
                        seq.append(add_block(t, "header", None, loc, style_info(p, styles)[2]))
                    else:
                        footers.append((t, loc, style_info(p, styles)[2]))

    def walk(el, body_index, container):
        for ch in el:
            bi = body_index if body_index is not None else None
            if ch.tag == W_P:
                t = accepted_text(ch)
                if t.strip():
                    btype, level, sname = style_info(ch, styles)
                    loc = {"format": "docx", "part": "body", "body_index": bi, **({"container_path": container} if container else {})}
                    seq.append(add_block(t, btype, level, loc, sname))
            elif ch.tag == W_TBL:
                ti = counters["t"]
                counters["t"] += 1
                tid = f"t{ti + 1:03d}"
                loc = {"format": "docx", "part": "body", "body_index": bi, "table_index": ti, **({"container_path": container} if container else {})}
                cells, n_rows, n_cols, header_rows, nested = build_table(ch, loc)
                if nested:
                    diag(ir, "EXT-UNSUPPORTED", f"표 안의 중첩 표 {nested}개는 펼치지 않음 (셀 텍스트에 포함되지 않음)", location=loc)
                ir["tables"].append({"table_id": tid, "location": loc, "n_rows": n_rows, "n_cols": n_cols, "header_rows": len(header_rows) or None,
                                     "cells": cells, "continuation": None, "caption_block_id": None, "detection": "native"})
                seq.append(tid)
            elif ch.tag in CONTAINERS:
                name = CONTAINERS[ch.tag]
                walk(ch, bi, container + [name] if name else container)

    body = d.element.body
    for i, ch in enumerate(c for c in body if c.tag != qn("w:sectPr")):
        walk([ch], i, [])
    for t, loc, style in footers:
        seq.append(add_block(t, "footer", None, loc, style))
    # 각주·미주 (python-docx API 없음 → 관계로 부품을 찾아 XML 직접 읽기)
    notes_found = []
    for rel_obj in d.part.rels.values():
        kind = str(rel_obj.reltype).rsplit("/", 1)[-1]
        if kind in ("footnotes", "endnotes") and not rel_obj.is_external:
            root = etree.fromstring(rel_obj.target_part.blob)
            tag = qn("w:footnote" if kind == "footnotes" else "w:endnote")
            for n in root.findall(tag):
                if n.get(qn("w:type")) in ("separator", "continuationSeparator", "continuationNotice"):
                    continue
                t = "\n".join(accepted_text(p) for p in n.iter(W_P))
                if t.strip():
                    seq.append(add_block(t, "footnote", None, {"format": "docx", "part": kind, "note_id": n.get(qn("w:id"))}, None))
                    notes_found.append(kind)
    finalize_order(ir, seq)
    ir["document"]["units_of_division"] = {"sections": len(d.sections)}
    ir["format_specific"].update({
        "location_index_base": LOC_BASE, "page_number_fields": page_field,
        "notes_read": {k: notes_found.count(k) for k in ("footnotes", "endnotes")},
        "text_rule": "변경 추적 수락 상태 (w:ins 포함, w:del 제외)",
        "pages": "DOCX에는 쪽 나눔 결과가 저장되지 않음 — page 위치 미제공",
        "reading_order_basis": "머리말 → 본문(컨테이너 안 포함, 문서 순서) → 꼬리말 → 각주·미주",
    })
    return ir
