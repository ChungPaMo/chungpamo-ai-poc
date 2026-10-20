"""E03 직접 문서 파서 + 독립 채점기 테스트 (정상 + 음성 대조).

PDF(P-01·P-02)는 공개 보류 문서라 새 클론에 없을 수 있다 → PDF 필요 테스트는 사유와 함께 건너뛴다 (통과로 세지 않음).
"""

from __future__ import annotations

import ast
import copy
import csv
import json
import re
from pathlib import Path

import pytest

import e03_grade_parsers as G
from e03_parse_doc import ir_digest
from parsers.doc_registry import PARSERS

ROOT = Path(__file__).resolve().parents[1]
DOCS = {r["doc_id"]: r for r in csv.DictReader(open(ROOT / "results" / "E03_document_parsers" / "sample_manifest.csv", encoding="utf-8"))}
PDF_PRESENT = all((ROOT / DOCS[d]["file"]).exists() for d in ("P-01", "P-02"))
needs_pdf = pytest.mark.skipif(not PDF_PRESENT, reason="PDF 샘플 없음 (공개 보류 문서, 로컬 전용)")
PARSER_FOR = {"D-01": "python-docx", "D-02": "python-docx", "T-01": "python-pptx", "T-02": "python-pptx"}


def parse(doc_id: str, parser: str | None = None) -> dict:
    d = DOCS[doc_id]
    return PARSERS[parser or PARSER_FOR[doc_id]][1](ROOT / d["file"], d["file"])


@pytest.fixture(scope="module")
def truth():
    return G.load_truth()


@pytest.fixture(scope="module")
def irs():
    return {d: parse(d) for d in PARSER_FOR}


def g(ir, doc_id, truth):
    return G.grade(ir, DOCS[doc_id], *truth)


# ---- 독립성 ----

def test_parser_sources_do_not_reference_answers():
    for p in (ROOT / "src" / "parsers").glob("doc_*.py"):
        text = p.read_text(encoding="utf-8")
        for bad in ("canonical", "e03_document_truth", "e03_document_locations", "sample_manifest", "CS1-", "CS2-", "CS3-"):
            assert bad not in text, (p.name, bad)


def test_grader_does_not_import_parsers():
    tree = ast.parse((ROOT / "scripts" / "e03_grade_parsers.py").read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(m.startswith("parsers") or m.startswith("pptx") or m.startswith("docx") or "pdf" in m for m in mods), mods


def test_pptx_parser_does_not_derive_ids_from_shape_names(irs):
    for d in ("T-01", "T-02"):
        ir = irs[d]
        ids = [b["block_id"] for b in ir["blocks"]] + [t["table_id"] for t in ir["tables"]] + [t.get("logical_table_id") or "" for t in ir["tables"]]
        assert all(re.fullmatch(r"(b\d{4}|t\d{3}|)", x) for x in ids), ids


# ---- IR 형식 ----

def test_ir_schema_basics(irs):
    for d, ir in irs.items():
        assert ir["schema"] == "chungpamo.parse_ir" and ir["schema_version"] == "0.2"
        assert ir["document"]["source_file"] == DOCS[d]["file"] and ir["document"]["sha256"] == DOCS[d]["sha256"]
        assert ir["parser"]["mode"] == "direct" and ir["parser"]["api_calls"] == 0
        seq = ir["format_specific"]["reading_sequence"]
        assert len(seq) == len(set(seq)) == len(ir["blocks"]) + len(ir["tables"])
        assert all(seq[b["order"]] == b["block_id"] for b in ir["blocks"])
        for t in ir["tables"]:
            occupied = set()
            for c in t["cells"]:
                cells = {(c["row"] + i, c["col"] + j) for i in range(c["rowspan"]) for j in range(c["colspan"])}
                assert not (cells & occupied), (d, t["table_id"], c["row"], c["col"])
                occupied |= cells
            assert occupied == {(r, c) for r in range(1, t["n_rows"] + 1) for c in range(1, t["n_cols"] + 1)}, (d, t["table_id"])


def test_ir_has_no_local_paths(irs):
    text = json.dumps(irs, ensure_ascii=False)
    assert str(Path.home()) not in text and not re.search(r"[A-Za-z]:\\\\", text)


def test_parsers_are_deterministic():
    for d in PARSER_FOR:
        assert ir_digest(parse(d)) == ir_digest(parse(d)), d


# ---- 정상 결과 (측정값을 고정하지 않고 구조만 확인) ----

def test_docx_merges_and_parts(irs):
    t = irs["D-01"]["tables"][0]
    anchors = {(c["row"], c["col"]): (c["rowspan"], c["colspan"]) for c in t["cells"]}
    assert anchors[(1, 1)] == (2, 1) and anchors[(1, 2)] == (1, 2) and (2, 1) not in anchors
    assert {b["location"]["part"] for b in irs["D-01"]["blocks"]} == {"header", "body"}
    assert {b["location"]["part"] for b in irs["D-02"]["blocks"]} == {"body", "footer"}


def test_pptx_group_notes_and_link(irs):
    ir = irs["T-01"]
    grouped = [b for b in ir["blocks"] if len(b["location"].get("nested_path", [])) > 1]
    assert grouped and grouped[0]["location"]["nested_path"][0].startswith("grp")
    assert [b["type"] for b in ir["blocks"]].count("speaker_notes") == 1
    linked = [t for t in ir["tables"] if t.get("continuation")]
    assert len(linked) == 2 and linked[1]["repeated_header_rows"] == [1, 2] and linked[1]["continuation"]["detection"] == "inferred"


def test_link_rule_does_not_join_distinct_tables_with_same_header(irs):
    # T-02: 표 1·2가 같은 헤더로 연속 슬라이드에 있지만 표 2 앞에 캡션이 있어 서로 다른 표 → 연결하면 안 됨
    assert all(t.get("continuation") is None for t in irs["T-02"]["tables"])


# ---- 채점기 음성 대조 ----

def test_zero_denominator_is_not_measured(irs, truth):
    r = g(irs["D-01"], "D-01", truth)
    assert r["values"]["money"]["status"] == "NOT_MEASURED" and r["linkage"]["recall"]["status"] == "NOT_MEASURED"


def test_missing_ir_is_not_measured_not_fail(truth):
    r = G.grade(None, DOCS["P-01"], *truth)
    assert r["status"] == "NOT_MEASURED"


def test_negative_cell_text_and_value(irs, truth):
    base = g(irs["D-02"], "D-02", truth)
    ir = copy.deepcopy(irs["D-02"])
    cell = next(c for c in ir["tables"][0]["cells"] if c["row"] == 3 and c["col"] == 5)   # 첫 주문 납기
    cell["text"] = "2026-11-21"
    r = g(ir, "D-02", truth)
    assert r["cells"]["text"]["numerator"] == base["cells"]["text"]["numerator"] - 1
    assert r["values"]["date"]["numerator"] == base["values"]["date"]["numerator"] - 1


def test_negative_merge_span(irs, truth):
    ir = copy.deepcopy(irs["D-01"])
    c = next(c for c in ir["tables"][0]["cells"] if (c["row"], c["col"]) == (1, 2))
    c["colspan"] = 1
    r = g(ir, "D-01", truth)
    assert r["cells"]["merge_spans"]["numerator"] == r["cells"]["merge_spans"]["denominator"] - 1


def test_negative_missing_and_extra_table(irs, truth):
    ir = copy.deepcopy(irs["D-02"])
    removed = ir["tables"].pop(1)
    ir["format_specific"]["reading_sequence"].remove(removed["table_id"])
    r = g(ir, "D-02", truth)
    assert r["table_detection"]["recall"]["numerator"] == 1 and r["cells"]["text"]["numerator"] < r["cells"]["text"]["denominator"]
    ir2 = copy.deepcopy(irs["D-02"])
    extra = copy.deepcopy(ir2["tables"][0])
    extra.update({"table_id": "t999", "location": {**extra["location"], "table_index": 9}})
    ir2["tables"].append(extra)
    ir2["format_specific"]["reading_sequence"].append("t999")
    r2 = g(ir2, "D-02", truth)
    assert r2["table_detection"]["precision"]["numerator"] == 2 and r2["table_detection"]["precision"]["denominator"] == 3


def test_negative_reading_order(irs, truth):
    ir = copy.deepcopy(irs["D-02"])
    seq = ir["format_specific"]["reading_sequence"]
    b1, b2 = (b["block_id"] for b in ir["blocks"] if b["location"].get("body_index") in (0, 1))
    i, j = seq.index(b1), seq.index(b2)
    seq[i], seq[j] = seq[j], seq[i]
    r = g(ir, "D-02", truth)
    assert not r["reading_order"]["exact_sequence"] and r["reading_order"]["pairwise_order"]["numerator"] < r["reading_order"]["pairwise_order"]["denominator"]


def test_negative_location(irs, truth):
    ir = copy.deepcopy(irs["T-02"])
    b = next(b for b in ir["blocks"] if b["location"]["slide_index"] == 1)
    b["location"]["shape_id"] = 99
    r = g(ir, "T-02", truth)
    assert r["text"]["block"]["fine_location"]["numerator"] == r["text"]["block"]["fine_location"]["denominator"] - 1
    assert r["text"]["block"]["exact"]["numerator"] == r["text"]["block"]["exact"]["denominator"]   # 텍스트는 그대로 맞음


def test_negative_linkage(irs, truth):
    ir = copy.deepcopy(irs["T-01"])
    for t in ir["tables"]:
        t["continuation"] = None
    assert g(ir, "T-01", truth)["linkage"]["recall"]["numerator"] == 0
    ir2 = copy.deepcopy(irs["T-02"])
    ir2["tables"][0]["continuation"] = {"continues_to": ir2["tables"][1]["table_id"]}
    assert g(ir2, "T-02", truth)["linkage"]["false_links"] == 1


# ---- PDF (로컬 전용 문서 필요) ----

@needs_pdf
def test_pdfplumber_tables_and_link(truth):
    ir = parse("P-02", "pdfplumber")
    assert [t["location"]["page"] for t in ir["tables"]] == [1, 2, 3]
    assert ir["tables"][0]["continuation"]["continues_to"] == ir["tables"][1]["table_id"]
    assert all("bbox" in b["location"] for b in ir["blocks"])


@needs_pdf
def test_pypdf_reports_unsupported_tables_and_bbox(truth):
    ir = parse("P-01", "pypdf")
    assert ir["tables"] == [] and sum(d["code"] == "EXT-UNSUPPORTED" for d in ir["diagnostics"]) >= 2
    r = G.grade(ir, DOCS["P-01"], *truth)
    assert r["table_detection"]["recall"]["numerator"] == 0 and r["table_detection"]["precision"]["status"] == "NOT_MEASURED"
    assert r["text"]["block"]["fine_location"]["numerator"] == 0


@needs_pdf
def test_negative_pdf_block_bbox(truth):
    ir = parse("P-01", "pdfplumber")
    base = G.grade(ir, DOCS["P-01"], *truth)["text"]["block"]["fine_location"]["numerator"]
    b = next(b for b in ir["blocks"] if b["text"].startswith("FG001"))
    b["location"]["bbox"] = [x + 300 for x in b["location"]["bbox"]]
    assert G.grade(ir, DOCS["P-01"], *truth)["text"]["block"]["fine_location"]["numerator"] == base - 1
