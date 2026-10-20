"""E03 문서 샘플 독립 검증 테스트 (정상 문서 + 음성 대조)."""

from __future__ import annotations

import ast
import base64
import re
import shutil
import tempfile
import zipfile
import zlib
from pathlib import Path

import pytest

import e03_validate_docs as V

ROOT = Path(__file__).resolve().parents[1]
# P-01·P-02는 폰트 서브셋 재배포 조건 미확인으로 공개 저장소에서 보류(D-020) → 새 클론에는 없을 수 있다
PDF_PRESENT = all((ROOT / "data" / "documents" / n).exists() for n in ("P-01_bom_spec.pdf", "P-02_order_inventory.pdf"))
needs_pdf = pytest.mark.skipif(not PDF_PRESENT, reason="PDF 샘플 없음 (공개 보류 문서, 로컬 전용)")


@pytest.fixture(scope="module")
def report():
    return V.validate()


def test_validator_does_not_import_generator():
    tree = ast.parse((ROOT / "scripts" / "e03_validate_docs.py").read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "e03_generate_docs" not in mods


def test_six_documents_present_and_no_fail(report):
    assert sorted(report) == ["D-01", "D-02", "P-01", "P-02", "T-01", "T-02"]
    fails = [(d, k) for d, it in report.items() for k, v in it.items() if not k.startswith("_") and v["status"] == "FAIL"]
    assert fails == []
    # 파일이 없는 보류 문서는 NOT_MEASURED(test_missing_document_is_not_measured_not_fail에서 검사)
    present = [d for d, it in report.items() if not str(it["13_visual_layout"].get("detail", "")).startswith("파일 없음")]
    assert all(report[d]["13_visual_layout"]["status"] == "NEEDS_MANUAL_REVIEW" for d in present)
    assert PDF_PRESENT or not {"P-01", "P-02"} & set(present)


def test_no_zero_denominator_reported_as_pass(report):
    for d, it in report.items():
        for k, v in it.items():
            if not k.startswith("_") and v.get("denominator") == 0:
                assert v["status"] == "NOT_MEASURED", (d, k)


@needs_pdf
def test_pdf_text_layer_and_pages(report):
    for d, pages in (("P-01", 1), ("P-02", 3)):
        assert report[d]["_text_layer"]["truetype_fonts_with_tounicode"] is True
        assert report[d]["11_multi_page_slide"]["detail"]["pages"] == pages
    assert report["P-02"]["11_multi_page_slide"]["detail"]["repeated_header_fragments"] == "1/1"


def test_pptx_group_and_notes(report):
    d = report["T-01"]["12_header_footer_notes"]["detail"]
    assert d["notes_blocks"] == ["CS3-b03"] and d["groups"][0]["children"][1][1] == "txt_CS3-b02"


# ---------------- 음성 대조 (복사본만 변경) ----------------
@pytest.fixture()
def sandbox():
    with tempfile.TemporaryDirectory(prefix="e03_neg_") as t:
        root = Path(t)
        shutil.copytree(ROOT / "data" / "documents", root / "data" / "documents")
        (root / "data" / "canonical").mkdir(parents=True)
        for n in ("e03_document_truth_v1.json", "e03_document_locations_v1.json"):
            shutil.copy(ROOT / "data" / "canonical" / n, root / "data" / "canonical" / n)
        yield root


def _rewrite_zip(path: Path, member: str, old: bytes, new: bytes) -> None:
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    hit = False
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in items:
            if info.filename == member and old in data:
                data = data.replace(old, new, 1)
                hit = True
            z.writestr(info, data)
    assert hit, f"{member}에 {old!r} 없음"


def test_negative_docx_cell_value(sandbox):
    _rewrite_zip(sandbox / "data/documents/D-01_bom_spec.docx", "word/document.xml", b">1.2<", b">1.3<")
    r = V.validate(sandbox)["D-01"]
    assert r["6_cell_count"]["status"] == "FAIL" and r["8_numbers_units_dates"]["status"] == "FAIL" and r["9_canonical_refs"]["status"] == "FAIL"


def test_negative_docx_merge_removed(sandbox):
    _rewrite_zip(sandbox / "data/documents/D-01_bom_spec.docx", "word/document.xml", b'<w:gridSpan w:val="2"/>', b"")
    assert V.validate(sandbox)["D-01"]["7_merged_cells"]["status"] == "FAIL"


def test_negative_pptx_notes_and_cell(sandbox):
    p = sandbox / "data/documents/T-01_plan_comparison.pptx"
    with zipfile.ZipFile(p) as z:
        notes = [n for n in z.namelist() if n.startswith("ppt/notesSlides/") and n.endswith(".xml")][0]
    _rewrite_zip(p, notes, "발표자 노트".encode("utf-8"), "발표자 메모".encode("utf-8"))
    _rewrite_zip(p, "ppt/slides/slide2.xml", b">FG001<", b">FG009<")
    r = V.validate(sandbox)["T-01"]
    assert r["12_header_footer_notes"]["status"] == "FAIL" and r["6_cell_count"]["status"] == "FAIL"


@needs_pdf
def test_negative_pdf_content_stream(sandbox):
    p = sandbox / "data/documents/P-02_order_inventory.pdf"
    data = p.read_bytes()
    changed = False
    for m in re.finditer(rb"(\d+) 0 obj\s*<<(.*?)>>\s*stream\r?\n(.*?)endstream", data, re.S):
        if b"ASCII85Decode" not in m.group(2):
            continue
        raw = m.group(3).strip()
        content = zlib.decompress(base64.a85decode(raw[:-2]))
        if b"(O015)" in content:
            new = base64.a85encode(zlib.compress(content.replace(b"(O015)", b"(O016)")), adobe=False) + b"~>"
            data = data.replace(raw, new, 1)
            changed = True
            break
    assert changed
    p.write_bytes(data)
    r = V.validate(sandbox)["P-02"]
    assert r["6_cell_count"]["status"] == "FAIL" and r["8_numbers_units_dates"]["status"] == "FAIL"


@needs_pdf
def test_negative_pdf_location_shift(sandbox):
    lp = sandbox / "data/canonical/e03_document_locations_v1.json"
    import json
    loc = json.loads(lp.read_text(encoding="utf-8"))
    cell = loc["documents"]["P-01"]["tables"]["CS1-T1"]["fragments"][0]["cells"]["3,2"]
    cell["bbox"] = [b + 120 for b in cell["bbox"]]
    lp.write_text(json.dumps(loc, ensure_ascii=False), encoding="utf-8")
    assert V.validate(sandbox)["P-01"]["10_source_location"]["status"] == "FAIL"


def test_missing_document_is_not_measured_not_fail(sandbox):
    (sandbox / "data/documents/P-01_bom_spec.pdf").unlink(missing_ok=True)
    r = V.validate(sandbox)["P-01"]
    assert {v["status"] for v in r.values()} == {"NOT_MEASURED"}


def test_negative_truth_hash_guard(sandbox):
    tp = sandbox / "data/canonical/e03_document_truth_v1.json"
    tp.write_bytes(tp.read_bytes().replace("가정용 히터 A".encode("utf-8"), "가정용 히터 Z".encode("utf-8"), 1))
    with pytest.raises(SystemExit):
        V.validate(sandbox)


def test_truth_spec_unchanged():
    import hashlib
    assert hashlib.sha256((ROOT / "data/canonical/e03_document_truth_v1.json").read_bytes()).hexdigest() == V.TRUTH_SHA256
