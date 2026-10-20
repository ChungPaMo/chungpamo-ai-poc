"""E03 외부 문서 독립 정답셋 v1 작성.

    .\\.venv\\Scripts\\python.exe scripts\\e03_build_external_truth.py

원천과 상태
- VERIFIED_OFFICIAL : 공식 주석(PubTables-1M) 또는 저장소가 명시한 사실(README 계약·테스트 기대값·본문 원문 source.md)
- PROVISIONAL       : 이 스크립트가 원본 XML을 직접 읽어 만든 값 (평가 대상 파서 미사용). 뷰어에서 사람이 확인하지 않았다
- NEEDS_MANUAL_REVIEW : 공식 값과 원본 대응이 어긋나 사람 검토가 필요한 값
- NOT_MEASURED      : 정답 원천 없음 (예: PDF 본문 읽기 순서, PPTX 논리 읽기 순서)
VERIFIED_MANUAL은 사람이 뷰어로 확인한 경우에만 쓰며, 이 버전에는 없다.

평가 대상 파서(python-docx·python-pptx·pypdf·pdfplumber)와 src/parsers를 import하지 않는다.
출력: data/canonical/external/e03_external_truth_v1.json (외부 문서 텍스트 포함 → Git 제외, D-025)
     results/E03_document_parsers/external_truth_v1/truth_manifest.json (텍스트 없는 공개용 요약·해시)
이미 있는 v1 정답은 덮어쓰지 않는다 (--force 없이는 중단).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "external_documents"
SRC = ROOT / "configs" / "e03_external_sources.json"
SPLITS = ROOT / "configs" / "e03_external_splits.json"
OUT = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"
PUB = ROOT / "results" / "E03_document_parsers" / "external_truth_v1"
VO, PV, NMR, NM = "VERIFIED_OFFICIAL", "PROVISIONAL", "NEEDS_MANUAL_REVIEW", "NOT_MEASURED"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
      "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
W, A, P, C, DG = ("{%s}" % NS[k] for k in ("w", "a", "p", "c", "dgm"))
RID = "{%s}id" % NS["r"]
SKIP_RUN_PARENTS = {W + "del", W + "moveFrom"}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def nows(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


# ======================= DOCX (원본 XML 직접 판독) =======================
# 텍스트 규칙 (변경 추적 '수락한 상태'): w:t, w:tab→\t, w:br·w:cr→\n. w:del·w:moveFrom 안 텍스트와 w:instrText(필드 코드)는 제외,
# w:ins·w:hyperlink·w:sdt·w:smartTag·w:fldSimple 안 텍스트는 포함. 각주·미주 참조 표식은 텍스트 없음.

def para_text(p) -> str:
    out = []
    for e in p.iter(W + "t", W + "tab", W + "br", W + "cr"):
        if any(a.tag in SKIP_RUN_PARENTS for a in e.iterancestors()):
            continue
        # 문단 안 중첩 문단(텍스트 상자 등)은 해당 문단에서 따로 센다
        if next((a for a in e.iterancestors(W + "p")), None) is not p:
            continue
        out.append(e.text or "" if e.tag == W + "t" else "\t" if e.tag == W + "tab" else "\n")
    return "".join(out)


def docx_table(tbl) -> dict:
    """앵커 셀 + span. 행은 w:tr(콘텐츠 컨트롤로 감싼 행 포함), w:gridBefore만큼 열을 건너뛴다."""
    rows = [tr for tr in tbl.iter(W + "tr") if next(tr.iterancestors(W + "tbl")) is tbl]
    grid = tbl.find(W + "tblGrid")
    cells, open_v = [], {}
    max_c = 0
    for r, tr in enumerate(rows, start=1):
        trpr = tr.find(W + "trPr")
        gb = trpr.find(W + "gridBefore") if trpr is not None else None
        c = 1 + (int(gb.get(W + "val")) if gb is not None else 0)
        tcs = [tc for tc in tr.iter(W + "tc") if next(tc.iterancestors(W + "tr")) is tr]
        for tc in tcs:
            pr = tc.find(W + "tcPr")
            span, vm = 1, None
            if pr is not None:
                gs = pr.find(W + "gridSpan")
                span = int(gs.get(W + "val")) if gs is not None else 1
                v = pr.find(W + "vMerge")
                vm = (v.get(W + "val") or "continue") if v is not None else None
            text = "\n".join(para_text(p) for p in tc.iter(W + "p") if next(p.iterancestors(W + "tc")) is tc)
            if vm == "continue" and c in open_v:
                open_v[c]["rowspan"] += 1
            else:
                cell = {"row": r, "col": c, "rowspan": 1, "colspan": span, "text": text}
                cells.append(cell)
                if vm == "restart":
                    open_v[c] = cell
                else:
                    open_v.pop(c, None)
            c += span
        max_c = max(max_c, c - 1)
    n_grid = len(grid.findall(W + "gridCol")) if grid is not None else 0
    anc = [a.tag.split("}")[1] for a in tbl.iterancestors()]
    return {"n_rows": len(rows), "n_cols": max(max_c, n_grid), "grid_cols_declared": n_grid, "cells": cells,
            "container": [t for t in reversed(anc) if t in ("body", "sdt", "tc", "customXml", "txbxContent")],
            "nested_tables": sum(1 for t in tbl.iter(W + "tbl") if t is not tbl)}


def docx_truth(z: zipfile.ZipFile) -> dict:
    doc = etree.fromstring(z.read("word/document.xml"))
    body = doc.find(W + "body")
    blocks, tables, order = [], [], []

    def walk(el):
        for ch in el:
            if ch.tag == W + "p":
                t = para_text(ch)
                if t.strip():
                    bid = f"p{len(blocks) + 1:03d}"
                    blocks.append({"block_id": bid, "part": "body", "text": t,
                                   "in_container": [a.tag.split("}")[1] for a in ch.iterancestors() if a.tag in (W + "sdt", W + "customXml")]})
                    order.append(bid)
            elif ch.tag == W + "tbl":
                tid = f"t{len(tables) + 1:02d}"
                tables.append({"table_id": tid, "doc_order": len(tables), **docx_table(ch)})
                order.append(tid)
            elif ch.tag in (W + "sdt", W + "sdtContent", W + "customXml", W + "smartTag"):
                walk(ch)
    walk(body)
    parts = {"header": [], "footer": []}
    for n in sorted(z.namelist()):
        m = re.match(r"word/(header|footer)\d*\.xml$", n)
        if m:
            root = etree.fromstring(z.read(n))
            parts[m.group(1)] += [{"part_file": n, "text": para_text(p)} for p in root.iter(W + "p") if para_text(p).strip()]
    notes = {}
    for part, tag in (("word/footnotes.xml", "footnote"), ("word/endnotes.xml", "endnote")):
        if part in z.namelist():
            root = etree.fromstring(z.read(part))
            notes[tag + "s"] = [{"id": n.get(W + "id"), "text": "\n".join(para_text(p) for p in n.iter(W + "p"))}
                                for n in root.findall(W + tag) if n.get(W + "type") not in ("separator", "continuationSeparator", "continuationNotice")]
        else:
            notes[tag + "s"] = []
    ins = ["".join(t.text or "" for t in e.iter(W + "t")) for e in body.iter(W + "ins")]
    dels = ["".join(t.text or "" for t in e.iter(W + "delText")) for e in body.iter(W + "del")]
    return {"blocks": blocks, "tables": tables, "body_order": order, "headers": parts["header"], "footers": parts["footer"], **notes,
            "tracked_changes": {"insertions": [t for t in ins if t.strip()], "deletions": [t for t in dels if t.strip()]},
            "comments": len(etree.fromstring(z.read("word/comments.xml")).findall(W + "comment")) if "word/comments.xml" in z.namelist() else 0}


# ======================= PPTX (원본 XML 직접 판독) =======================

def rels_of(z, part):
    rp = part.rsplit("/", 1)
    name = f"{rp[0]}/_rels/{rp[1]}.rels"
    if name not in z.namelist():
        return {}
    base = rp[0]
    out = {}
    for r in etree.fromstring(z.read(name)):
        t = r.get("Target")
        if r.get("TargetMode") == "External":
            continue
        parts = (base + "/" + t).split("/") if not t.startswith("/") else t.lstrip("/").split("/")
        stack = []
        for s in parts:
            if s == "..":
                stack.pop()
            elif s and s != ".":
                stack.append(s)
        out[r.get("Id")] = ("/".join(stack), r.get("Type").rsplit("/", 1)[-1])
    return out


def txbody_text(tx) -> str:
    paras = []
    for p in tx.findall(A + "p"):
        s = []
        for e in p:
            if e.tag in (A + "r", A + "fld"):
                s.append(e.findtext(A + "t") or "")
            elif e.tag == A + "br":
                s.append("\n")
        paras.append("".join(s))
    return "\n".join(paras)


def pptx_table(tbl) -> dict:
    cells = []
    trs = tbl.findall(A + "tr")
    for r, tr in enumerate(trs, start=1):
        for c, tc in enumerate(tr.findall(A + "tc"), start=1):
            if tc.get("hMerge") in ("1", "true") or tc.get("vMerge") in ("1", "true"):
                continue
            tx = tc.find(A + "txBody")
            cells.append({"row": r, "col": c, "rowspan": int(tc.get("rowSpan", "1")), "colspan": int(tc.get("gridSpan", "1")),
                          "text": txbody_text(tx) if tx is not None else ""})
    return {"n_rows": len(trs), "n_cols": len(tbl.find(A + "tblGrid")), "cells": cells}


def chart_texts(z, part) -> list[str]:
    root = etree.fromstring(z.read(part))
    out = []
    t = root.find(f".//{C}chart/{C}title")
    if t is not None:
        out.append("".join(x.text or "" for x in t.iter(A + "t")))
    for ser in root.iter(C + "ser"):
        out += [v.text for v in ser.findall(f"{C}tx//{C}v")]
        out += [v.text for v in ser.findall(f"{C}cat//{C}pt/{C}v")]
    for ax in list(root.iter(C + "catAx")) + list(root.iter(C + "valAx")):
        tt = ax.find(C + "title")
        if tt is not None:
            out.append("".join(x.text or "" for x in tt.iter(A + "t")))
    seen, uniq = set(), []
    for s in out:
        if s and s.strip() and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def smartart_nodes(z, part) -> list[str]:
    root = etree.fromstring(z.read(part))
    out = []
    for pt in root.iter(DG + "pt"):
        if pt.get("type", "node") not in ("node", "asst"):
            continue
        t = pt.find(DG + "t")
        if t is not None:
            s = txbody_text(t)
            if s.strip():
                out.append(s)
    return out


def pptx_truth(z: zipfile.ZipFile) -> dict:
    pres = etree.fromstring(z.read("ppt/presentation.xml"))
    prels = rels_of(z, "ppt/presentation.xml")
    slides = []
    for si, sid in enumerate(pres.find(P + "sldIdLst"), start=1):
        part = prels[sid.get(RID)][0]
        root = etree.fromstring(z.read(part))
        srels = rels_of(z, part)
        shapes, tables, charts, smart = [], [], [], []

        def walk(tree, path):
            for el in tree:
                tag = el.tag
                if tag not in (P + "sp", P + "grpSp", P + "graphicFrame", P + "cxnSp", P + "pic"):
                    continue
                nv = el.find("./*/" + P + "cNvPr")
                sid_, name = int(nv.get("id")), nv.get("name")
                npath = path + [name]
                if tag == P + "grpSp":
                    shapes.append({"shape_id": sid_, "name": name, "kind": "group", "nested_path": npath, "text": ""})
                    walk(el, npath)
                    continue
                kind, text = tag.split("}")[1], ""
                if tag in (P + "sp", P + "cxnSp"):
                    tx = el.find(P + "txBody")
                    text = txbody_text(tx) if tx is not None else ""
                elif tag == P + "graphicFrame":
                    gd = el.find(f"{A}graphic/{A}graphicData")
                    uri = gd.get("uri", "")
                    if uri.endswith("/table"):
                        kind = "table"
                        tables.append({"shape_id": sid_, "nested_path": npath, **pptx_table(gd.find(A + "tbl"))})
                    elif "chart" in uri:
                        kind = "chart"
                        cid = gd.find(C + "chart").get(RID)
                        charts.append({"shape_id": sid_, "texts": chart_texts(z, srels[cid][0])})
                    elif "diagram" in uri:
                        kind = "smartart"
                        dm = gd.find(DG + "relIds").get("{%s}dm" % NS["r"])
                        smart.append({"shape_id": sid_, "node_texts": smartart_nodes(z, srels[dm][0])})
                shapes.append({"shape_id": sid_, "name": name, "kind": kind, "nested_path": npath, "text": text})
        walk(root.find(f"{P}cSld/{P}spTree"), [])
        notes = ""
        nrel = [t for t, typ in srels.values() if typ == "notesSlide"]
        if nrel:
            nroot = etree.fromstring(z.read(nrel[0]))
            for sp in nroot.iter(P + "sp"):
                ph = sp.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                if ph is not None and ph.get("type") == "body":
                    notes = txbody_text(sp.find(P + "txBody"))
        slides.append({"slide_index": si, "shapes": shapes, "tables": tables, "charts": charts, "smartart": smart, "notes": notes})
    return {"slides": slides}


# ======================= PDF (PubTables-1M 공식 주석) =======================

def pdf_truth(pdf_path: Path, ann_path: Path) -> dict:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    tables = []
    for t in json.loads(ann_path.read_text(encoding="utf-8")):
        pg = pdf[t["pdf_page_index"]]
        W_, H_ = pg.get_size()
        tp = pg.get_textpage()
        cells, review = [], []
        for c in t["cells"]:
            rn, cn = sorted(c["row_nums"]), sorted(c["column_nums"])
            text = c.get("pdf_text_content") or ""
            x0, y0, x1, y1 = c["pdf_bbox"]
            got = tp.get_text_bounded(left=x0, bottom=H_ - y1, right=x1, top=H_ - y0)
            agree = nows(got) == nows(text) if nows(text) else None
            cell = {"row": rn[0] + 1, "col": cn[0] + 1, "rowspan": len(rn), "colspan": len(cn), "text": text,
                    "bbox": [round(v, 2) for v in c["pdf_bbox"]], "is_column_header": c["is_column_header"],
                    "is_projected_row_header": c["is_projected_row_header"], "status": VO}
            if agree is False:
                cell["status"] = NMR
                cell["review_note"] = "공식 주석 텍스트와 PDF 해당 영역 텍스트(PDFium)가 다름 — 주석은 유지, 사람 검토 대상"
                review.append([cell["row"], cell["col"]])
            cells.append(cell)
        tables.append({"table_id": t["structure_id"], "page": t["pdf_page_index"] + 1, "bbox": [round(v, 2) for v in t["pdf_table_bbox"]],
                       "n_rows": len(t["rows"]), "n_cols": len(t["columns"]), "cells": cells, "cells_needing_review": review,
                       "column_header_rows": sorted({i + 1 for i, r in enumerate(t["rows"]) if r.get("is_column_header")})})
    return {"pages": len(pdf), "tables": tables, "coordinate_system": {"unit": "pt", "origin": "top-left", "bbox": "[x0, top, x1, bottom]",
                                                                         "basis": "PubTables-1M pdf_bbox (셀 텍스트 대응 검사로 좌상단 원점 확인)"}}


# ======================= 공식 사실 덧씌우기 =======================

def official_node_texts(src_dir: Path) -> list[str]:
    """ts-pptx test/read/diagram.test.ts의 NODE_TEXT 배열 (data/raw/external_documents/truth_sources/, Git 제외)."""
    src = (src_dir / "ts-pptx_diagram.test.ts").read_text(encoding="utf-8")
    body = re.search(r"const NODE_TEXT = \[(.*?)\]", src, re.S).group(1)
    return re.findall(r"'((?:[^'\\]|\\.)*)'", body)


def official_merge_texts(src_dir: Path) -> tuple[str, str]:
    """ts-pptx test/read/table-merge-encoding.test.ts의 슬라이드 1 앵커·(3,1) 셀 기대값."""
    src = (src_dir / "ts-pptx_table-merge-encoding.test.ts").read_text(encoding="utf-8")
    anchor = re.search(r"assertEqual\(expected, '((?:[^'\\]|\\.)*)'", src).group(1).replace("\\n", "\n")
    t31 = re.search(r"cellAt\(table, 2, 0\)\.text, '([^']*)'", src).group(1)
    return anchor, t31


def official_smartart_prefixes(src_dir: Path) -> list[str]:
    """ts-pptx fixtures README의 smartart-families 노드 문자열 접두어 (예: `xxx-*` 형식 4개)."""
    readme = (src_dir / "ts-pptx_fixtures_README.md").read_text(encoding="utf-8")
    line = next(ln for ln in readme.splitlines() if "smartart-families.pptx` —" in ln or "greppable" in ln)
    block = readme[readme.index(line):readme.index(line) + 600]
    return [m + "-" for m in re.findall(r"`([a-z]+)-\*`", block)]


def official_overlay(doc_id: str, t: dict, src_dir: Path) -> tuple[list[dict], dict]:
    """저장소가 명시한 사실을 판정 가능한 단언으로 기록하고, XML 판독 결과와 일치하는지 표시. (단언 목록, 항목 상태)"""
    claims = []

    def claim(text, ok, source):
        claims.append({"claim": text, "source": source, "status": VO, "xml_reading_agrees": bool(ok)})
    if doc_id == "X-D01":
        tb = t["tables"]
        s = "docx-editor __fixtures__/README.md (kitchen-sink 계약)"
        claim("표 2개, 문서 순서", len(tb) == 2, s)
        claim("첫 표: 세로·가로 병합이 있는 격자", any(c["rowspan"] > 1 for c in tb[0]["cells"]) and any(c["colspan"] > 1 for c in tb[0]["cells"]), s)
        claim("둘째 표: w:tblGrid에 w:gridCol 없음", tb[1]["grid_cols_declared"] == 0, s)
        claim("머리말·꼬리말 부품 있음", bool(t["headers"]) and bool(t["footers"]), s)
        claim("각주·미주 부품 있음 (실제 각주·미주는 구분자뿐 — 0건)", t["footnotes"] == [] and t["endnotes"] == [], s + " + XML")
    elif doc_id == "X-D02":
        tb = t["tables"]
        s = "docx-editor __fixtures__/README.md (google-docs-export 계약)"
        claim("3열 표: 세로 병합 2개, gridSpan 1개", tb[0]["n_cols"] == 3 and sum(c["rowspan"] > 1 for c in tb[0]["cells"]) == 2 and sum(c["colspan"] > 1 for c in tb[0]["cells"]) == 1, s)
        claim("둘째 표 (vAlign 3종)", len(tb) == 2, s)
        claim("각주 2개", len(t["footnotes"]) == 2, s)
        claim("메모 1개", t["comments"] == 1, s)
        claim("단어 중간을 나누는 w:ins 1개", len(t["tracked_changes"]["insertions"]) == 1, s)
        md = (src_dir / "docx-editor_producers_source.md").read_text(encoding="utf-8")
        flat = nows(re.sub(r"[*_`#>\[\]()|\\-]", "", md))
        for b in t["blocks"]:
            b["text_status"] = VO if nows(re.sub(r"[*_`#>\[\]()|\\-]", "", b["text"])) in flat else PV
            b["text_source"] = "source.md (본문 원문)" if b["text_status"] == VO else "XML 판독"
    elif doc_id == "X-T01":
        s = "ts-pptx test/read/fixtures/README.md, test/read/diagram.test.ts"
        claim("슬라이드 11장", len(t["slides"]) == 11, s)
        node = official_node_texts(src_dir)   # 원문 문자열은 코드에 두지 않고 로컬(Git 제외) 공식 테스트 파일에서 읽는다 (D-025)
        sa = t["slides"][1]["smartart"]
        claim("슬라이드 2 SmartArt 노드 11개 (diagram.test.ts NODE_TEXT)", bool(sa) and [nows(x) for x in sa[0]["node_texts"]] == [nows(x) for x in node], s)
        if sa:
            sa[0]["node_texts_official"] = node
            sa[0]["status"] = VO
        claim("표·차트 그래픽 프레임 있음", any(s_["tables"] for s_ in t["slides"]) and any(s_["charts"] for s_ in t["slides"]), s)
    elif doc_id == "X-T02":
        s = "ts-pptx fixtures README + test/read/table-merge-encoding.test.ts"
        spec = [(3, 3, 2, 2), (4, 4, 3, 3), (3, 3, 2, 2), (3, 3, 1, 2), (3, 3, 2, 1)]   # 행, 열, 앵커 rowspan, colspan
        for i, (nr, nc, rs, cs) in enumerate(spec):
            tb = t["slides"][i]["tables"][0]
            a = next(c for c in tb["cells"] if (c["row"], c["col"]) == (1, 1))
            claim(f"슬라이드 {i + 1}: {nr}×{nc} 표, (1,1) 앵커 rowspan {rs} colspan {cs}", (tb["n_rows"], tb["n_cols"], a["rowspan"], a["colspan"]) == (nr, nc, rs, cs), s)
            tb["structure_status"] = VO
        tb0 = t["slides"][0]["tables"][0]
        cell = lambda r, c: next((x for x in tb0["cells"] if (x["row"], x["col"]) == (r, c)), None)
        anchor, t31 = official_merge_texts(src_dir)   # 기대값은 로컬(Git 제외) 공식 테스트 파일에서 읽는다 (D-025)
        claim(f"슬라이드 1 앵커 텍스트 '{anchor.replace(chr(10), chr(92) + 'n')}'", cell(1, 1) and cell(1, 1)["text"] == anchor, s)
        claim(f"슬라이드 1 (3,1) 텍스트 '{t31}'", cell(3, 1) and cell(3, 1)["text"] == t31, s)
        for rc in ((1, 1), (3, 1)):
            if cell(*rc):
                cell(*rc)["status"] = VO
    elif doc_id == "X-HO-T03":
        s = "ts-pptx fixtures README (smartart-families)"
        sa = [x for sl in t["slides"] for x in sl["smartart"]]
        claim("SmartArt 4개 (슬라이드당 1)", len(sa) == 4, s)
        prefixes = official_smartart_prefixes(src_dir)
        claim("노드 텍스트 접두어 " + "·".join(prefixes), all(any(n.startswith(p) for n in d["node_texts"]) for d, p in zip(sa, prefixes)), s)
    return claims, {}


ITEMS = ["body_text", "table_region", "row_col_structure", "cell_text", "cell_merge", "header_cells", "reading_order", "page_slide",
         "shape_hierarchy", "source_location", "footnotes", "tracked_changes", "smartart", "chart"]


def item_status(fmt: str, doc_id: str, claims: list[dict]) -> dict:
    """항목별 정답 상태 (공식 단언이 있어도 셀 단위까지 공식인 경우만 VERIFIED_OFFICIAL)."""
    if fmt == "pdf":
        s = {k: NM for k in ITEMS}
        s.update({k: VO for k in ("table_region", "row_col_structure", "cell_text", "cell_merge", "header_cells", "page_slide", "source_location")})
        s["cell_text"] = VO + " (일부 셀 NEEDS_MANUAL_REVIEW)"
        return s
    if fmt == "docx":
        s = {k: PV for k in ITEMS}
        s.update({"header_cells": NM, "page_slide": NM, "shape_hierarchy": NM, "smartart": NM, "chart": NM, "source_location": PV + " (본문 순번)"})
        if doc_id == "X-D02":
            s["body_text"] = "VERIFIED_OFFICIAL (source.md와 일치하는 문단) / PROVISIONAL (그 밖)"
        return s
    s = {k: PV for k in ITEMS}
    s.update({"reading_order": NM, "header_cells": NM, "footnotes": NM, "tracked_changes": NM, "page_slide": PV})
    if doc_id == "X-T02":
        s.update({"cell_merge": VO, "row_col_structure": VO, "cell_text": "VERIFIED_OFFICIAL (슬라이드 1의 2셀) / PROVISIONAL (그 밖)"})
    if doc_id == "X-T01":
        s.update({"smartart": VO, "page_slide": VO})
    return s


def main() -> int:
    verify = "--verify-against-frozen" in sys.argv   # 파일을 쓰지 않고, 고정된 v1과 내용(created 제외)이 같은지만 확인
    if OUT.exists() and "--force" not in sys.argv and not verify:
        raise SystemExit(f"{OUT.relative_to(ROOT)} 이미 있음 — 정답 v1은 덮어쓰지 않는다")
    sources = {s["id"]: s for s in json.loads(SRC.read_text(encoding="utf-8"))["sources"]}
    splits = json.loads(SPLITS.read_text(encoding="utf-8"))
    split_of = {i: k for k in ("blind8", "dev", "holdout") for i in splits[k]}
    docs = []
    for doc_id in splits["blind8"] + splits["dev"] + splits["holdout"]:
        s = sources[doc_id]
        p = RAW / s["format"] / s["file"]
        data = p.read_bytes()
        rec = {"doc_id": doc_id, "split": split_of[doc_id], "format": s["format"], "file": s["file"], "sha256": sha(data), "license": s["license"]}
        if s["format"] == "pdf":
            if not s.get("annotation"):
                rec.update({"truth": None, "items": {k: NM for k in ITEMS}, "note": "공식 주석 없음 — 정량 평가 제외"})
                docs.append(rec)
                continue
            rec["truth"] = pdf_truth(p, RAW / "pubtables1m" / "pdf_annotations_sample" / s["annotation"])
            rec["truth_source"] = "PubTables-1M PDF 주석 (CDLA-Permissive-2.0) — " + s["annotation"]
        else:
            with zipfile.ZipFile(p) as z:
                rec["truth"] = docx_truth(z) if s["format"] == "docx" else pptx_truth(z)
            rec["truth_source"] = "원본 XML 직접 판독 (lxml) + 저장소 공식 사실"
        rec["official_claims"], _ = official_overlay(doc_id, rec["truth"], RAW / "truth_sources")
        rec["items"] = item_status(s["format"], doc_id, rec["official_claims"])
        docs.append(rec)
    out = {"schema": "chungpamo.e03_external_truth", "version": "v1", "created": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "status_vocabulary": [VO, "VERIFIED_MANUAL", PV, NMR, NM], "manual_review_performed": False,
           "rules": {"docx_text": "수락한 변경 기준: w:ins 포함, w:del·필드 코드 제외, w:tab→\\t, w:br→\\n, 셀 텍스트 = 셀 안 문단을 \\n으로 연결",
                     "docx_order": "본문 직속 + 콘텐츠 컨트롤(w:sdt)·customXml 안의 문단·표를 문서 순서로. 빈 문단 제외. 표 안 문단은 셀에 속함",
                     "pptx_text": "슬라이드 sldIdLst 순서, 도형 트리 순서, 그룹 재귀. 문단 \\n 연결. 노트 = 본문 자리표시자 텍스트",
                     "pptx_table": "병합 덮인 셀(hMerge·vMerge)은 제외한 앵커 셀 + gridSpan·rowSpan",
                     "pdf": "PubTables row_nums·column_nums(0부터) → 1부터 행·열 + span, 텍스트 = pdf_text_content, bbox = pdf_bbox(pt, 좌상단 원점)"},
           "documents": docs}
    if verify:
        frozen = json.loads(OUT.read_text(encoding="utf-8"))
        same = {k: frozen.get(k) == out.get(k) for k in out if k != "created"}
        print(json.dumps({"same_as_frozen_except_created": all(same.values()), "fields": same}, ensure_ascii=False))
        return 0 if all(same.values()) else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    blob = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    OUT.write_bytes(blob)
    PUB.mkdir(parents=True, exist_ok=True)
    pub = {"truth_file": OUT.relative_to(ROOT).as_posix(), "truth_sha256": sha(blob), "created": out["created"], "manual_review_performed": False,
           "builder_sha256": sha((ROOT / "scripts" / "e03_build_external_truth.py").read_bytes()), "documents": [public_view(d) for d in docs]}
    (PUB / "truth_manifest.json").write_text(json.dumps(pub, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"truth_sha256": pub["truth_sha256"], "docs": len(docs),
                      "claims_disagree": [(d["doc_id"], c["claim"]) for d in docs for c in d.get("official_claims", []) if not c["xml_reading_agrees"]]},
                     ensure_ascii=False))
    return 0


def redact_claim(label: str) -> str:
    """공개용 단언 설명에서 정답 문자열(따옴표 안 값·접두어 목록)을 가린다."""
    label = re.sub(r"'[^']*'", "'(로컬 정답 참조)'", label)
    return re.sub(r"접두어 .*$", "접두어 (로컬 정답 참조)", label)


def public_view(d: dict) -> dict:
    """텍스트 없이 개수·상태만."""
    t = d.get("truth") or {}
    v = {"doc_id": d["doc_id"], "split": d["split"], "format": d["format"], "sha256": d["sha256"], "items": d["items"],
         "official_claims": [{**{k: c[k] for k in ("source", "status", "xml_reading_agrees")}, "claim": redact_claim(c["claim"])}
                             for c in d.get("official_claims", [])]}
    if d["format"] == "pdf" and t:
        v["counts"] = {"tables": len(t["tables"]), "cells": sum(len(x["cells"]) for x in t["tables"]),
                       "spanning_cells": sum(1 for x in t["tables"] for c in x["cells"] if c["rowspan"] > 1 or c["colspan"] > 1),
                       "cells_needing_review": sum(len(x["cells_needing_review"]) for x in t["tables"])}
    elif d["format"] == "docx":
        v["counts"] = {"body_blocks": len(t["blocks"]), "tables": len(t["tables"]), "cells": sum(len(x["cells"]) for x in t["tables"]),
                       "tables_in_containers": sum(1 for x in t["tables"] if "sdt" in x["container"]), "footnotes": len(t["footnotes"]),
                       "headers": len(t["headers"]), "footers": len(t["footers"]), "insertions": len(t["tracked_changes"]["insertions"]),
                       "deletions": len(t["tracked_changes"]["deletions"])}
    elif d["format"] == "pptx":
        sl = t["slides"]
        v["counts"] = {"slides": len(sl), "text_shapes": sum(1 for s in sl for x in s["shapes"] if x["text"].strip()),
                       "groups": sum(1 for s in sl for x in s["shapes"] if x["kind"] == "group"),
                       "max_nesting": max((len(x["nested_path"]) for s in sl for x in s["shapes"]), default=0),
                       "tables": sum(len(s["tables"]) for s in sl), "charts": sum(len(s["charts"]) for s in sl),
                       "smartart": sum(len(s["smartart"]) for s in sl), "notes": sum(1 for s in sl if s["notes"].strip())}
    return v


if __name__ == "__main__":
    sys.exit(main())
