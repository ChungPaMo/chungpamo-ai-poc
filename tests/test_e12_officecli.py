"""E12 OfficeCLI 비교 테스트 — 변환 규칙(정상 + 음성 대조), 정답 생성 재현, 결과 파일 일관성, 공개 파일 누출, 실제 OfficeCLI 실행.

OfficeCLI 실행 파일은 저장소 밖(사용자 로컬 도구 폴더)에 있다 → 없으면 실행 필요 테스트는 사유와 함께 건너뛴다 (통과로 세지 않음).
외부 문서(data/raw)가 없는 새 클론에서는 외부 문서 테스트도 건너뛴다.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

import e12_make_xlsx as MX
import e12_officecli as O

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "E12_officecli"
TRUTH = json.loads((ROOT / "data" / "canonical" / "e12" / "xlsx_truth_v1.json").read_text(encoding="utf-8"))
EXE_OK = O.EXE.exists() and O.sha(O.EXE) == O.EXE_SHA256
needs_exe = pytest.mark.skipif(not EXE_OK, reason="OfficeCLI v1.0.157 실행 파일 없음 또는 해시 불일치 (저장소 밖 로컬 도구)")
needs_results = pytest.mark.skipif(not (OUT / "results.json").exists(), reason="E12 결과 없음 (scripts/e12_run.py 미실행)")
EXT_TRUTH = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"


def tc(path, text="", **fmt):
    return {"type": "tc", "path": path, "text": text, "format": fmt, "children": []}


# ---- 변환 규칙 (실행 파일 불필요) ----

def test_grid_pptx_covered_cells_take_one_column():
    """PPTX: 덮인 셀(hmerge/vmerge)도 tc로 남는다 → tc 하나 = 1열. (첫 구현의 버그: 앵커 뒤 colspan만큼 건너뜀 → 열 수 8)"""
    rows = [{"children": [tc("a", "No", rowspan=2), tc("b", "Comp", colspan=2), tc("c", hmerge=True), tc("d", "Qty", colspan=2), tc("e", hmerge=True), tc("f", "Loss", rowspan=2)]},
            {"children": [tc("g", vmerge=True), tc("h", "Code"), tc("i", "Name"), tc("j", "Q"), tc("k", "U"), tc("l", vmerge=True)]}]
    cells, nr, nc = O._grid(rows, mode="pptx")
    assert (nr, nc) == (2, 6)
    got = {(c["row"], c["col"]): (c["rowspan"], c["colspan"], c["text"]) for c in cells}
    assert got[(1, 1)] == (2, 1, "No") and got[(1, 2)] == (1, 2, "Comp") and got[(1, 4)] == (1, 2, "Qty") and got[(1, 6)] == (2, 1, "Loss")
    assert (2, 1) not in got and (2, 6) not in got and got[(2, 2)][2] == "Code"


def test_grid_docx_vmerge_continue_extends_anchor():
    rows = [{"children": [{"type": "cell", "path": "p1", "text": "A", "format": {"vmerge": "restart"}, "children": []},
                          {"type": "cell", "path": "p2", "text": "B", "format": {"colspan": 2}, "children": []}]},
            {"children": [{"type": "cell", "path": "p3", "text": "", "format": {"vmerge": "continue"}, "children": []},
                          {"type": "cell", "path": "p4", "text": "x", "format": {}, "children": []}, {"type": "cell", "path": "p5", "text": "y", "format": {}, "children": []}]}]
    cells, nr, nc = O._grid(rows, mode="docx")
    got = {(c["row"], c["col"]): (c["rowspan"], c["colspan"]) for c in cells}
    assert (nr, nc) == (2, 3) and got[(1, 1)] == (2, 1) and got[(1, 2)] == (1, 2) and (2, 1) not in got
    # 음성 대조: continue 표시를 지우면 세로 병합이 사라져야 한다
    rows2 = copy.deepcopy(rows)
    rows2[1]["children"][0]["format"] = {}
    got2 = {(c["row"], c["col"]): c["rowspan"] for c in O._grid(rows2, mode="docx")[0]}
    assert got2[(1, 1)] == 1 and (2, 1) in got2


def test_multi_paragraph_cell_keeps_line_breaks():
    cell = {"type": "cell", "path": "p", "text": "ab", "format": {}, "children": [{"type": "paragraph", "text": "a"}, {"type": "paragraph", "text": "b"}]}
    assert O._grid([{"children": [cell]}], mode="docx")[0][0]["text"] == "a\nb"


def test_batch_rejects_non_read_commands(tmp_path):
    f = tmp_path / "x.docx"
    f.write_bytes(b"x")
    with pytest.raises(AssertionError):
        O.batch(f, [{"command": "set", "path": "/body/p[1]", "props": {"text": "x"}}])


def test_batch_reads_inline_and_file_results(monkeypatch, tmp_path):
    """결과가 작으면 stdout(data.results)에, 크면 outputFile에 담긴다 — 둘 다 받아야 한다 (첫 구현은 파일만 받아 4개 문서 내용이 비었음)."""
    src = tmp_path / "x.pptx"
    src.write_bytes(b"x")
    inline = {"index": 0, "success": True, "output": {"results": [{"path": "/slide[1]"}]}}
    monkeypatch.setattr(O, "run", lambda *a, **k: {"data": {"success": True, "data": {"results": [inline]}}, "returncode": 0})
    r = O.batch(src, [{"command": "get", "path": "/slide[1]"}])
    assert r["batch_output"] == "inline" and r["outputs"][0]["results"][0]["path"] == "/slide[1]" and r.get("ok", True)
    of = tmp_path / "out.json"
    of.write_text(json.dumps({"results": [inline]}), encoding="utf-8")
    monkeypatch.setattr(O, "run", lambda *a, **k: {"data": {"success": True, "data": {"outputFile": str(of)}}, "returncode": 0})
    r = O.batch(src, [{"command": "get", "path": "/slide[1]"}])
    assert r["batch_output"] == "file" and r["outputs"][0]["results"] and not of.exists()
    # 음성 대조: 명령 수와 결과 수가 다르면 실패로 표시
    monkeypatch.setattr(O, "run", lambda *a, **k: {"data": {"success": True, "data": {"results": []}}, "returncode": 0})
    assert O.batch(src, [{"command": "get", "path": "/slide[1]"}])["ok"] is False


def test_update_check_disabled_in_env():
    assert O.ENV.get("OFFICECLI_SKIP_UPDATE") == "1"


# ---- 정답 생성 재현 ----

def test_xlsx_truth_generator_is_deterministic(tmp_path):
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    MX.build(a, True)
    MX.build(b, False)
    assert hashlib.sha256(a.read_bytes()).hexdigest() == TRUTH["sha256"]
    assert hashlib.sha256(b.read_bytes()).hexdigest() == TRUTH["variant_no_formula_cache"]["sha256"]
    assert O.sha(ROOT / TRUTH["file"]) == TRUTH["sha256"]


def test_xlsx_truth_contents():
    kinds = {c["note"] for c in TRUTH["cells"] if c["note"]}
    assert {"number_stored_as_text", "invalid_number", "blank", "formula_error"} <= kinds
    assert len(TRUTH["merges"]) == 4 and TRUTH["hidden_rows"] and TRUTH["hidden_cols"]
    assert TRUTH["status"].startswith("GENERATED")


# ---- 결과 파일 일관성 ----

@needs_results
def test_results_consistency():
    r = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    meta = json.loads((OUT / "run_meta.json").read_text(encoding="utf-8"))
    assert r["pdf"]["status"] == "NOT_SUPPORTED"
    assert meta["inputs_unchanged_after_run"] is True and meta["officecli"]["sha256"] == O.EXE_SHA256
    for d in r["synthetic"] + r["external"]:
        assert d["officecli_run"]["source_unchanged"] is True
        assert d["baseline_v2"] and d["officecli"], f"{d['doc_id']} 지표가 비어 있음 (채점 결과 평탄화 실패)"
    for d in r["external"]:
        assert d["truth"].startswith("PROVISIONAL")
    for p in r["perf"]:
        assert p["officecli"]["cli_calls"] == 2


@needs_results
def test_summary_matches_results():
    import e12_summary  # noqa: F401  (집계 함수 재사용)
    r = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    s = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    ho = [d for d in r["external"] if d["split"] == "holdout"]
    assert s["external"]["holdout"] == {**s["external"]["holdout"], **e12_summary.agg(ho, e12_summary.EXT_KEYS)}
    assert s["xlsx"]["X12-02_no_formula_cache"]["openpyxl"] == r["xlsx"]["X12-02_no_formula_cache"]["openpyxl"]["metrics"]


@needs_results
def test_examples_are_real_runs():
    e = json.loads((OUT / "examples.json").read_text(encoding="utf-8"))
    assert all(len(e[f]) >= 3 for f in ("xlsx", "docx", "pptx"))

    def calls(x):
        if isinstance(x, dict):
            if "returncode" in x and "command" in x:
                yield x
            for v in x.values():
                yield from calls(v)
        elif isinstance(x, list):
            for v in x:
                yield from calls(v)
    cs = list(calls(e))
    assert cs and all(c["returncode"] == 0 for c in cs)
    assert all(c["source_unchanged"] for c in cs if "source_unchanged" in c)
    assert all(x["original"] and x["baseline"] and x["conclusion"] for f in ("xlsx", "docx", "pptx") for x in e[f])


@needs_results
def test_public_results_have_no_private_text():
    """D-025: 공개 결과에 외부 문서 본문·홈 경로·사용자 이름이 없어야 한다."""
    blob = "\n".join(p.read_text(encoding="utf-8") for p in OUT.rglob("*.json"))
    assert not re.search(r"[A-Za-z]:\\\\Users\\\\|/Users/|AppData", blob)
    if EXT_TRUTH.exists():
        texts = [b["text"] for d in json.loads(EXT_TRUTH.read_text(encoding="utf-8"))["documents"] for b in (d.get("truth") or {}).get("blocks", []) if len(b["text"]) >= 40]
        leaked = [t[:40] for t in texts if t in blob]
        assert not leaked, leaked


# ---- 실제 OfficeCLI 실행 ----

@needs_exe
def test_officecli_xlsx_extract_and_source_untouched():
    x = ROOT / TRUTH["file"]
    h = O.sha(x)
    ex = O.extract(x)
    cells = O.xlsx_cells(ex)
    assert O.sha(x) == h and all(c["source_unchanged"] for c in ex["calls"])
    assert {(m["sheet"], m["range"]) for m in TRUTH["merges"]} == cells["merges"]
    assert ("Orders", 5) in cells["hidden_rows"] and ("Orders", "I") in cells["hidden_cols"]
    assert cells["cells"][("Orders", "C3")]["type"] == "SharedString"


@needs_exe
def test_officecli_computes_formula_without_cache():
    nc = ROOT / TRUTH["variant_no_formula_cache"]["file"]
    c = O.xlsx_cells(O.extract(nc))["cells"][("Orders", "F2")]
    assert c["cached"] == "0" and c["computed"] == "6000000"


@needs_exe
def test_officecli_rejects_pdf(tmp_path):
    pdfs = sorted((ROOT / "data").rglob("*.pdf"))
    if not pdfs:
        pytest.skip("PDF 입력 없음")
    r = O.run(["get", "{file}", "/", "--json"], pdfs[0])
    assert r["returncode"] != 0 or not r["data"].get("success")
