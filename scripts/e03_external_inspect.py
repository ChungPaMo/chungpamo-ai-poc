"""E03 외부 제작 문서 후보 검사: 형식·안전성·구조 특성·(PDF) 공식 주석 대응 확인.

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_inspect.py

블라인드 조건: 평가 대상 파서(python-docx·python-pptx·pypdf·pdfplumber)와 E03 파서 코드(src/parsers)를 쓰지 않는다.
OOXML은 zipfile + lxml로 XML을 직접 읽고, PDF는 pypdfium2(PDFium)로 쪽 수·텍스트 레이어·선 객체만 본다.
매크로·OLE·외부 링크는 실행하지 않고 존재 여부만 기록한다. 문서 작성자 이름 등 개인 메타데이터 값은 기록하지 않는다.
결과: results/E03_document_parsers/external_candidates/ (manifest.csv, inspection.json, summary.md)
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
import zipfile
import zlib
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "configs" / "e03_external_sources.json"
RAW = ROOT / "data" / "raw" / "external_documents"
OUT = ROOT / "results" / "E03_document_parsers" / "external_candidates"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
      "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
      "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
      "dc": "http://purl.org/dc/elements/1.1/"}
W = "{%s}" % NS["w"]
PDF_RISK_TOKENS = [b"/JavaScript", b"/JS", b"/OpenAction", b"/AA", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/SubmitForm",
                   b"/XFA", b"/Encrypt", b"/URI", b"/GoToR"]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def xml(z: zipfile.ZipFile, name: str):
    return etree.fromstring(z.read(name)) if name in z.namelist() else None


# ---------------- OOXML 공통 ----------------

def ooxml_common(z: zipfile.ZipFile) -> dict:
    names = z.namelist()
    ct = xml(z, "[Content_Types].xml")
    overrides = [o.get("ContentType") for o in ct] if ct is not None else []
    ext_rels, rel_types = [], Counter()
    for n in names:
        if n.endswith(".rels"):
            for r in xml(z, n):
                rel_types[r.get("Type", "").rsplit("/", 1)[-1]] += 1
                if r.get("TargetMode") == "External":
                    u = urlparse(r.get("Target", ""))
                    ext_rels.append({"part": n, "type": r.get("Type", "").rsplit("/", 1)[-1], "scheme": u.scheme or "(상대/파일)", "host": u.netloc})
    app = xml(z, "docProps/app.xml")
    core = xml(z, "docProps/core.xml")
    gt = lambda root, tag: (root.findtext(tag, namespaces=NS) if root is not None else None)
    return {
        "parts": len(names),
        "macro_vba": any("vbaproject" in n.lower() for n in names) or any("macroEnabled" in (o or "") for o in overrides),
        "activex": any("activex" in n.lower() for n in names),
        "ole_embeddings": sorted(n for n in names if "embeddings/" in n.lower() or "oleobject" in n.lower()),
        "external_relationships": ext_rels,
        "attached_template": rel_types.get("attachedTemplate", 0),
        "alt_chunk": rel_types.get("aFChunk", 0),
        "embedded_fonts": sorted(n for n in names if n.lower().endswith((".fntdata", ".odttf")) or "/fonts/" in n.lower()),
        "media": sum(1 for n in names if "/media/" in n),
        "app": {"Application": gt(app, "ep:Application"), "AppVersion": gt(app, "ep:AppVersion")},
        "core_personal_fields_present": {k: bool(gt(core, k)) for k in ("dc:creator", "cp:lastModifiedBy")} if core is not None else "docProps/core.xml 없음",
    }


# ---------------- DOCX ----------------

def table_stats(tbl) -> dict:
    rows = tbl.findall(W + "tr")
    grid = tbl.find(W + "tblGrid")
    spans = vm_restart = vm_cont = 0
    for tc in tbl.iter(W + "tc"):
        if tc.getparent().getparent() is not tbl and tc.getparent().getparent().getparent() is not tbl:
            continue
        pr = tc.find(W + "tcPr")
        if pr is None:
            continue
        gs = pr.find(W + "gridSpan")
        if gs is not None and int(gs.get(W + "val", "1")) > 1:
            spans += 1
        vm = pr.find(W + "vMerge")
        if vm is not None:
            if vm.get(W + "val") == "restart":
                vm_restart += 1
            else:
                vm_cont += 1
    anc = [a.tag.split("}")[1] for a in tbl.iterancestors()]
    return {"rows": len(rows), "grid_cols": len(grid.findall(W + "gridCol")) if grid is not None else None,
            "rows_wrapped_in_sdt": sum(1 for r in tbl.findall(W + "sdt")),
            "gridSpan_cells": spans, "vMerge_restart": vm_restart, "vMerge_continue": vm_cont,
            "nested_in_table": anc.count("tbl"), "inside_sdt": "sdt" in anc, "direct_body_child": tbl.getparent().tag == W + "body",
            "cell_paragraphs": sum(1 for _ in tbl.iter(W + "p")), "cell_lists": sum(1 for p in tbl.iter(W + "p") if p.find(f"{W}pPr/{W}numPr") is not None)}


def inspect_docx(z: zipfile.ZipFile) -> dict:
    doc = xml(z, "word/document.xml")
    body = doc.find(W + "body")
    names = z.namelist()
    notes = {}
    for part, tag in (("word/footnotes.xml", "footnote"), ("word/endnotes.xml", "endnote")):
        root = xml(z, part)
        notes[tag + "s"] = sum(1 for n in root.findall(W + tag) if n.get(W + "type") not in ("separator", "continuationSeparator", "continuationNotice")) if root is not None else 0
    tables = [table_stats(t) for t in body.iter(W + "tbl")]
    return {
        "body_direct_paragraphs": len(body.findall(W + "p")),
        "body_direct_tables": len(body.findall(W + "tbl")),
        "tables_total": len(tables), "tables": tables,
        "content_controls_sdt": sum(1 for _ in body.iter(W + "sdt")),
        "sections": sum(1 for _ in body.iter(W + "sectPr")),
        "header_parts": sum(1 for n in names if re.match(r"word/header\d*\.xml$", n)),
        "footer_parts": sum(1 for n in names if re.match(r"word/footer\d*\.xml$", n)),
        **notes,
        "comments": len(xml(z, "word/comments.xml").findall(W + "comment")) if "word/comments.xml" in names else 0,
        "tracked_ins": sum(1 for _ in body.iter(W + "ins")), "tracked_del": sum(1 for _ in body.iter(W + "del")),
        "fields": sum(1 for _ in body.iter(W + "fldChar")) // 3 + sum(1 for _ in body.iter(W + "fldSimple")),
        "drawings": sum(1 for _ in body.iter(W + "drawing")),
        "hyperlinks": sum(1 for _ in body.iter(W + "hyperlink")),
        "alternate_content": sum(1 for e in body.iter() if isinstance(e.tag, str) and e.tag.endswith("}AlternateContent")),
        "text_chars": sum(len(t.text or "") for t in body.iter(W + "t")),
    }


# ---------------- PPTX ----------------

def inspect_pptx(z: zipfile.ZipFile) -> dict:
    pres = xml(z, "ppt/presentation.xml")
    prels = {r.get("Id"): r.get("Target") for r in xml(z, "ppt/_rels/presentation.xml.rels")}
    slides = []
    P, A = "{%s}" % NS["p"], "{%s}" % NS["a"]
    for i, sid in enumerate(pres.find(P + "sldIdLst"), start=1):
        part = "ppt/" + prels[sid.get("{%s}id" % NS["r"])]
        root = xml(z, part)
        tree = root.find(f"{P}cSld/{P}spTree")
        rels_name = part.replace("slides/", "slides/_rels/") + ".rels"
        srels = [r.get("Type", "").rsplit("/", 1)[-1] for r in xml(z, rels_name)] if rels_name in z.namelist() else []

        def depth(e, d=0):
            kids = [c for c in e if c.tag == P + "grpSp"]
            return max([depth(c, d + 1) for c in kids], default=d)
        frames = list(tree.iter(P + "graphicFrame"))
        kinds = Counter()
        tables = []
        for f in frames:
            uri = f.find(f"{A}graphic/{A}graphicData").get("uri", "")
            kind = "table" if uri.endswith("/table") else "chart" if "chart" in uri else "smartart" if "diagram" in uri else uri.rsplit("/", 1)[-1] or "other"
            kinds[kind] += 1
            if kind == "table":
                tbl = f.find(f".//{A}tbl")
                cells = list(tbl.iter(A + "tc"))
                tables.append({"rows": len(tbl.findall(A + "tr")), "cols": len(tbl.find(A + "tblGrid")),
                               "gridSpan_gt1": sum(1 for c in cells if int(c.get("gridSpan", "1")) > 1),
                               "rowSpan_gt1": sum(1 for c in cells if int(c.get("rowSpan", "1")) > 1),
                               "hMerge": sum(1 for c in cells if c.get("hMerge") in ("1", "true")),
                               "vMerge": sum(1 for c in cells if c.get("vMerge") in ("1", "true")),
                               "in_placeholder": f.find(f"{P}nvGraphicFramePr/{P}nvPr/{P}ph") is not None,
                               "inside_group": f.getparent().tag == P + "grpSp"})
        xfrms = [x for x in tree.iter(A + "xfrm")] + [x for x in tree.iter(P + "xfrm")]
        slides.append({
            "slide": i, "shapes_sp": sum(1 for _ in tree.iter(P + "sp")), "groups": sum(1 for _ in tree.iter(P + "grpSp")),
            "max_group_depth": depth(tree), "connectors": sum(1 for _ in tree.iter(P + "cxnSp")), "pictures": sum(1 for _ in tree.iter(P + "pic")),
            "graphic_frames": dict(kinds), "tables": tables,
            "rotated": sum(1 for x in xfrms if x.get("rot") not in (None, "0")), "flipped": sum(1 for x in xfrms if x.get("flipH") == "1" or x.get("flipV") == "1"),
            "text_runs": sum(1 for _ in tree.iter(A + "t")), "notes": "notesSlide" in srels,
            "hidden": root.get("show") == "0",
        })
    return {"slides": len(slides), "per_slide": slides,
            "totals": {k: sum(s[k] for s in slides) for k in ("shapes_sp", "groups", "connectors", "pictures", "rotated", "flipped", "text_runs")}
            | {"max_group_depth": max(s["max_group_depth"] for s in slides), "tables": sum(len(s["tables"]) for s in slides),
               "charts": sum(s["graphic_frames"].get("chart", 0) for s in slides), "smartart": sum(s["graphic_frames"].get("smartart", 0) for s in slides),
               "notes_slides": sum(s["notes"] for s in slides)},
            "diagram_parts": sorted(n for n in z.namelist() if n.startswith("ppt/diagrams/")),
            "chart_parts": sum(1 for n in z.namelist() if re.match(r"ppt/charts/chart\d+\.xml$", n))}


# ---------------- PDF ----------------

def pdf_safety(data: bytes) -> dict:
    """객체 사전(스트림 본문 밖) + 객체 스트림(/Type /ObjStm)만 검색. 이미지·글꼴 등 이진 스트림 본문의 우연한 바이트는 제외."""
    hits = Counter()
    outside, objstm, pos = [], 0, 0
    for m in re.finditer(rb"stream\r?\n", data):
        end = data.find(b"endstream", m.end())
        if end < 0:
            break
        outside.append(data[pos:m.start()])
        head = data[max(pos, m.start() - 400):m.start()]
        if b"/ObjStm" in head:
            try:
                outside.append(zlib.decompress(data[m.end():end]))
                objstm += 1
            except zlib.error:
                pass
        pos = end + len(b"endstream")
    outside.append(data[pos:])
    text = b"\n".join(outside)
    for t in PDF_RISK_TOKENS:
        hits[t.decode()] += len(re.findall(re.escape(t) + rb"(?![A-Za-z])", text))
    actions = []
    for m in re.finditer(rb"/OpenAction\s*(\d+)\s+0\s+R", text):
        obj = re.search(rb"(?<![0-9])" + m.group(1) + rb"\s+0\s+obj(.{0,300}?)endobj", text, re.S)
        s = re.search(rb"/S\s*/(\w+)", obj.group(1)) if obj else None
        actions.append({"target_obj": int(m.group(1)), "action_type": s.group(1).decode() if s else ("목적지 배열(이동)" if obj and b"[" in obj.group(1) else "미확인")})
    if re.search(rb"/OpenAction\s*\[", text):
        actions.append({"target_obj": None, "action_type": "목적지 배열(이동)"})
    return {"risk_tokens": {k: v for k, v in hits.items() if v}, "object_streams_scanned": objstm, "open_actions": actions,
            "note": "객체 사전·객체 스트림만 검색 (스트림 본문 제외, 실행·렌더링 없음). /URI는 일반 하이퍼링크일 수 있음"}


def inspect_pdf(path: Path, ann_path: Path | None) -> dict:
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    pdf = pdfium.PdfDocument(str(path))
    meta = pdf.get_metadata_dict()
    pages = []
    for i in range(len(pdf)):
        pg = pdf[i]
        tp = pg.get_textpage()
        pages.append({"page_index": i, "size_pt": [round(x, 2) for x in pg.get_size()], "chars": tp.count_chars()})
    out = {"pages": len(pdf), "page_info": pages, "text_layer": all(p["chars"] > 0 for p in pages),
           "producer_software": {k: meta.get(k) for k in ("Producer", "Creator")}, "pdf_version": pdf.get_version(),
           "author_field_present": bool(meta.get("Author"))}
    if ann_path is None:
        out["annotation"] = None
        out["line_objects_per_page"] = [line_counts(pdf[i], None, pdfium_c) for i in range(len(pdf))]
        return out
    tables = json.loads(ann_path.read_text(encoding="utf-8"))
    ann = []
    for t in tables:
        pg = pdf[t["pdf_page_index"]] if t["pdf_page_index"] < len(pdf) else None
        W_, H_ = pg.get_size() if pg else (None, None)
        fb = t["pdf_full_page_bbox"]
        rec = {"structure_id": t["structure_id"], "split": t["split"], "page_index": t["pdf_page_index"], "rows": len(t["rows"]), "cols": len(t["columns"]),
               "cells": len(t["cells"]), "spanning_cells": sum(1 for c in t["cells"] if len(c["row_nums"]) > 1 or len(c["column_nums"]) > 1),
               "column_header_cells": sum(1 for c in t["cells"] if c["is_column_header"]),
               "projected_row_header_cells": sum(1 for c in t["cells"] if c["is_projected_row_header"]),
               "empty_cells": sum(1 for c in t["cells"] if not (c.get("pdf_text_content") or "").strip()),
               "excluded": t["exclude_for_structure"] or t["exclude_for_detection"],
               "page_size_matches": pg is not None and abs(W_ - (fb[2] - fb[0])) < 1 and abs(H_ - (fb[3] - fb[1])) < 1}
        if pg is not None:
            tp = pg.get_textpage()
            hit = tot = 0
            for c in t["cells"]:
                want = re.sub(r"\s+", "", c.get("pdf_text_content") or "")
                if not want:
                    continue
                x0, y0, x1, y1 = c["pdf_bbox"]
                got = re.sub(r"\s+", "", tp.get_text_bounded(left=x0, bottom=H_ - y1, right=x1, top=H_ - y0))
                tot += 1
                hit += got == want
            rec["cell_text_correspondence"] = {"numerator": hit, "denominator": tot, "rate": round(hit / tot, 4) if tot else None,
                                               "method": "주석 pdf_bbox(좌상단 원점 가정)를 PDFium 좌표로 바꿔 영역 텍스트를 읽고, 공백 제거 후 주석 pdf_text_content와 완전 일치"}
            rec["rules"] = line_counts(pg, t["pdf_table_bbox"], pdfium_c, H_)
        ann.append(rec)
    out["annotation"] = {"file": ann_path.name, "tables": ann}
    return out


def line_counts(pg, bbox, pdfium_c, H=None) -> dict:
    """표 영역(또는 쪽 전체) 안의 선 형태 경로 객체 수: 가로선(높이<2pt, 폭>10pt) / 세로선(폭<2pt, 높이>10pt) / 그 밖의 경로."""
    h = v = other = 0
    for obj in pg.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_PATH], max_depth=8):
        l, b, r, t = obj.get_bounds()
        if bbox is not None:
            x0, y0, x1, y1 = bbox
            if r < x0 - 2 or l > x1 + 2 or t < H - y1 - 2 or b > H - y0 + 2:
                continue
        w_, h_ = r - l, t - b
        if h_ < 2 and w_ > 10:
            h += 1
        elif w_ < 2 and h_ > 10:
            v += 1
        else:
            other += 1
    kind = "격자(세로선 있음)" if v >= 2 else "가로선만" if h else "선 없음 또는 사각형 경로만" if other else "선 없음"
    return {"horizontal": h, "vertical": v, "other_paths": other, "class": kind}


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    fetch = {f["id"]: f for f in json.loads((RAW / "fetch_log.json").read_text(encoding="utf-8"))["files"]}
    rows, detail = [], []
    for s in cfg["sources"]:
        p = RAW / s["format"] / s["file"]
        rec = {"id": s["id"], "role": s["role"], "format": s["format"], "file": s["file"], "source": fetch.get(s["id"], {}).get("url"),
               "license": s["license"], "producer_note": s["producer_note"], "present": p.exists()}
        if not p.exists():
            rec["error"] = "파일 없음"
            detail.append(rec)
            rows.append(rec)
            continue
        data = p.read_bytes()
        rec.update({"sha256": sha(data), "bytes": len(data)})
        if s.get("expected_sha256"):
            rec["matches_published_sha256"] = rec["sha256"] == s["expected_sha256"]
        if s.get("metadata_url"):
            rec["pmc_license_code"] = fetch[s["id"]].get("pmc_license_code")
            rec["pmc_pdf_md5_matches"] = fetch[s["id"]].get("pmc_pdf_md5_matches")
        try:
            if s["format"] in ("docx", "pptx"):
                rec["magic_ok"] = data[:4] == b"PK\x03\x04"
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    rec["zip_test"] = z.testzip() is None
                    main_ct = [o.get("ContentType") for o in xml(z, "[Content_Types].xml") if o.get("PartName") in ("/word/document.xml", "/ppt/presentation.xml")]
                    rec["main_content_type"] = main_ct[0] if main_ct else None
                    rec["safety"] = ooxml_common(z)
                    rec["structure"] = inspect_docx(z) if s["format"] == "docx" else inspect_pptx(z)
            else:
                rec["magic_ok"] = data[:5] == b"%PDF-"
                rec["safety"] = pdf_safety(data)
                ann = RAW / "pubtables1m" / "pdf_annotations_sample" / s["annotation"] if s.get("annotation") else None
                rec["structure"] = inspect_pdf(p, ann)
        except Exception as e:  # 검사 실패는 기록 (통과 처리하지 않음)
            rec["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        detail.append(rec)
        rows.append(rec)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "tools": tool_versions(),
            "blind_note": "평가 대상 파서·E03 파서 코드 미사용 (zipfile + lxml, pypdfium2)", "documents": detail}
    (OUT / "inspection.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    write_manifest(rows)
    print(json.dumps([{k: r.get(k) for k in ("id", "role", "magic_ok", "error")} for r in rows], ensure_ascii=False))
    return 0


def tool_versions() -> dict:
    from importlib.metadata import version
    return {"lxml": version("lxml"), "pypdfium2": version("pypdfium2"), "python": sys.version.split()[0]}


def write_manifest(rows: list[dict]) -> None:
    cols = ["id", "role", "format", "file", "source", "license", "sha256", "bytes", "magic_ok", "matches_published_sha256", "pmc_license_code",
            "pmc_pdf_md5_matches", "units", "tables", "merge_features", "producer", "macro_ole_activex", "external_links", "embedded_fonts", "error"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        st, sf = r.get("structure") or {}, r.get("safety") or {}
        row = dict(r)
        if r["format"] == "docx" and st:
            row["units"] = f"sections={st['sections']}"
            row["tables"] = f"{st['tables_total']} (본문 직속 {st['body_direct_tables']}, sdt 안 {sum(t['inside_sdt'] for t in st['tables'])}, 중첩 {sum(t['nested_in_table'] > 0 for t in st['tables'])})"
            row["merge_features"] = f"gridSpan {sum(t['gridSpan_cells'] for t in st['tables'])}, vMerge {sum(t['vMerge_restart'] + t['vMerge_continue'] for t in st['tables'])}"
        elif r["format"] == "pptx" and st:
            tt = st["totals"]
            row["units"] = f"slides={st['slides']}"
            row["tables"] = f"{tt['tables']} (차트 {tt['charts']}, SmartArt {tt['smartart']})"
            tabs = [t for s in st["per_slide"] for t in s["tables"]]
            row["merge_features"] = f"gridSpan {sum(t['gridSpan_gt1'] for t in tabs)}, rowSpan {sum(t['rowSpan_gt1'] for t in tabs)}, hMerge {sum(t['hMerge'] for t in tabs)}, vMerge {sum(t['vMerge'] for t in tabs)}"
        elif st:
            row["units"] = f"pages={st['pages']}"
            a = st.get("annotation")
            row["tables"] = f"{len(a['tables'])} (공식 주석)" if a else "미확인 (공식 주석 없음)"
            row["merge_features"] = f"spanning {sum(t['spanning_cells'] for t in a['tables'])}" if a else "미확인"
        if sf:
            if r["format"] == "pdf":
                other = [k for k in sf["risk_tokens"] if k not in ("/URI", "/OpenAction")]
                acts = ",".join(a["action_type"] for a in sf["open_actions"])
                row["macro_ole_activex"] = "; ".join(filter(None, [("위험 토큰 " + ",".join(other)) if other else "JavaScript·실행·첨부 없음",
                                                                  f"OpenAction={acts}" if acts else None]))
                row["external_links"] = sf["risk_tokens"].get("/URI", 0)
            else:
                emb = sf["ole_embeddings"]
                row["macro_ole_activex"] = (f"매크로 {'있음' if sf['macro_vba'] else '없음'}, ActiveX {'있음' if sf['activex'] else '없음'}, "
                                            f"임베딩 {len(emb)}" + (f" ({', '.join(Path(e).name for e in emb)})" if emb else ""))
                row["external_links"] = len(sf["external_relationships"])
                row["embedded_fonts"] = len(sf["embedded_fonts"])
                row["producer"] = f"{sf['app']['Application']} {sf['app']['AppVersion'] or ''}".strip() if sf["app"]["Application"] else "docProps/app.xml 없음 또는 Application 없음"
        if r["format"] == "pdf" and st:
            row["producer"] = " / ".join(v for v in st["producer_software"].values() if v) or "메타데이터 없음"
        w.writerow(row)
    (OUT / "manifest.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
