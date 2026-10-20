"""E03 1단계 문서 정답 명세 검증 (명세 생성 코드와 별도로 canonical v2와 대조)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data" / "canonical" / "e03_document_truth_v1.json"


@pytest.fixture(scope="module")
def truth():
    return json.loads(TRUTH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gt():
    return json.loads((ROOT / "data" / "canonical" / "ground_truth_v2.json").read_text(encoding="utf-8"))


def test_source_hash_is_canonical_v2(truth):
    import hashlib
    assert truth["source"]["sha256"] == hashlib.sha256((ROOT / "data/canonical/ground_truth_v2.json").read_bytes()).hexdigest()


def test_canonical_refs_match_values(truth, gt):
    by_uid = {r["record_uid"]: r for rows in gt["entities"].values() for r in rows}
    checked = 0
    for s in truth["content_sets"].values():
        for v in s["extracted_values"]:
            ref = v["canonical_ref"]
            if "expected_path" in ref:
                node = gt
                for k in ref["expected_path"].split("."):
                    node = node[k]
                assert Decimal(node) == Decimal(v["value"]), v
            elif v.get("derived_rule"):
                continue  # 문서용 파생값은 아래 테스트에서 별도 확인
            else:
                rec = by_uid[ref["record_uid"]]
                want = rec[ref["field"]]
                assert (Decimal(want) == Decimal(v["value"])) if v.get("unit") else (want == v["value"]), v
            checked += 1
    assert checked > 100


def test_derived_inventory_value(truth, gt):
    mat = {m["material_id"]: m for m in gt["entities"]["Material"]}
    t = next(t for t in truth["content_sets"]["CS2"]["tables"] if t["table_id"] == "CS2-T2")
    cell = {(c["row"], c["col"]): c["text"] for c in t["cells"]}
    # M003: 재고 200,000 g = 200 kg × 11,000원 = 2,200,000원
    row = next(r for (r, c), x in cell.items() if c == 2 and x == "M003")
    assert cell[(row, 4)] == "200,000" and cell[(row, 5)] == "g" and cell[(row, 7)] == "2,200,000"
    assert mat["M003"]["unit_cost"] == "11000"


def test_table_grids_and_merges(truth):
    for s in truth["content_sets"].values():
        for t in s["tables"]:
            covered = set()
            for m in t["merged_ranges"]:
                assert m["row"] + m["rowspan"] - 1 <= t["header_rows"] or m["rowspan"] == 1
                for r in range(m["row"], m["row"] + m["rowspan"]):
                    for c in range(m["col"], m["col"] + m["colspan"]):
                        assert (r, c) not in covered, (t["table_id"], r, c)
                        covered.add((r, c))
            anchors = {(c["row"], c["col"]) for c in t["cells"]}
            hidden = covered - {(m["row"], m["col"]) for m in t["merged_ranges"]}
            assert not anchors & hidden
            assert len(anchors) + len(hidden) == t["n_rows"] * t["n_cols"]


def test_documents_not_marked_verified(truth):
    for d in truth["documents"]:
        assert d["status"] == "NOT_GENERATED" and "미측정" in d["verification"]
    hwpx = next(d for d in truth["documents"] if d["format"] == "hwpx")
    assert "검증 완료로 처리하지 않음" in hwpx["method"]
    assert {d["format"] for d in truth["documents"]} == {"docx", "pdf_text", "pdf_scan", "pptx", "hwpx", "hwp"}
