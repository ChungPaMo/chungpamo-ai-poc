"""E03 외부 문서 평가 도구 테스트: 정답 작성기·채점기 독립성, 분할 고정, 정답 해시 고정, 채점기 음성 대조.

외부 원본·정답 파일(Git 제외)이 없는 환경에서는 해당 테스트를 사유와 함께 건너뛴다 (통과로 세지 않음).
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

import pytest

import e03_grade_external as G

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"
MANIFEST = ROOT / "results" / "E03_document_parsers" / "external_truth_v1" / "truth_manifest.json"
SPLITS = json.loads((ROOT / "configs" / "e03_external_splits.json").read_text(encoding="utf-8"))
needs_truth = pytest.mark.skipif(not TRUTH.exists(), reason="외부 정답 파일 없음 (로컬 전용, D-025)")
EVALUATED = ("docx", "pptx", "pypdf", "pdfplumber", "pdfminer", "parsers")


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    return mods | {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}


@pytest.mark.parametrize("script", ["e03_build_external_truth.py", "e03_grade_external.py", "e03_external_inspect.py", "e03_external_truth_crosscheck.py"])
def test_truth_and_grading_tools_do_not_use_evaluated_parsers(script):
    mods = imports_of(ROOT / "scripts" / script)
    assert not any(m.split(".")[0] in EVALUATED for m in mods), (script, mods)


def test_splits_are_disjoint_and_fixed():
    b, d, h = (set(SPLITS[k]) for k in ("blind8", "dev", "holdout"))
    assert len(b) == 8 and not (b & d) and not (b & h) and not (d & h)


def test_parsers_do_not_hardcode_external_document_names():
    names = [s["file"] for s in json.loads((ROOT / "configs" / "e03_external_sources.json").read_text(encoding="utf-8"))["sources"]]
    for p in (ROOT / "src" / "parsers").rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert not any(n in text for n in names) and "PMC" not in text, p


@needs_truth
def test_parsers_do_not_hardcode_external_document_text():
    import e03_external_leak_scan as L
    strings = L.truth_strings(json.loads(TRUTH.read_text(encoding="utf-8")))
    for p in (ROOT / "src" / "parsers").rglob("*.py"):
        body = L.nows(p.read_text(encoding="utf-8"))
        assert not any(s in body for s in strings), p


@needs_truth
def test_truth_hash_is_frozen():
    assert hashlib.sha256(TRUTH.read_bytes()).hexdigest() == json.loads(MANIFEST.read_text(encoding="utf-8"))["truth_sha256"]


@needs_truth
def test_truth_status_vocabulary_and_no_manual_claim():
    t = json.loads(TRUTH.read_text(encoding="utf-8"))
    assert t["manual_review_performed"] is False
    text = json.dumps(t, ensure_ascii=False)
    assert "VERIFIED_MANUAL\"" not in text.replace('"VERIFIED_MANUAL",', "")   # 어휘 목록 외에는 쓰지 않음


# ---- 채점기 음성 대조 (합성 정답·출력) ----

def pdf_doc():
    cells = [{"row": 1, "col": 1, "rowspan": 1, "colspan": 2, "text": "Head", "bbox": [0, 0, 100, 10], "is_column_header": True, "is_projected_row_header": False, "status": "VERIFIED_OFFICIAL"},
             {"row": 2, "col": 1, "rowspan": 1, "colspan": 1, "text": "a 1", "bbox": [0, 10, 50, 20], "is_column_header": False, "is_projected_row_header": False, "status": "VERIFIED_OFFICIAL"},
             {"row": 2, "col": 2, "rowspan": 1, "colspan": 1, "text": "b", "bbox": [50, 10, 100, 20], "is_column_header": False, "is_projected_row_header": False, "status": "VERIFIED_OFFICIAL"}]
    return {"doc_id": "T", "format": "pdf", "items": {}, "truth": {"tables": [{"table_id": "t", "page": 1, "bbox": [0, 0, 100, 20], "n_rows": 2, "n_cols": 2, "cells": cells}]}}


def pdf_ir():
    cells = [{"row": 1, "col": 1, "rowspan": 1, "colspan": 2, "text": "Head", "is_header": None, "location": {"page": 1, "bbox": [0, 0, 100, 10]}},
             {"row": 2, "col": 1, "rowspan": 1, "colspan": 1, "text": "a\n1", "is_header": None, "location": {"page": 1, "bbox": [0, 10, 50, 20]}},
             {"row": 2, "col": 2, "rowspan": 1, "colspan": 1, "text": "b", "is_header": None, "location": {"page": 1, "bbox": [50, 10, 100, 20]}}]
    return {"parser": {"name": "x"}, "blocks": [], "diagnostics": [], "format_specific": {},
            "tables": [{"table_id": "t1", "n_rows": 2, "n_cols": 2, "location": {"page": 1, "bbox": [0, 0, 100, 20]}, "cells": cells}]}


def test_grader_pdf_perfect_and_negatives():
    m = G.grade(pdf_ir(), pdf_doc())["metrics"]
    assert m["cells"]["text_loose_grid"]["rate"] == 1.0 and m["cells"]["merge_spans"]["rate"] == 1.0 and m["table_detection"]["recall"]["rate"] == 1.0
    ir = pdf_ir()
    ir["tables"][0]["cells"][0]["colspan"] = 1
    m2 = G.grade(ir, pdf_doc())["metrics"]
    assert m2["cells"]["merge_spans"]["rate"] == 0.0
    ir = pdf_ir()
    ir["tables"][0]["location"]["bbox"] = [300, 300, 400, 320]
    m3 = G.grade(ir, pdf_doc())["metrics"]
    assert m3["table_detection"]["recall"]["rate"] == 0.0 and m3["cells"]["text_loose_grid"]["rate"] == 0.0
    ir = pdf_ir()
    ir["tables"][0]["cells"][2]["text"] = "c"
    assert G.grade(ir, pdf_doc())["metrics"]["cells"]["text_loose_grid"]["numerator"] == 2


def test_grader_false_merge_and_review_exclusion():
    ir = pdf_ir()
    ir["tables"][0]["cells"][1]["colspan"] = 2
    del ir["tables"][0]["cells"][2]
    assert G.grade(ir, pdf_doc())["metrics"]["cells"]["false_merges"] == 1
    d = pdf_doc()
    d["truth"]["tables"][0]["cells"][2]["status"] = "NEEDS_MANUAL_REVIEW"
    m = G.grade(pdf_ir(), d)["metrics"]["cells"]
    assert m["review_excluded_cells"] == 1 and m["text_loose_grid"]["denominator"] == 2


def test_grader_missing_output_is_failure_not_pass():
    assert G.grade(None, pdf_doc())["status"] == "PARSER_FAILED"
    assert G.grade(pdf_ir(), {"doc_id": "x", "truth": None})["status"] == "NOT_MEASURED"


def test_grader_reading_order_and_char_scores():
    r = G.pairwise(["a", "b", "c"], {"a": 0, "b": 2, "c": 1}, "PROVISIONAL")
    assert r["pairwise_order"]["numerator"] == 2 and r["pairwise_order"]["denominator"] == 3
    c = G.char_scores("abcdef", "abcxef", "PROVISIONAL")
    assert c["recall"]["numerator"] == 5 and c["precision"]["denominator"] == 6
    assert G.char_scores("", "x", "P")["recall"]["status"] == "NOT_MEASURED"


def test_runner_refuses_to_overwrite_existing_results(tmp_path, monkeypatch):
    import e03_run_external as R
    existing = ROOT / "results" / "E03_document_parsers" / "external_baseline_v1"
    if not existing.exists():
        pytest.skip("external_baseline_v1 없음 — 덮어쓰기 방지는 결과가 있을 때만 확인 가능")
    monkeypatch.setattr("sys.argv", ["x", "--version", "v1", "--set", "blind8", "--out", "external_baseline_v1"])
    with pytest.raises(SystemExit) as e:
        R.main()
    assert "덮어쓰지" in str(e.value)
