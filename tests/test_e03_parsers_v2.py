"""E03 직접 파서 v2 단위 테스트 — 테스트 안에서 만든 작은 합성 문서만 사용 (외부 문서·평가 묶음 미사용).

각 개선 기능: 정상 / 변형 / 누락 / 잘못된 병합 / 읽기 순서 / 원본 위치 / 미지원 구조.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

import e03_grade_external as G
from parsers.doc_docx import parse_docx
from parsers.doc_pdf import parse_pdf_pdfplumber
from parsers.doc_pptx import parse_pptx
from parsers.v2.docx_v2 import parse_docx_v2
from parsers.v2.pdf_v2 import parse_pdf_pdfplumber_v2
from parsers.v2.pptx_v2 import parse_pptx_v2

ROOT = Path(__file__).resolve().parents[1]


# ======================= PDF: 가로 괘선만 있는 표 =======================

def make_pdf(path: Path, *, top_rule=True, two_column=False, group_header=False, rules=True, decor_only=False, wrapped=False):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    H = A4[1]
    y = lambda top: H - top
    x0, x1 = 60, 300 if two_column else 520
    c.setFont("Helvetica", 9)
    c.drawString(x0, y(90), "Table 1. Synthetic values by group")
    if decor_only:
        for i in range(4):
            c.rect(100 + 40 * i, y(400), 12, 6, stroke=1, fill=0)
        c.save()
        return
    cols = [x0, x0 + 80, x0 + 160] if two_column else [x0, x0 + 150, x0 + 300]
    hdr_top = 110
    if rules and top_rule:
        c.line(x0, y(hdr_top - 9), x1, y(hdr_top - 9))
    if group_header:
        c.drawString(cols[1], y(hdr_top), "Group A")
        if rules:
            c.line(cols[1], y(hdr_top + 3), cols[2] + 50, y(hdr_top + 3))
        hdr_top += 12
    for cx, t in zip(cols, ["Item", "Mean", "SD"]):
        c.drawString(cx, y(hdr_top), t)
    if rules:
        c.line(x0, y(hdr_top + 4), x1, y(hdr_top + 4))
    rows = [["alpha", "1.25", "0.10"], ["beta", "2.50", "0.20"], ["gamma", "3.75", "0.30"]]
    top = hdr_top + 16
    for i, r in enumerate(rows):
        for cx, t in zip(cols, r):
            c.drawString(cx, y(top), t)
        top += 12
        if wrapped and i == 0:
            c.drawString(cols[1], y(top), "(adj)")
            top += 12
    if rules:
        c.line(x0, y(top - 7), x1, y(top - 7))
    if two_column:
        for k in range(12):
            c.drawString(330, y(100 + 12 * k), "This is running prose text in the second column of the page.")
    c.drawString(x0, y(top + 30), "A body paragraph after the table.")
    c.save()


def rules_tables(ir):
    return [t for t in ir["tables"] if t.get("format_specific", {}).get("detector") == "rules_text"]


def cell(t, r, c):
    return next((x for x in t["cells"] if (x["row"], x["col"]) == (r, c)), None)


def test_pdf_rule_table_normal_and_v1_contrast(tmp_path):
    p = tmp_path / "t.pdf"
    make_pdf(p)
    v2 = parse_pdf_pdfplumber_v2(p, "t.pdf")
    tb = rules_tables(v2)
    assert len(tb) == 1 and (tb[0]["n_rows"], tb[0]["n_cols"]) == (4, 3)
    assert cell(tb[0], 1, 2)["text"] == "Mean" and cell(tb[0], 1, 2)["is_header"] is True
    assert cell(tb[0], 4, 3)["text"] == "0.30" and cell(tb[0], 4, 3)["is_header"] is False
    assert parse_pdf_pdfplumber(p, "t.pdf")["tables"] == []          # v1은 세로선 없는 표를 못 찾음 (개선 전 기준)


def test_pdf_rule_table_variants(tmp_path):
    for kw, shape in (({"top_rule": False}, (4, 3)), ({"two_column": True}, (4, 3)), ({"wrapped": True}, (4, 3))):
        p = tmp_path / f"v{len(kw)}{list(kw)[0]}.pdf"
        make_pdf(p, **kw)
        tb = rules_tables(parse_pdf_pdfplumber_v2(p, p.name))
        assert len(tb) == 1 and (tb[0]["n_rows"], tb[0]["n_cols"]) == shape, kw
    p = tmp_path / "wrap.pdf"
    make_pdf(p, wrapped=True)
    tb = rules_tables(parse_pdf_pdfplumber_v2(p, p.name))[0]
    assert "(adj)" in cell(tb, 2, 2)["text"]                         # 첫 열이 빈 줄은 앞 행으로 합침


def test_pdf_group_header_span(tmp_path):
    p = tmp_path / "g.pdf"
    make_pdf(p, group_header=True)
    tb = rules_tables(parse_pdf_pdfplumber_v2(p, p.name))[0]
    g = next(x for x in tb["cells"] if x["text"] == "Group A")
    assert g["colspan"] == 2 and g["is_header"] is True              # 밑줄이 덮는 두 열


def test_pdf_missing_and_unsupported(tmp_path):
    p = tmp_path / "norule.pdf"
    make_pdf(p, rules=False)
    assert rules_tables(parse_pdf_pdfplumber_v2(p, p.name)) == []    # 괘선 없는 표: 미지원 (검출하지 않음)
    p = tmp_path / "decor.pdf"
    make_pdf(p, decor_only=True)
    assert parse_pdf_pdfplumber_v2(p, p.name)["tables"] == []        # 작은 장식 사각형은 표로 내지 않음


def test_pdf_location_and_reading_order(tmp_path):
    p = tmp_path / "t.pdf"
    make_pdf(p)
    ir = parse_pdf_pdfplumber_v2(p, "t.pdf")
    tb = rules_tables(ir)[0]
    seq = ir["format_specific"]["reading_sequence"]
    cap = next(b for b in ir["blocks"] if b["text"].startswith("Table 1"))
    after = next(b for b in ir["blocks"] if b["text"].startswith("A body paragraph"))
    assert seq.index(cap["block_id"]) < seq.index(tb["table_id"]) < seq.index(after["block_id"])
    c = cell(tb, 2, 1)
    assert c["location"]["page"] == 1 and c["location"]["bbox"][0] < c["location"]["bbox"][2] and c["location"]["bbox"][1] < c["location"]["bbox"][3]


def test_pdf_grader_detects_wrong_merge_and_location(tmp_path):
    p = tmp_path / "t.pdf"
    make_pdf(p)
    ir = parse_pdf_pdfplumber_v2(p, "t.pdf")
    tb = rules_tables(ir)[0]
    truth_cells = [{"row": x["row"], "col": x["col"], "rowspan": x["rowspan"], "colspan": x["colspan"], "text": x["text"], "bbox": x["location"]["bbox"],
                    "is_column_header": bool(x["is_header"]), "is_projected_row_header": False, "status": "VERIFIED_OFFICIAL"} for x in tb["cells"]]
    doc = {"doc_id": "S", "format": "pdf", "items": {}, "truth": {"tables": [{"table_id": "s", "page": 1, "bbox": tb["location"]["bbox"],
                                                                          "n_rows": tb["n_rows"], "n_cols": tb["n_cols"], "cells": truth_cells}]}}
    assert G.grade(ir, doc)["metrics"]["cells"]["text_loose_grid"]["rate"] == 1.0
    bad = json.loads(json.dumps(ir))
    t = rules_tables(bad)[0]
    cell(t, 2, 1)["colspan"] = 2                                     # 잘못된 병합
    for x in t["cells"]:
        x["location"]["bbox"] = [v + 200 for v in x["location"]["bbox"]]   # 원본 위치 오류
    m = G.grade(bad, doc)["metrics"]["cells"]
    assert m["false_merges"] >= 1 and m["cell_bbox_iou_ge_0_5"]["numerator"] == 0


# ======================= DOCX: 컨테이너·변경 추적·각주·스타일 없음 =======================

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def make_docx(path: Path, with_footnotes=True):
    body = (f'<w:document {W}><w:body>'
            '<w:p><w:r><w:t>First paragraph</w:t></w:r></w:p>'
            '<w:sdt><w:sdtPr/><w:sdtContent><w:p><w:r><w:t>Inside control</w:t></w:r></w:p>'
            '<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>'
            '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr><w:p><w:r><w:t>Span</w:t></w:r></w:p></w:tc></w:tr>'
            '<w:sdt><w:sdtContent><w:tr><w:tc><w:p><w:r><w:t>a</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>b</w:t></w:r></w:p></w:tc></w:tr></w:sdtContent></w:sdt>'
            '</w:tbl></w:sdtContent></w:sdt>'
            '<w:p><w:r><w:t xml:space="preserve">Kept </w:t></w:r><w:ins w:id="1" w:author="A"><w:r><w:t>inserted</w:t></w:r></w:ins>'
            '<w:del w:id="2" w:author="A"><w:r><w:delText>removed</w:delText></w:r></w:del>'
            + ('<w:r><w:footnoteReference w:id="1"/></w:r>' if with_footnotes else '') + '</w:p>'
            '<w:sectPr/></w:body></w:document>')
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          + ('<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>' if with_footnotes else '')
          + '</Types>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    drels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             + ('<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>' if with_footnotes else '')
             + '</Relationships>')
    notes = (f'<w:footnotes {W}><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
             '<w:footnote w:id="1"><w:p><w:r><w:t>A footnote text</w:t></w:r></w:p></w:footnote></w:footnotes>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", body)
        z.writestr("word/_rels/document.xml.rels", drels)
        if with_footnotes:
            z.writestr("word/footnotes.xml", notes)


def test_docx_v2_containers_tracked_footnotes_no_styles(tmp_path):
    p = tmp_path / "d.docx"
    make_docx(p)
    ir = parse_docx_v2(p, "d.docx")                                   # 스타일 부품 없음에서도 중단하지 않음
    texts = [b["text"] for b in ir["blocks"]]
    assert "Inside control" in texts and "Kept inserted" in texts and not any("removed" in t for t in texts)
    assert any(b["location"]["part"] == "footnotes" and b["text"] == "A footnote text" for b in ir["blocks"])
    t = ir["tables"][0]
    assert t["location"]["container_path"] == ["sdt"] and (t["n_rows"], t["n_cols"]) == (2, 2)
    assert cell(t, 1, 1)["colspan"] == 2 and cell(t, 2, 2)["text"] == "b"   # 콘텐츠 컨트롤로 감싼 행 포함


def test_docx_v2_reading_order_and_missing_parts(tmp_path):
    p = tmp_path / "d.docx"
    make_docx(p, with_footnotes=False)
    ir = parse_docx_v2(p, "d.docx")
    seq = ir["format_specific"]["reading_sequence"]
    pos = {b["text"]: seq.index(b["block_id"]) for b in ir["blocks"]}
    assert pos["First paragraph"] < pos["Inside control"] < seq.index(ir["tables"][0]["table_id"]) < pos["Kept inserted"]
    assert ir["format_specific"]["notes_read"] == {"footnotes": 0, "endnotes": 0}


def test_docx_v1_contrast_on_same_package(tmp_path):
    p = tmp_path / "d.docx"
    make_docx(p)
    v1 = parse_docx(p, "d.docx")
    assert v1["tables"] == [] and "Kept inserted" not in [b["text"] for b in v1["blocks"]]   # v1 한계가 그대로 보존됨


# ======================= PPTX: 차트·SmartArt =======================

def make_chart_pptx(path: Path):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Chart slide"
    cd = CategoryChartData()
    cd.categories = ["North", "South"]
    cd.add_series("Revenue", (1.0, 2.0))
    ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(2), Inches(6), Inches(4), cd).chart
    ch.has_title = True
    ch.chart_title.text_frame.text = "Sales by region"
    prs.save(str(path))


def test_pptx_v2_chart_text_and_v1_contrast(tmp_path):
    p = tmp_path / "c.pptx"
    make_chart_pptx(p)
    v2 = parse_pptx_v2(p, "c.pptx")
    ch = [b for b in v2["blocks"] if b.get("format_specific", {}).get("kind") == "chart"]
    assert len(ch) == 1 and all(t in ch[0]["text"] for t in ("Sales by region", "North", "South", "Revenue"))
    assert ch[0]["location"]["slide_index"] == 1 and ch[0]["location"]["shape_id"] is not None
    v1 = parse_pptx(p, "c.pptx")
    assert not any("North" in b["text"] for b in v1["blocks"])


def test_pptx_v2_without_graphics_matches_v1_text(tmp_path):
    from pptx import Presentation
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "Title"
    s.placeholders[1].text = "Body"
    p = tmp_path / "plain.pptx"
    prs.save(str(p))
    a, b = parse_pptx(p, "plain.pptx"), parse_pptx_v2(p, "plain.pptx")
    assert [x["text"] for x in a["blocks"]] == [x["text"] for x in b["blocks"]]


SMARTART_DEV = ROOT / "data" / "raw" / "external_documents" / "pptx" / "smartart-hyperlink.pptx"


@pytest.mark.skipif(not SMARTART_DEV.exists(), reason="개발용 외부 문서 없음 (로컬 전용)")
def test_pptx_v2_smartart_on_dev_document():
    ir = parse_pptx_v2(SMARTART_DEV, SMARTART_DEV.name)
    sa = [b for b in ir["blocks"] if b.get("format_specific", {}).get("kind") == "smartart"]
    assert len(sa) == 1 and sa[0]["text"].strip()
