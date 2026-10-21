"""E05 데이터 정합성 검증 테스트: 평가셋 무결성, 검증기와 정답 분리, 정상 데이터 무오탐, 단일 주입 검출, SQLite 설정·날짜 동작, 채점기 음성 대조."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

import e05_dataset as D
import e05_score as SC
import e05_validate_python as PY
import e05_validate_sql as SQ

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = D.EVAL_DIR / "eval_set_v1.json"
SPEC = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
MANIFEST = json.loads((D.EVAL_DIR / "manifest_v1.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "configs" / "e05_validation_rules.json").read_text(encoding="utf-8"))
GT = D.load_gt()
SINGLES = [d for d in SPEC["datasets"] if d["kind"] == "single"]
PASSES = [d for d in SPEC["datasets"] if d["kind"] == "pass"]


def ents_of(ds):
    return D.apply_ops(GT["entities"], ds["ops"], ds["dataset_id"])[0]


def non_info(reports):
    return [r for r in reports if r["severity"] != "INFO"]


def test_validators_do_not_read_truth():
    for f in ("e05_validate_python.py", "e05_validate_sql.py"):
        text = (ROOT / "scripts" / f).read_text(encoding="utf-8")
        assert "eval_set_v1" not in text and '"truth"' not in text and "injected_errors" not in text and "manifest_v1" not in text, f
    assert '"truth"' not in (ROOT / "scripts" / "e05_dataset.py").read_text(encoding="utf-8")   # 평가셋 연산(ops)만 적용, 정답은 읽지 않음


def test_eval_set_hash_and_independent_verification():
    assert hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest() == MANIFEST["eval_set_sha256"]
    ver = json.loads((D.EVAL_DIR / "verification_v1.json").read_text(encoding="utf-8"))
    assert len(ver) == len(SPEC["datasets"]) and all(v["ok"] for v in ver)
    mds = {d["dataset_id"]: d["dataset_sha256"] for d in MANIFEST["datasets"]}
    for ds in SPEC["datasets"]:
        assert D.dataset_sha256(ents_of(ds)) == mds[ds["dataset_id"]], ds["dataset_id"]


def test_catalog_metadata_and_synthetic_flags():
    ids = [r["rule_id"] for r in CATALOG["rules"]]
    assert len(ids) == len(set(ids))
    need = {"rule_id", "target", "description", "error_code", "severity", "method", "input_fields", "expected_result", "basis", "synthetic_assumption", "shacl_fit"}
    for r in CATALOG["rules"]:
        assert need <= set(r), r["rule_id"]
        if r["synthetic_assumption"]:
            assert "합성 가정" in r["basis"] and r["severity"] != "ERROR", r["rule_id"]


@pytest.mark.parametrize("mode", ["full", "pydantic_only"])
def test_clean_python_no_error_or_warning(mode):
    assert non_info(PY.validate(GT["entities"], GT["parameters"], "clean", mode)["reports"]) == []


def test_clean_sql_queries_and_constraints():
    assert non_info(SQ.run_queries(GT["entities"], GT["parameters"], "clean")["reports"]) == []
    c = SQ.run_constraints(GT["entities"], GT["parameters"], "clean")
    assert c["fk_enabled"] is True and c["rejected_rows"] == 0 and c["reports"] == []


def test_capacity_matches_ground_truth():
    for run in (PY.validate(GT["entities"], GT["parameters"], "clean"), SQ.run_queries(GT["entities"], GT["parameters"], "clean")):
        cap = SC.capacity_check(run["capacity"], GT["expected"])
        assert cap["rows_equal"] == cap["rows_compared"] and cap["excess_rows_output"] == cap["excess_rows_expected"] == 6


@pytest.mark.parametrize("ds", SINGLES, ids=[d["dataset_id"] for d in SINGLES])
def test_single_injection_detected_by_python_and_sql(ds):
    ents = ents_of(ds)
    for reports in (PY.validate(ents, GT["parameters"], ds["dataset_id"])["reports"], SQ.run_queries(ents, GT["parameters"], ds["dataset_id"])["reports"]):
        got = {(r["rule_id"], r["record_uid"]) for r in reports}
        for x in ds["truth"]["expected"]:
            for u in x["record_uids"]:
                assert (x["rule"], u) in got, (ds["dataset_id"], x["rule"], u)


@pytest.mark.parametrize("ds", PASSES, ids=[d["dataset_id"] for d in PASSES])
def test_boundary_pass_cases_have_no_error(ds):
    ents = ents_of(ds)
    assert [r for r in PY.validate(ents, GT["parameters"], ds["dataset_id"])["reports"] if r["severity"] == "ERROR"] == []
    assert [r for r in SQ.run_queries(ents, GT["parameters"], ds["dataset_id"])["reports"] if r["severity"] == "ERROR"] == []


def test_sqlite_foreign_keys_default_off_and_pragma_on():
    con = sqlite3.connect(":memory:")
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 0
    con.execute("PRAGMA foreign_keys = ON")
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    con.execute("CREATE TABLE p (id TEXT PRIMARY KEY)")
    con.execute("CREATE TABLE c (pid TEXT REFERENCES p(id))")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO c VALUES ('x')")


def test_sqlite_date_normalizes_invalid_day_so_equality_check_needed():
    con = sqlite3.connect(":memory:")
    assert con.execute("SELECT date('2026-02-30')").fetchone()[0] == "2026-03-02"
    assert con.execute("SELECT date('2026.12.01')").fetchone()[0] is None
    assert con.execute(f"SELECT {SQ.DATE_OK.format(c=chr(39) + '2026-02-30' + chr(39))}").fetchone()[0] == 0


def test_scorer_negative_and_positive_controls():
    ds = next(d for d in SINGLES if d["dataset_id"] == "I-V07")
    counts = {e: len(v) for e, v in ents_of(ds).items()}
    rules = {r["rule_id"] for r in CATALOG["rules"]}
    empty = SC.score_dataset(ds, [], counts, rules)["by_severity"]["ERROR"]
    assert empty["tp"] == 0 and empty["fn"] >= 1 and empty["fp"] == 0
    perfect = [{"rule_id": x["rule"], "record_uid": u, "field": x["field"], "severity": "ERROR"} for x in ds["truth"]["expected"] for u in x["record_uids"]]
    assert SC.score_dataset(ds, perfect, counts, rules)["by_severity"]["ERROR"]["fn"] == 0
    noise = SC.score_dataset(ds, [{"rule_id": "V07", "record_uid": "rec_0000000000000000", "field": "due_date", "severity": "ERROR"}], counts, rules)
    assert noise["by_severity"]["ERROR"]["fp"] == 1
