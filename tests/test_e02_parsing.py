"""E02 CSV/Excel 파서 테스트 (표준 csv + openpyxl Baseline)."""

from __future__ import annotations

import ast
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from normalization.values import NormalizeError, parse_date, parse_number
from parsers.vendor_parser import load_config, parse_vendor

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config(ROOT / "configs" / "e02_vendor_mapping.json")


@pytest.fixture(scope="module")
def outs():
    return {ds: {v: parse_vendor(CFG, v, ROOT / "data", ds == "invalid") for v in ("A", "B")} for ds in ("clean", "invalid")}


def rec(out, entity, **match):
    hits = [r for r in out["entities"][entity] if all(r["values"].get(k) == v for k, v in match.items())]
    assert hits, (entity, match)
    return hits[0]


def test_parser_sources_do_not_reference_answers():
    for p in list((ROOT / "src" / "parsers").glob("*.py")) + list((ROOT / "src" / "normalization").glob("*.py")):
        text = p.read_text(encoding="utf-8")
        assert "ground_truth" not in text and "data/canonical" not in text and "vendor_id_map" not in text, p.name


def test_parser_runs_without_canonical_dir(outs):
    with tempfile.TemporaryDirectory(prefix="e02_nocanon_") as t:
        root = Path(t)
        for sub in ("vendor_a", "vendor_b", "invalid"):
            shutil.copytree(ROOT / "data" / sub, root / sub)
        assert not (root / "canonical").exists()
        for ds in ("clean", "invalid"):
            for v in ("A", "B"):
                assert parse_vendor(CFG, v, root, ds == "invalid") == outs[ds][v]


def test_grader_independent_of_parser():
    tree = ast.parse((ROOT / "scripts" / "e02_grade.py").read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(m.startswith(("parsers", "normalization")) for m in mods)


def test_encoding_detection(outs):
    enc = {(f["file"], f["sheet"]): f.get("encoding") for v in outs["clean"].values() for f in v["files"]}
    assert enc[("vendor_a/materials.csv", "")] == "utf-8-sig"
    assert enc[("vendor_a/orders.csv", "")] == "utf-8"
    assert enc[("vendor_b/vendor_b_orders.csv", "")] == "cp949"
    assert enc[("vendor_b/vendor_b_inventory.csv", "")] == "cp949"


def test_leading_zero_code_kept_and_mapped(outs):
    r = rec(outs["clean"]["A"], "Material", material_id="M005")
    assert r["source"]["cells"]["material_id"]["raw"] == "000105"
    x = [r for r in outs["clean"]["A"]["entities"]["Material"] if r["source"]["sheet"] == "Materials"]
    assert x[0]["source"]["cells"]["material_id"]["raw"].startswith("000")   # Excel 텍스트 셀에서도 선행 0 유지


def test_thousands_and_gram_conversion(outs):
    b = outs["clean"]["B"]
    inv = rec(b, "Inventory", item_type="MATERIAL", item_id="M003")
    assert inv["source"]["cells"]["on_hand_qty"]["raw"] == "200,000" and Decimal(inv["values"]["on_hand_qty"]) == 200   # g → kg
    line = rec(b, "BOMLine", bom_id="BOM-FG001-V2", line_no=2)
    assert line["source"]["cells"]["qty_per"]["raw"] == "1,000" and line["values"]["qty_per"] == "1" and line["values"]["unit"] == "kg"
    mat = rec(b, "Material", material_id="M001")
    assert mat["values"]["unit_cost"] == "1200" and mat["values"]["base_unit"] == "kg"           # 1.2원/g → 1200원/kg
    sl = rec(b, "BOMLine", bom_id="BOM-SF002-V1", line_no=2)
    assert sl["values"]["scrap_rate"] == "0.02"                                                   # 2% → 0.02


def test_merged_header_restored(outs):
    h = next(x for x in outs["clean"]["B"]["headers"] if x["sheet"] == "BOM")
    assert h["header_rows"] == 2
    groups = {c["name"]: c["group"] for c in h["header"]}
    assert groups["BOM번호"] == "BOM 정보" and groups["시작일"] == "유효조건" and groups["손실률(%)"] == "구성"


def test_clean_inputs_have_no_error_reports(outs):
    errs = [d for o in outs["clean"].values() for d in o["diagnostics"] if d["severity"] == "error"]
    assert errs == []


def test_invalid_inputs_parser_scope_detections(outs):
    got = {(d["file"], d["sheet"], d["row"], d["column"], d["error_code"])
           for o in outs["invalid"].values() for d in o["diagnostics"] if d["severity"] == "error"}
    inj = json.loads((ROOT / "data" / "canonical" / "injected_errors_v1.json").read_text(encoding="utf-8"))["errors"]
    e05 = {"E01-ERR-009", "E01-ERR-010", "E01-ERR-011", "E01-ERR-012"}
    missing = [e["error_id"] for e in inj if e["error_id"] not in e05
               and (e["file"], e["sheet"], e["row_number"], e["field"], e["error_code"]) not in got]
    assert missing == [], missing


def test_value_parsers():
    assert parse_number("1,500.5", "thousands") == Decimal("1500.5")
    with pytest.raises(NormalizeError) as e:
        parse_number("8OO,000", "thousands")
    assert e.value.error_code == "ERR-NUMFMT"
    with pytest.raises(NormalizeError) as e:
        parse_number("1,500", "plain")
    assert e.value.error_code == "ERR-NUMFMT"
    with pytest.raises(NormalizeError) as e:
        parse_date("2026-02-30", "%Y-%m-%d")
    assert e.value.error_code == "ERR-DATE"
    assert parse_date("2026.11.20", "%Y.%m.%d").isoformat() == "2026-11-20"


def test_results_recorded_with_three_repeats():
    import csv
    m = ROOT / "results" / "E02_tabular_parsing" / "metrics.csv"
    if not m.exists():
        pytest.skip("e02_run.py 실행 전")
    rows = list(csv.DictReader(m.open(encoding="utf-8")))
    assert rows and all(r["repeats"] == "3" for r in rows)
    assert all(r["time_median_s"] != "측정실패" for r in rows)
