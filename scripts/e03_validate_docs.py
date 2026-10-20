"""E03 문서 샘플 독립 검증 — 저장된 파일을 다시 읽어 정답 명세(v1)·위치 메타데이터(v1)와 대조.

    .\\.venv\\Scripts\\python.exe scripts\\e03_validate_docs.py [--root DIR]

e03_generate_docs.py를 import하지 않는다. 생성기 내부 객체를 받지 않고 파일만 읽는다.
- DOCX·PPTX: zip + lxml로 OOXML 원문을 직접 파싱(병합·도형 ID·그룹·노트), 열림 확인은 python-docx·python-pptx
- PDF: 외부 PDF 파서 없이 자체 최소 디코더(ToUnicode CMap)로 텍스트 레이어·좌표를 확인한다.
  이것은 'PDF 내부 구조 확인'이며 PDF 파서의 추출 정확도가 아니다 (E03 파서 비교 단계에서 측정).
상태: PASS / FAIL / NOT_MEASURED / NEEDS_MANUAL_REVIEW. 분모가 0이면 NOT_MEASURED.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
TRUTH_SHA256 = "982af3be7af0b4f512851a3a2cba2d68578b8e046540d94f0efe1170b0cf554a"
AUTHOR = "chungpamo-poc (synthetic sample generator)"
IOU_TABLE = 0.5
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
ITEMS = ["1_package_format", "2_not_corrupted", "3_text_blocks", "4_text_order", "5_table_count", "6_cell_count",
         "7_merged_cells", "8_numbers_units_dates", "9_canonical_refs", "10_source_location", "11_multi_page_slide",
         "12_header_footer_notes", "13_visual_layout", "14_metadata_privacy"]


def item(status: str, detail=None, num=None, den=None) -> dict:
    if den == 0 and status == "PASS":
        status = "NOT_MEASURED"
    return {"status": status, "numerator": num, "denominator": den, "detail": detail}


def ratio_item(num: int, den: int, detail=None) -> dict:
    if den == 0:
        return item("NOT_MEASURED", detail or "분모 0", num, den)
    return item("PASS" if num == den else "FAIL", detail, num, den)


def iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


class Ctx:
    def __init__(self, root: Path) -> None:
        self.root = root
        tp = root / "data" / "canonical" / "e03_document_truth_v1.json"
        if hashlib.sha256(tp.read_bytes()).hexdigest() != TRUTH_SHA256:
            raise SystemExit("정답 명세 해시 불일치 → 검증 중단")
        self.truth = json.loads(tp.read_text(encoding="utf-8"))
        self.locs = json.loads((root / "data" / "canonical" / "e03_document_locations_v1.json").read_text(encoding="utf-8"))
        self.gt = json.loads((ROOT / "data" / "canonical" / "ground_truth_v2.json").read_text(encoding="utf-8"))
        self.by_uid = {r["record_uid"]: r for rows in self.gt["entities"].values() for r in rows}


def canonical_check(ctx: Ctx, cs: dict, table_ids: list[str], cell_text) -> dict:
    """문서에서 읽은 셀 문자열이 canonical 값과 같은 의미인지 (구현: 문서 문자열을 직접 해석)."""
    ok = tot = 0
    bad = []
    unit = {u["unit_code"]: u for u in ctx.gt["entities"]["Unit"]}
    mat = {m["material_id"]: m for m in ctx.gt["entities"]["Material"]}
    for v in cs["extracted_values"]:
        tid = v["source"]["table_id"]
        if tid not in table_ids:
            continue
        txt = cell_text(tid, v["source"]["row"], v["source"]["col"])
        tot += 1
        ref = v["canonical_ref"]
        if txt is None:
            bad.append((tid, v["source"], "셀 없음"))
            continue
        token = txt.split(" ")[0].replace(",", "")
        try:
            if "expected_path" in ref:
                node = ctx.gt
                for k in ref["expected_path"].split("."):
                    node = node[k]
                good = Decimal(token) == Decimal(node)
            elif v.get("derived_rule"):
                inv = ctx.by_uid[ref["record_uid"]]
                m = mat[inv["item_id"]]
                want = Decimal(inv["on_hand_qty"]) * Decimal(unit[inv["unit"]]["to_base_factor"]) / Decimal(unit[m["base_unit"]]["to_base_factor"]) * Decimal(m["unit_cost"])
                good = Decimal(token) == want
            else:
                rec = ctx.by_uid[ref["record_uid"]]
                want = rec[ref["field"]]
                try:
                    good = Decimal(token) == Decimal(str(want))
                except InvalidOperation:
                    good = token == str(want)
        except (InvalidOperation, KeyError) as e:
            good = False
            bad.append((tid, v["source"], f"{type(e).__name__}"))
        ok += good
        if not good and len(bad) < 10:
            bad.append((tid, v["source"], txt))
    return ratio_item(ok, tot, bad[:10] or None)


# ===========================================================================
# DOCX
# ===========================================================================
def docx_text(p) -> str:
    return "".join(t.text or "" for t in p.iter(f"{W}t"))


def docx_table_grid(tbl) -> list[dict]:
    anchors = {}
    out = []
    for r, tr in enumerate(tbl.findall(f"{W}tr"), start=1):
        col = 1
        for tc in tr.findall(f"{W}tc"):
            pr = tc.find(f"{W}tcPr")
            span = 1
            vm = None
            if pr is not None:
                gs = pr.find(f"{W}gridSpan")
                if gs is not None:
                    span = int(gs.get(f"{W}val"))
                v = pr.find(f"{W}vMerge")
                if v is not None:
                    vm = v.get(f"{W}val", "continue")
            text = "\n".join(docx_text(p) for p in tc.findall(f"{W}p"))
            if vm == "continue":
                a = anchors.get(col)
                if a is not None:
                    a["rowspan"] += 1
            else:
                cell = {"row": r, "col": col, "rowspan": 1, "colspan": span, "text": text}
                out.append(cell)
                if vm == "restart":
                    anchors[col] = cell
                else:
                    anchors.pop(col, None)
            col += span
    return out


def validate_docx(ctx: Ctx, spec: dict, loc: dict) -> dict:
    path = ctx.root / spec["file"]
    cs = ctx.truth["content_sets"][spec["content_set"]]
    res = {}
    try:
        z = zipfile.ZipFile(path)
        names = set(z.namelist())
        need = {"[Content_Types].xml", "word/document.xml", "docProps/core.xml", "_rels/.rels"}
        res["1_package_format"] = item("PASS" if need <= names and z.testzip() is None else "FAIL", sorted(need - names) or None)
    except zipfile.BadZipFile as e:
        return {k: item("FAIL", f"zip 아님: {e}") for k in ITEMS}
    try:
        import docx
        docx.Document(str(path))
        xmls = {n: etree.fromstring(z.read(n)) for n in names if n.endswith(".xml") or n.endswith(".rels")}
        res["2_not_corrupted"] = item("PASS", f"python-docx 열림, XML {len(xmls)}개 파싱")
    except Exception as e:  # noqa: BLE001
        res["2_not_corrupted"] = item("FAIL", f"{type(e).__name__}: {e}")
        return {**{k: item("FAIL", "열기 실패") for k in ITEMS}, **res}
    body = xmls["word/document.xml"].find(f"{W}body")
    elems = [el for el in body if el.tag in (f"{W}p", f"{W}tbl")]
    blocks = {b["block_id"]: b for b in cs["blocks"]}
    tables = {t["table_id"]: t for t in cs["tables"]}
    order = spec["layout"]["body_order"]
    # 3·10 블록
    found = loc_ok = loc_tot = 0
    hdr_ftr = {}
    for part in ("header", "footer"):
        for n in sorted(x for x in names if re.match(rf"word/{part}\d+\.xml", x)):
            hdr_ftr.setdefault(part, []).extend(docx_text(p) for p in xmls[n].iter(f"{W}p"))
    rendered = [b for b in blocks if b in loc["blocks"]]
    for bid in rendered:
        for l in loc["blocks"][bid]:
            loc_tot += 1
            if l["part"] == "body":
                el = elems[l["body_index"]] if l["body_index"] < len(elems) else None
                ok = el is not None and el.tag == f"{W}p" and docx_text(el) == blocks[bid]["text"]
            else:
                ok = blocks[bid]["text"] in hdr_ftr.get(l["part"], [])
            loc_ok += ok
        body_texts = [docx_text(e) for e in elems if e.tag == f"{W}p"] + sum(hdr_ftr.values(), [])
        found += blocks[bid]["text"] in body_texts
    res["3_text_blocks"] = ratio_item(found, len(rendered), {"rendered": rendered, "not_rendered": sorted(set(blocks) - set(rendered))})
    # 4 순서: body_order 요소의 실제 본문 위치가 증가하는가
    pos = []
    for oid in order:
        if oid in blocks:
            l = next(x for x in loc["blocks"][oid] if x["part"] == "body")
            pos.append(l["body_index"])
        else:
            pos.append(loc["tables"][oid]["fragments"][0]["body_index"])
    actual_ok = all(elems[i].tag == (f"{W}tbl" if oid in tables else f"{W}p") for oid, i in zip(order, pos))
    res["4_text_order"] = item("PASS" if pos == sorted(pos) and actual_ok else "FAIL", {"body_index_sequence": pos})
    # 5~8 표
    tbls = [e for e in elems if e.tag == f"{W}tbl"]
    table_ids = [o for o in order if o in tables]
    res["5_table_count"] = item("PASS" if len(tbls) == len(table_ids) else "FAIL", f"문서 {len(tbls)} / 명세 {len(table_ids)}", len(tbls), len(table_ids))
    cell_ok = cell_tot = merge_ok = merge_tot = 0
    grids = {}
    for tid in table_ids:
        f = loc["tables"][tid]["fragments"][0]
        el = elems[f["body_index"]]
        g = docx_table_grid(el) if el.tag == f"{W}tbl" else []
        grids[tid] = {(c["row"], c["col"]): c for c in g}
        for c in tables[tid]["cells"]:
            cell_tot += 1
            d = grids[tid].get((c["row"], c["col"]))
            cell_ok += d is not None and d["text"] == c["text"]
            if c["rowspan"] > 1 or c["colspan"] > 1:
                merge_tot += 1
                merge_ok += d is not None and (d["rowspan"], d["colspan"]) == (c["rowspan"], c["colspan"])
        extra = len(g) - len(tables[tid]["cells"])
        if extra:
            cell_tot += abs(extra)
    res["6_cell_count"] = ratio_item(cell_ok, cell_tot, "셀 위치·텍스트 일치 (문서 앵커 수 차이는 분모에 더함)")
    res["7_merged_cells"] = ratio_item(merge_ok, merge_tot)
    val_ok = val_tot = 0
    for v in cs["extracted_values"]:
        tid = v["source"]["table_id"]
        if tid in grids:
            val_tot += 1
            d = grids[tid].get((v["source"]["row"], v["source"]["col"]))
            val_ok += d is not None and d["text"] == v["raw"]
    res["8_numbers_units_dates"] = ratio_item(val_ok, val_tot)
    res["9_canonical_refs"] = canonical_check(ctx, cs, table_ids, lambda t, r, c: (grids[t].get((r, c)) or {}).get("text"))
    tloc_ok = sum(1 for tid in table_ids if elems[loc["tables"][tid]["fragments"][0]["body_index"]].tag == f"{W}tbl")
    res["10_source_location"] = ratio_item(loc_ok + tloc_ok, loc_tot + len(table_ids),
                                           "생성 기록 위치(part·body_index)의 실제 요소 내용 일치. 파서 추출 위치 정확도는 미측정")
    res["11_multi_page_slide"] = item("NOT_MEASURED", "DOCX 페이지 나눔은 뷰어 레이아웃에 따름 (자동 검증 불가)")
    page_field = any(e.get(f"{W}instr", "").strip() == "PAGE" for n in names if n.startswith("word/footer") for e in xmls[n].iter(f"{W}fldSimple"))
    hf_expect = [b for b in rendered if any(l["part"] in ("header", "footer") for l in loc["blocks"][b])]
    hf_ok = sum(1 for b in hf_expect if blocks[b]["text"] in sum(hdr_ftr.values(), []))
    res["12_header_footer_notes"] = item("PASS" if hf_ok == len(hf_expect) and page_field else "FAIL",
                                         {"header_footer_blocks": hf_expect, "page_field": page_field}, hf_ok + page_field, len(hf_expect) + 1)
    res["13_visual_layout"] = item("NEEDS_MANUAL_REVIEW", "Word 등 뷰어로 레이아웃 미검수 (OOXML 구조 유효성과 별개)")
    res["14_metadata_privacy"] = ooxml_metadata(z, xmls)
    return res


def ooxml_metadata(z, xmls) -> dict:
    core = xmls.get("docProps/core.xml")
    ns = {"dc": "http://purl.org/dc/elements/1.1/", "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"}
    creator = core.findtext("dc:creator", namespaces=ns) if core is not None else None
    last = core.findtext("cp:lastModifiedBy", namespaces=ns) if core is not None else None
    app = xmls.get("docProps/app.xml")
    company = None
    if app is not None:
        for e in app.iter():
            if e.tag.endswith("}Company"):
                company = e.text
    external = [n for n, x in xmls.items() if n.endswith(".rels") for r in x if r.get("TargetMode") == "External"]
    ok = creator == AUTHOR and last == AUTHOR and not company and not external
    return item("PASS" if ok else "FAIL", {"creator": creator, "lastModifiedBy": last, "company": company, "external_rels": external})


# ===========================================================================
# PPTX
# ===========================================================================
def validate_pptx(ctx: Ctx, spec: dict, loc: dict) -> dict:
    path = ctx.root / spec["file"]
    cs = ctx.truth["content_sets"][spec["content_set"]]
    res = {}
    try:
        z = zipfile.ZipFile(path)
        names = set(z.namelist())
        need = {"[Content_Types].xml", "ppt/presentation.xml", "docProps/core.xml"}
        res["1_package_format"] = item("PASS" if need <= names and z.testzip() is None else "FAIL", sorted(need - names) or None)
    except zipfile.BadZipFile as e:
        return {k: item("FAIL", f"zip 아님: {e}") for k in ITEMS}
    try:
        from pptx import Presentation
        prs = Presentation(str(path))
        xmls = {n: etree.fromstring(z.read(n)) for n in names if n.endswith(".xml") or n.endswith(".rels")}
        res["2_not_corrupted"] = item("PASS", f"python-pptx 열림, XML {len(xmls)}개 파싱")
    except Exception as e:  # noqa: BLE001
        return {**{k: item("FAIL", "열기 실패") for k in ITEMS}, "2_not_corrupted": item("FAIL", f"{type(e).__name__}: {e}")}
    blocks = {b["block_id"]: b for b in cs["blocks"]}
    tables = {t["table_id"]: t for t in cs["tables"]}

    def walk(shapes, path_):
        for s in shapes:
            p = path_ + [s.name]
            yield s, p
            if s.shape_type is not None and s.shape_type == 6:  # GROUP
                yield from walk(s.shapes, p)

    slides = list(prs.slides)
    by_slide = {i + 1: list(walk(sl.shapes, [])) for i, sl in enumerate(slides)}
    notes = {i + 1: (sl.notes_slide.notes_text_frame.text if sl.has_notes_slide else None) for i, sl in enumerate(slides)}
    # 3·10 블록
    found = loc_ok = loc_tot = 0
    rendered = [b for b in blocks if b in loc["blocks"]]
    for bid in rendered:
        hit = False
        for l in loc["blocks"][bid]:
            loc_tot += 1
            if l["part"] == "notes":
                ok = notes.get(l["slide_index"]) == blocks[bid]["text"]
            else:
                cand = [(s, p) for s, p in by_slide.get(l["slide_index"], []) if s.shape_id == l["shape_id"]]
                ok = bool(cand) and cand[0][0].has_text_frame and cand[0][0].text_frame.text == blocks[bid]["text"] \
                    and cand[0][1] == l["nested_path"] and cand[0][0].name == l["shape_name"]
            loc_ok += ok
            hit = hit or ok
        found += hit
    res["3_text_blocks"] = ratio_item(found, len(rendered), {"rendered": rendered, "not_rendered": sorted(set(blocks) - set(rendered))})
    # 4 순서: 슬라이드 번호 → 같은 슬라이드 안 도형 순서(z-order)
    seq = []
    for bid in rendered:
        for l in loc["blocks"][bid]:
            if l["part"] == "slide":
                idx = next(i for i, (s, p) in enumerate(by_slide[l["slide_index"]]) if s.shape_id == l["shape_id"])
                seq.append((l["slide_index"], idx, bid))
    for tid, e in loc["tables"].items():
        for f in e["fragments"]:
            idx = next((i for i, (s, p) in enumerate(by_slide[f["slide_index"]]) if s.shape_id == f["shape_id"]), -1)
            seq.append((f["slide_index"], idx, f"{tid}#{f['fragment_index']}"))
    # 4 순서: ① 모든 요소가 파일에서 발견됨 ② 명세 layout의 '슬라이드 번호: …' 항목에 적힌 ID는 그 슬라이드에 있음
    #   ③ 같은 슬라이드 안에서는 명세 항목에 적힌 순서대로 도형이 쌓여 있음 (z-order)
    plan_slide = {}
    plan_rank = {}
    for entry in spec["layout"]["slides"]:
        head, _, body_ = entry.partition(":")
        if not head.strip().isdigit():
            continue
        for k, oid in enumerate(re.findall(r"CS\d-[bT]\d+", body_)):
            plan_slide.setdefault(oid, set()).add(int(head))
            plan_rank[(int(head), oid)] = k
    problems = [x for x in seq if x[1] < 0]
    for s_, idx, oid in seq:
        base = oid.split("#")[0]
        if base in plan_slide and s_ not in plan_slide[base]:
            problems.append((s_, idx, oid, "명세 슬라이드와 다름"))
    for s_ in {x[0] for x in seq}:
        ranked = [(idx, plan_rank[(s_, oid.split("#")[0])]) for x_s, idx, oid in seq if x_s == s_ and (s_, oid.split("#")[0]) in plan_rank]
        if [r for _, r in sorted(ranked)] != sorted(r for _, r in ranked):
            problems.append((s_, "z-order가 명세 순서와 다름"))
    res["4_text_order"] = item("PASS" if not problems else "FAIL",
                               {"(slide, shape_order, id)": sorted(seq), "ids_checked_against_plan": sorted(plan_slide), "problems": problems})
    # 5~8 표
    frag_total = sum(len(e["fragments"]) for e in loc["tables"].values())
    graphic_tables = [(i, s) for i, lst in by_slide.items() for s, p in lst if getattr(s, "has_table", False) and s.has_table]
    res["5_table_count"] = item("PASS" if len(graphic_tables) == frag_total else "FAIL", f"표 도형 {len(graphic_tables)} / 조각 {frag_total}",
                                len(graphic_tables), frag_total)
    cell_ok = cell_tot = merge_ok = merge_tot = 0
    logical = {}
    for tid, e in loc["tables"].items():
        t = tables[tid]
        truth_cells = {(c["row"], c["col"]): c for c in t["cells"]}
        for f in e["fragments"]:
            shp = next((s for s, p in by_slide[f["slide_index"]] if s.shape_id == f["shape_id"]), None)
            if shp is None or not shp.has_table:
                cell_tot += sum(1 for c in t["cells"] if c["row"] in f["logical_rows"])
                continue
            tbl = shp.table
            for ri, lr in enumerate(f["logical_rows"]):
                for ci in range(t["n_cols"]):
                    cell = tbl.cell(ri, ci)
                    if cell.is_spanned:
                        continue
                    tc = truth_cells.get((lr, ci + 1))
                    cell_tot += 1
                    if tc is None:
                        continue
                    cell_ok += cell.text == tc["text"]
                    logical.setdefault(tid, {}).setdefault((lr, ci + 1), cell.text)
                    if tc["rowspan"] > 1 or tc["colspan"] > 1:
                        merge_tot += 1
                        merge_ok += cell.is_merge_origin and (cell.span_height, cell.span_width) == (tc["rowspan"], tc["colspan"])
    res["6_cell_count"] = ratio_item(cell_ok, cell_tot, "조각별 셀 텍스트 일치 (반복 헤더 포함)")
    res["7_merged_cells"] = ratio_item(merge_ok, merge_tot)
    val_ok = val_tot = 0
    for v in cs["extracted_values"]:
        tid = v["source"]["table_id"]
        if tid in loc["tables"]:
            val_tot += 1
            val_ok += logical.get(tid, {}).get((v["source"]["row"], v["source"]["col"])) == v["raw"]
    res["8_numbers_units_dates"] = ratio_item(val_ok, val_tot)
    res["9_canonical_refs"] = canonical_check(ctx, cs, list(loc["tables"]), lambda t, r, c: logical.get(t, {}).get((r, c)))
    tloc = sum(1 for e in loc["tables"].values() for f in e["fragments"]
               if any(s.shape_id == f["shape_id"] and s.name == f["shape_name"] for s, p in by_slide[f["slide_index"]]))
    res["10_source_location"] = ratio_item(loc_ok + tloc, loc_tot + frag_total, "슬라이드 번호·도형 ID·이름·중첩 경로 일치. 파서 추출 위치 정확도는 미측정")
    rep_ok = rep_tot = 0
    for tid, e in loc["tables"].items():
        if len(e["fragments"]) > 1:
            for f in e["fragments"][1:]:
                rep_tot += 1
                rep_ok += f["repeated_header_rows"] == list(range(1, tables[tid]["header_rows"] + 1))
    slides_ok = len(slides) == loc["slides"]
    res["11_multi_page_slide"] = item("PASS" if slides_ok and rep_ok == rep_tot else "FAIL",
                                      {"slides": len(slides), "expected": loc["slides"], "repeated_header_fragments": f"{rep_ok}/{rep_tot}"})
    grp_detail = []
    grp_ok = True
    for g in loc.get("groups", []):
        gs = next((s for s, p in by_slide[g["slide_index"]] if s.shape_id == g["group_shape_id"]), None)
        kids = [(k.shape_id, k.name) for k in gs.shapes] if gs is not None and gs.shape_type == 6 else []
        grp_ok &= kids == [(c["shape_id"], c["name"]) for c in g["children"]]
        grp_detail.append({"group": g["group_name"], "children": kids})
    note_blocks = [b for b in rendered if any(l["part"] == "notes" for l in loc["blocks"][b])]
    notes_ok = all(any(notes.get(l["slide_index"]) == blocks[b]["text"] for l in loc["blocks"][b]) for b in note_blocks)
    if note_blocks or loc.get("groups"):
        res["12_header_footer_notes"] = item("PASS" if notes_ok and grp_ok else "FAIL",
                                             {"notes_blocks": note_blocks, "groups": grp_detail})
    else:
        res["12_header_footer_notes"] = item("NOT_MEASURED", "이 문서에는 노트·그룹 도형이 없음 (명세 layout)")
    res["13_visual_layout"] = item("NEEDS_MANUAL_REVIEW", "슬라이드 밖으로 벗어남·텍스트 겹침 등 시각 레이아웃 미검수")
    res["14_metadata_privacy"] = ooxml_metadata(z, xmls)
    return res


# ===========================================================================
# PDF (자체 최소 디코더)
# ===========================================================================
class MiniPdf:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.objs = {int(n): body for n, body in re.findall(rb"(\d+) 0 obj\s*(.*?)endobj", data, re.S)}

    def stream(self, n: int) -> bytes:
        o = self.objs[n]
        d = o.split(b"stream", 1)[1].lstrip(b"\r\n").rsplit(b"endstream", 1)[0].strip()
        if b"/ASCII85Decode" in o:
            d = base64.a85decode(d[:-2] if d.endswith(b"~>") else d)
        if b"/FlateDecode" in o:
            import zlib
            d = zlib.decompress(d)
        return d

    @staticmethod
    def ref(o: bytes, key: bytes) -> int | None:
        m = re.search(rb"/" + key + rb"\s+(\d+) 0 R", o)
        return int(m.group(1)) if m else None

    def pages(self) -> list[int]:
        return [n for n, o in sorted(self.objs.items()) if re.search(rb"/Type\s*/Page(?![s\w])", o)]

    def fonts(self, page_obj: bytes) -> dict:
        res = re.search(rb"/Font\s+(\d+) 0 R", page_obj)
        fdict = self.objs[int(res.group(1))] if res else b""
        out = {}
        for name, n in re.findall(rb"/([\w+]+)\s+(\d+) 0 R", fdict):
            fo = self.objs[int(n)]
            cmap = {}
            tu = self.ref(fo, b"ToUnicode")
            if tu:
                for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", self.stream(tu).split(b"beginbfchar", 1)[-1]):
                    cmap[int(a, 16)] = chr(int(b, 16))
            first = re.search(rb"/FirstChar\s+(\d+)", fo)
            widths = re.search(rb"/Widths\s*\[(.*?)\]", fo, re.S)
            fd = self.ref(fo, b"FontDescriptor")
            asc = desc = None
            if fd:
                a = re.search(rb"/Ascent\s+([-\d.]+)", self.objs[fd])
                d = re.search(rb"/Descent\s+([-\d.]+)", self.objs[fd])
                asc, desc = (float(a.group(1)) if a else None), (float(d.group(1)) if d else None)
            out[name.decode()] = {"cmap": cmap, "to_unicode": bool(tu), "first": int(first.group(1)) if first else 0,
                                  "widths": [float(x) for x in widths.group(1).split()] if widths else [],
                                  "ascent": asc or 750.0, "descent": desc or -250.0, "subtype": re.search(rb"/Subtype\s*/(\w+)", fo).group(1).decode()}
        return out


def pdf_literal(s: bytes, i: int) -> tuple[bytes, int]:
    out, depth = bytearray(), 1
    i += 1
    while i < len(s):
        ch = s[i]
        if ch == 0x5C:  # backslash
            nxt = s[i + 1]
            if 0x30 <= nxt <= 0x37:
                j = i + 1
                oct_ = b""
                while j < len(s) and len(oct_) < 3 and 0x30 <= s[j] <= 0x37:
                    oct_ += bytes([s[j]])
                    j += 1
                out.append(int(oct_, 8))
                i = j
                continue
            out.append({ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}.get(nxt, nxt))
            i += 2
            continue
        if ch == 0x28:
            depth += 1
        elif ch == 0x29:
            depth -= 1
            if depth == 0:
                return bytes(out), i + 1
        out.append(ch)
        i += 1
    return bytes(out), i


def pdf_runs(pdf: MiniPdf, page_n: int, page_h: float) -> list[dict]:
    po = pdf.objs[page_n]
    fonts = pdf.fonts(po)
    content = pdf.stream(pdf.ref(po, b"Contents"))
    runs, operands = [], []
    font, size, tm = None, 0.0, (0.0, 0.0)
    i = 0
    tok = re.compile(rb"\s*(\(|[-+]?\d*\.?\d+|/[\w+]+|[A-Za-z*']+|\[|\]|<<|>>|<[0-9A-Fa-f]*>)")
    rects = []
    while i < len(content):
        m = tok.match(content, i)
        if not m:
            i += 1
            continue
        t = m.group(1)
        if t == b"(":
            lit, i = pdf_literal(content, m.start(1))
            operands.append(lit)
            continue
        i = m.end()
        if re.fullmatch(rb"[-+]?\d*\.?\d+", t):
            operands.append(float(t))
        elif t.startswith(b"/"):
            operands.append(t[1:].decode())
        elif t in (b"[", b"]", b"<<", b">>"):
            continue
        else:
            op = t.decode()
            if op == "Tf":
                font, size = operands[-2], operands[-1]
            elif op == "Tm":
                tm = (operands[-2], operands[-1])
            elif op == "re":
                x, y, w, h = operands[-4:]
                rects.append([x, page_h - (y + h), x + w, page_h - y])
            elif op in ("Tj", "'"):
                raw = operands[-1]
                f = fonts.get(font, {})
                text = "".join(f["cmap"].get(b, chr(b)) for b in raw) if f.get("cmap") else raw.decode("latin-1")
                width = sum((f["widths"][b - f["first"]] if 0 <= b - f["first"] < len(f["widths"]) else 500) for b in raw) * size / 1000
                x, y = tm
                runs.append({"text": text, "x0": x, "x1": x + width, "top": page_h - (y + f.get("ascent", 750) * size / 1000),
                             "bottom": page_h - (y + f.get("descent", -250) * size / 1000), "font": font, "size": size})
            operands = []
    return runs, rects, fonts


def validate_pdf(ctx: Ctx, spec: dict, loc: dict) -> dict:
    path = ctx.root / spec["file"]
    cs = ctx.truth["content_sets"][spec["content_set"]]
    data = path.read_bytes()
    res = {}
    sx = re.search(rb"startxref\s+(\d+)\s+%%EOF\s*$", data)
    xref_ok = bool(sx) and data[int(sx.group(1)):int(sx.group(1)) + 4] == b"xref"
    res["1_package_format"] = item("PASS" if data.startswith(b"%PDF-") and xref_ok else "FAIL",
                                   {"header": data[:8].decode("latin-1"), "startxref_points_to_xref": xref_ok})
    try:
        pdf = MiniPdf(data)
        pages = pdf.pages()
        page_h = float(re.search(rb"/MediaBox\s*\[\s*[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)", pdf.objs[pages[0]]).group(1))
        parsed = {i + 1: pdf_runs(pdf, n, page_h) for i, n in enumerate(pages)}
        res["2_not_corrupted"] = item("PASS", f"자체 디코더로 {len(pages)}쪽 콘텐츠 해독")
    except Exception as e:  # noqa: BLE001
        return {**{k: item("FAIL", "해독 실패") for k in ITEMS}, **res, "2_not_corrupted": item("FAIL", f"{type(e).__name__}: {e}")}
    blocks = {b["block_id"]: b for b in cs["blocks"]}
    tables = {t["table_id"]: t for t in cs["tables"]}

    def runs_in(page, box, pad=1.0):
        out = []
        for r in parsed[page][0]:
            cx, cy = (r["x0"] + r["x1"]) / 2, (r["top"] + r["bottom"]) / 2
            if box[0] - pad <= cx <= box[2] + pad and box[1] - pad <= cy <= box[3] + pad:
                out.append(r)
        return sorted(out, key=lambda r: (round(r["top"], 1), r["x0"]))

    def union(rs):
        return [min(r["x0"] for r in rs), min(r["top"] for r in rs), max(r["x1"] for r in rs), max(r["bottom"] for r in rs)]

    found = loc_ok = loc_tot = 0
    rendered = [b for b in blocks if b in loc["blocks"]]
    order_seq = []
    for bid in rendered:
        hits = 0
        for l in loc["blocks"][bid]:
            loc_tot += 1
            rs = runs_in(l["page"], l["bbox"])
            text = "".join(r["text"] for r in rs)
            ok = text == blocks[bid]["text"] and bool(rs) and iou(union(rs), l["bbox"]) >= IOU_TABLE
            loc_ok += ok
            hits += text == blocks[bid]["text"]
            order_seq.append((l["page"], l["bbox"][1], bid))
        found += hits == len(loc["blocks"][bid])
    res["3_text_blocks"] = ratio_item(found, len(rendered), {"rendered": rendered, "not_rendered": sorted(set(blocks) - set(rendered))})
    cell_ok = cell_tot = merge_ok = merge_tot = frag_iou_ok = frag_tot = cell_pos_ok = 0
    logical = {}
    for tid, e in loc["tables"].items():
        t = tables[tid]
        truth_cells = {(c["row"], c["col"]): c for c in t["cells"]}
        for f in e["fragments"]:
            frag_tot += 1
            order_seq.append((f["page"], f["bbox"][1], f"{tid}#{f['fragment_index']}"))
            rects = [r for r in parsed[f["page"]][1] if r[0] >= f["bbox"][0] - 1 and r[2] <= f["bbox"][2] + 1
                     and r[1] >= f["bbox"][1] - 1 and r[3] <= f["bbox"][3] + 1]
            if rects:
                u = [min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)]
                frag_iou_ok += iou(u, f["bbox"]) >= IOU_TABLE
            for key, cl in f["cells"].items():
                r_, c_ = map(int, key.split(","))
                tc = truth_cells[(r_, c_)]
                cell_tot += 1
                rs = runs_in(cl["page"], cl["bbox"], pad=0.0)
                text = "".join(x["text"] for x in rs)
                ok = text == tc["text"]
                cell_ok += ok
                # 셀 테두리(re) 중 기록 bbox와 일치하는 사각형이 있는가 → 병합 크기 확인
                has_rect = any(iou(rr, cl["bbox"]) > 0.95 for rr in parsed[cl["page"]][1])
                cell_pos_ok += has_rect and ok
                if tc["rowspan"] > 1 or tc["colspan"] > 1:
                    merge_tot += 1
                    merge_ok += has_rect
                logical.setdefault(tid, {}).setdefault((r_, c_), text)
    res["5_table_count"] = item("PASS" if frag_iou_ok == frag_tot and frag_tot > 0 else "FAIL",
                                f"표 조각 {frag_tot}개 중 표 영역(테두리 합) IoU≥{IOU_TABLE} {frag_iou_ok}개", frag_iou_ok, frag_tot)
    res["6_cell_count"] = ratio_item(cell_ok, cell_tot, "기록된 셀 영역 안의 텍스트 런이 정답 셀 텍스트와 일치 (반복 헤더 포함)")
    res["7_merged_cells"] = ratio_item(merge_ok, merge_tot, "병합 영역 크기의 셀 테두리 사각형 존재")
    val_ok = val_tot = 0
    for v in cs["extracted_values"]:
        tid = v["source"]["table_id"]
        if tid in loc["tables"]:
            val_tot += 1
            val_ok += logical.get(tid, {}).get((v["source"]["row"], v["source"]["col"])) == v["raw"]
    res["8_numbers_units_dates"] = ratio_item(val_ok, val_tot)
    res["9_canonical_refs"] = canonical_check(ctx, cs, list(loc["tables"]), lambda t, r, c: logical.get(t, {}).get((r, c)))
    res["10_source_location"] = ratio_item(loc_ok + cell_pos_ok, loc_tot + cell_tot,
                                           f"PDF 내부 좌표(콘텐츠 스트림) 기준: 블록 IoU≥{IOU_TABLE}, 셀 테두리 일치. 파서 추출 bbox 정확도는 미측정")
    seq_sorted = sorted(order_seq, key=lambda x: (x[0], x[1]))
    rep_ok = rep_tot = 0
    for tid, e in loc["tables"].items():
        for f in e["fragments"][1:]:
            rep_tot += 1
            hdr = list(range(1, tables[tid]["header_rows"] + 1))
            rep_ok += f["repeated_header_rows"] == hdr and all(
                "".join(x["text"] for x in runs_in(cl["page"], cl["bbox"], 0.0)) == tables[tid]["cells"][[(c["row"], c["col"]) for c in tables[tid]["cells"]].index(tuple(map(int, k.split(","))))]["text"]
                for k, cl in f["cells"].items() if int(k.split(",")[0]) in hdr)
    plan_pages = loc["pages"]
    labels_ok = all(any(r["text"] == f"{p} / {plan_pages}" for r in parsed[p][0]) for p in parsed)
    res["11_multi_page_slide"] = item("PASS" if len(pages) == plan_pages and rep_ok == rep_tot and labels_ok else "FAIL",
                                      {"pages": len(pages), "expected": plan_pages, "repeated_header_fragments": f"{rep_ok}/{rep_tot}",
                                       "page_labels": labels_ok})
    # 4 순서: 머리말·꼬리말(페이지 상·하단 50pt)을 뺀 본문 요소의 (페이지, 위→아래) 순서가
    #   같은 내용 묶음 DOCX의 본문 순서(body_order)와 같은가
    def furniture(l):
        return l["bbox"][1] < 50 or l["bbox"][3] > page_h - 50
    ref_doc = next((d for d in ctx.truth["documents"] if d["format"] == "docx" and d["content_set"] == spec["content_set"]), None)
    expected_order = ref_doc["layout"]["body_order"] if ref_doc else []
    body_seq = []
    for p_, top, oid in seq_sorted:
        base = oid.split("#")[0]
        if base in blocks and all(furniture(l) for l in loc["blocks"][base]):
            continue
        if base not in body_seq:
            body_seq.append(base)
    res["4_text_order"] = item("PASS" if body_seq == expected_order else "FAIL", {"actual": body_seq, "expected_docx_body_order": expected_order})
    hf = [b for b in rendered if all(furniture(l) for l in loc["blocks"][b])]
    hf_ok = sum(1 for b in hf if all("".join(x["text"] for x in runs_in(l["page"], l["bbox"])) == blocks[b]["text"] for l in loc["blocks"][b]))
    res["12_header_footer_notes"] = ratio_item(hf_ok, len(hf), {"repeated_blocks": hf, "per_page": {b: len(loc["blocks"][b]) for b in hf}})
    fonts_all = {k: v for p in parsed.values() for k, v in p[2].items()}
    tt = {k: v for k, v in fonts_all.items() if v["subtype"] == "TrueType"}
    text_layer = bool(tt) and all(v["to_unicode"] for v in tt.values())
    res["13_visual_layout"] = item("NEEDS_MANUAL_REVIEW", "PDF 뷰어로 한글 렌더링·겹침 미검수")
    info = re.search(rb"/Author\s*\((.*?)\)\s*/CreationDate", data, re.S)
    author = info.group(1).replace(b"\\(", b"(").replace(b"\\)", b")").decode("latin-1") if info else None
    risky = [k.decode() for k in (b"/URI", b"/Launch", b"/EmbeddedFile", b"/JavaScript") if k in data]
    res["14_metadata_privacy"] = item("PASS" if author == AUTHOR and not risky else "FAIL",
                                      {"author": author, "risky_keys": risky, "creation_date_fixed": b"D:20000101000000" in data})
    res["_text_layer"] = {"truetype_fonts_with_tounicode": text_layer, "fonts": {k: {"subtype": v["subtype"], "to_unicode": v["to_unicode"]} for k, v in fonts_all.items()},
                          "decoder": "자체 최소 디코더 (ToUnicode bfchar, Tj 연산자) — 외부 PDF 파서 추출 결과 아님"}
    return res


def validate(root: Path | None = None) -> dict:
    ctx = Ctx(Path(root) if root else ROOT)
    out = {}
    for d in ctx.truth["documents"]:
        loc = ctx.locs["documents"].get(d["doc_id"])
        if loc is None:
            continue
        if not (ctx.root / d["file"]).exists():
            # 공개 저장소에서 보류한 문서(예: 폰트 서브셋 재배포 조건 미확인 PDF)는 새 클론에 없다 → 측정하지 않음
            out[d["doc_id"]] = {k: item("NOT_MEASURED", "파일 없음 — 로컬 전용 보류 문서이거나 생성 전") for k in ITEMS}
            continue
        fn = {"docx": validate_docx, "pdf_text": validate_pdf, "pptx": validate_pptx}[d["format"]]
        out[d["doc_id"]] = fn(ctx, d, loc)
    return out


def extract_signature(report: dict) -> dict:
    """재현성 비교용: 검증 결과의 상태·분자·분모만."""
    return {doc: {k: (v["status"], v["numerator"], v["denominator"]) for k, v in items.items() if not k.startswith("_")}
            for doc, items in report.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=None)
    args = ap.parse_args(argv)
    rep = validate(args.root)
    for doc, items in rep.items():
        print(doc, {k: v["status"] + (f" {v['numerator']}/{v['denominator']}" if v.get("denominator") is not None else "")
                    for k, v in items.items() if not k.startswith("_")})
    fails = [(d, k) for d, it in rep.items() for k, v in it.items() if not k.startswith("_") and v["status"] == "FAIL"]
    print("FAIL:", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
