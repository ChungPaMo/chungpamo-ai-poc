"""PDF 직접 파서 2종 → 공통 중간 JSON 0.2.

pypdf      : 페이지별 텍스트 추출만 (표 구조·좌표 API 없음). 줄 단위 블록, 위치는 page만.
pdfplumber : 선(lines) 기반 표 검출(find_tables) + 셀 bbox로 격자·병합 복원, 표 밖 텍스트 줄을 문단으로 묶음.
좌표는 pt, 좌상단 원점, bbox = [x0, top, x1, bottom].
"""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

from .doc_common import diag, finalize_order, link_fragments, new_ir

EDGE_TOL = 1.0          # 셀 경계 좌표를 같은 격자선으로 볼 허용 오차 (pt)
PARA_GAP_RATIO = 0.6    # 줄 간격이 줄 높이 × 이 값보다 작고 x0가 같으면 같은 문단


def parse_pdf_pypdf(path: Path, rel: str) -> dict:
    import pypdf

    ir = new_ir(path, rel, "pdf", {"name": "pypdf", "version": version("pypdf"), "options": {"extraction_mode": "plain"}})
    reader = pypdf.PdfReader(str(path))
    seq, n = [], 0
    for pi, page in enumerate(reader.pages, start=1):
        for li, line in enumerate(page.extract_text().splitlines()):
            if not line.strip():
                continue
            n += 1
            bid = f"b{n:04d}"
            ir["blocks"].append({"block_id": bid, "type": "paragraph", "order": None, "text": line,
                                 "location": {"format": "pdf", "page": pi, "line_index": li}, "level": None})
            seq.append(bid)
    finalize_order(ir, seq)
    total_chars = sum(len(b["text"].strip()) for b in ir["blocks"])
    ir["document"]["units_of_division"] = {"pages": len(reader.pages)}
    ir["document"]["is_scanned"] = {"value": total_chars == 0, "method": "pypdf 텍스트 추출 결과가 비었는지"}
    if total_chars == 0:
        diag(ir, "EXT-EMPTY", "텍스트 레이어 없음 또는 추출 실패", severity="error")
    diag(ir, "EXT-UNSUPPORTED", "pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴")
    diag(ir, "EXT-UNSUPPORTED", "pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만")
    diag(ir, "EXT-UNSUPPORTED", "문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)")
    ir["format_specific"].update({"location_index_base": {"page": 1, "line_index": 0}, "text_layer": total_chars > 0,
                                  "reading_order_basis": "pypdf 콘텐츠 스트림 순서"})
    return ir


def _cluster(values: list[float]) -> list[float]:
    out: list[float] = []
    for v in sorted(values):
        if not out or v - out[-1] > EDGE_TOL:
            out.append(v)
    return out


def _idx(edges: list[float], v: float) -> int:
    return min(range(len(edges)), key=lambda i: abs(edges[i] - v))


def _r(b) -> list[float]:
    return [round(float(x), 2) for x in b]


def parse_pdf_pdfplumber(path: Path, rel: str) -> dict:
    import pdfplumber

    opts = {"table_settings": "기본값 (vertical/horizontal_strategy=lines)", "x_tolerance": 3, "y_tolerance": 3,
            "paragraph_rule": f"같은 x0(±{EDGE_TOL}pt)이고 줄 간격 < 줄 높이×{PARA_GAP_RATIO}"}
    ir = new_ir(path, rel, "pdf", {"name": "pdfplumber", "version": version("pdfplumber"),
                                   "backend": {"pdfminer.six": version("pdfminer.six")}, "options": opts})
    seq: list[str] = []
    nb = nt = 0
    with pdfplumber.open(str(path)) as pdf:
        n_pages = len(pdf.pages)
        total_chars = 0
        for pi, page in enumerate(pdf.pages, start=1):
            total_chars += len(page.chars)
            items = []  # (top, x0, kind, payload)
            found = page.find_tables()
            for t in found:
                xs = _cluster([c[0] for c in t.cells] + [c[2] for c in t.cells])
                ys = _cluster([c[1] for c in t.cells] + [c[3] for c in t.cells])
                cells = []
                for cb in sorted(t.cells, key=lambda c: (round(c[1], 1), round(c[0], 1))):
                    r0, r1, c0, c1 = _idx(ys, cb[1]), _idx(ys, cb[3]), _idx(xs, cb[0]), _idx(xs, cb[2])
                    text = page.within_bbox(cb).extract_text() or ""
                    cells.append({"row": r0 + 1, "col": c0 + 1, "rowspan": max(1, r1 - r0), "colspan": max(1, c1 - c0), "text": text, "raw": text,
                                  "is_header": None, "location": {"format": "pdf", "page": pi, "bbox": _r(cb), "bbox_unit": "pt", "bbox_origin": "top-left"}})
                items.append((t.bbox[1], t.bbox[0], "table", {"bbox": t.bbox, "cells": cells, "n_rows": len(ys) - 1, "n_cols": len(xs) - 1}))
            inside = lambda ln: any(tb[0] - 1 <= (ln["x0"] + ln["x1"]) / 2 <= tb[2] + 1 and tb[1] - 1 <= (ln["top"] + ln["bottom"]) / 2 <= tb[3] + 1
                                    for tb in (t.bbox for t in found))
            lines = [ln for ln in page.extract_text_lines(x_tolerance=3, y_tolerance=3) if ln["text"].strip() and not inside(ln)]
            paras: list[list[dict]] = []
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
                    ir["tables"].append({"table_id": tid, "location": {"format": "pdf", "page": pi, "bbox": _r(p["bbox"]), "bbox_unit": "pt", "bbox_origin": "top-left"},
                                         "n_rows": p["n_rows"], "n_cols": p["n_cols"], "header_rows": None, "cells": p["cells"], "continuation": None,
                                         "caption_block_id": None, "detection": "inferred"})
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
    ir["format_specific"].update({
        "location_index_base": {"page": 1, "row": 1, "col": 1},
        "text_layer": total_chars > 0,
        "table_evidence": "그려진 선(lines)으로 셀 경계 추정 — 선 없는 표는 검출되지 않을 수 있음",
        "reading_order_basis": "페이지별 위→아래, 왼쪽→오른쪽 (요소 상단 좌표)",
        "continuation_links": {"count": links, "method": "header_repeat_rule (pdfplumber 자체 기능 아님)"},
    })
    return ir
