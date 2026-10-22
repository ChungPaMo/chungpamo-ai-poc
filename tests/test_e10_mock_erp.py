"""E10 모의 ERP 테스트: DB 안전장치(FK·트리거), 왕복 동일성, 승인·반려·롤백·중복, 평가셋 독립성. 알려진 결함은 xfail(strict)로 남긴다."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

import e05_dataset as D
import e10_mock_erp as M

ROOT = Path(__file__).resolve().parents[1]
GT = D.load_gt()
SPEC = json.loads((ROOT / "data" / "canonical" / "e10" / "eval_set_v1.json").read_text(encoding="utf-8"))


def fresh():
    erp = M.MockERP()
    erp.bootstrap(GT)
    return erp


def batch_of(bid):
    return next(st["stage"] for s in SPEC["scenarios"] for st in s["steps"] if "stage" in st and st["stage"]["batch_id"] == bid)


def test_eval_set_hash_and_independence():
    man = json.loads((ROOT / "data" / "canonical" / "e10" / "manifest_v1.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((ROOT / "data" / "canonical" / "e10" / "eval_set_v1.json").read_bytes()).hexdigest() == man["eval_set_sha256"]
    assert "import e10_mock_erp" not in (ROOT / "scripts" / "e10_build_eval_set.py").read_text(encoding="utf-8")
    src = (ROOT / "scripts" / "e10_mock_erp.py").read_text(encoding="utf-8")
    assert "eval_set_v1" not in src and '"truth"' not in src


def test_foreign_keys_on_and_snapshot_equals_ground_truth():
    erp = fresh()
    assert erp.fk_on and erp.q("PRAGMA foreign_keys")[0][0] == 1
    assert D.dataset_sha256(erp.snapshot(GT)) == D.dataset_sha256(GT["entities"])


def test_db_blocks_unapproved_and_delete():
    erp = fresh()
    row = {c: None for c in erp.cols["SalesOrder"]} | {"record_uid": "rec_ffffffffffffffff", "order_id": "O999", "product_id": "FG001", "order_qty": "1",
                                                       "unit": "EA", "order_date": "2026-11-01", "due_date": "2026-11-02", "priority": "NORMAL", "status": "OPEN"}
    assert erp.raw_insert_attempt("SalesOrder", row, "NO-SUCH-APPROVAL")["blocked"]
    with pytest.raises(sqlite3.DatabaseError):
        erp.con.execute("DELETE FROM SalesOrder WHERE order_id = 'O001'")
    with pytest.raises(sqlite3.DatabaseError):
        erp.con.execute("UPDATE SalesOrder SET order_qty = '1' WHERE order_id = 'O001'")     # 기존 승인 재사용 UPDATE (v0.2 수정 전에는 통과했음)
    used = erp.q("SELECT approved_by FROM SalesOrder WHERE order_id = 'O002'")[0][0]
    with pytest.raises(sqlite3.DatabaseError):                                            # 다른 레코드에 이미 쓰인 승인으로 새 행 쓰기
        erp.con.execute("INSERT INTO SalesOrder (record_uid, order_id, product_id, order_qty, unit, order_date, due_date, priority, status, approved_by) "
                        "VALUES ('rec_eeeeeeeeeeeeeeee', 'O998', 'FG001', '1', 'EA', '2026-11-01', '2026-11-02', 'NORMAL', 'OPEN', ?)", (used,))


def test_exact_code_auto_commit_and_reimport_no_duplicate():
    erp = fresh()
    r = erp.stage_batch(GT, batch_of("B-M01"))
    assert len(r["auto_committed"]) == 1 and erp.current("SalesOrder", {"order_id": "O021"})["product_id"] == "FG001"
    again = {**batch_of("B-M01"), "batch_id": "B-M11"}
    r2 = erp.stage_batch(GT, again)
    assert r2["staged"] == [] and r2["duplicates"][0]["kind"] == "REIMPORT_SAME_SOURCE"
    assert erp.stage_batch(GT, batch_of("B-M01"))["reused"]
    assert erp.q("SELECT COUNT(*) FROM SalesOrder WHERE order_id = 'O021'")[0][0] == 1


@pytest.mark.parametrize("bid,rule", [("B-M04", "R01"), ("B-M05", "B08"), ("B-M06", "S06"), ("B-M09", "B02"), ("B-M10", "R02"), ("B-X07", "M-20"), ("B-M03", "M-21")])
def test_blocking_issues_cannot_be_approved(bid, rule):
    erp = fresh()
    r = erp.stage_batch(GT, batch_of(bid))
    issues = {i["rule_id"] for d in r["diff"] if "issues" in d for i in d["issues"]}
    assert rule in issues
    for sid in r["staged"]:
        if erp.q("SELECT blocking_issue_count FROM StagingRecord WHERE staging_id = ?", sid)[0][0]:
            assert erp.approve(sid, "REVIEWER_A")["reason"] == "BLOCKING_ISSUES"
            with pytest.raises(sqlite3.DatabaseError):     # 애플리케이션을 우회해도 DB 트리거가 막음
                erp.con.execute("UPDATE ApprovalLog SET approval_status = 'APPROVED', reviewer = 'REVIEWER_A', approved_at = 'x' WHERE staging_id = ?", (sid,))


def test_reviewer_duplicate_approval_stale_source_and_rollback():
    erp = fresh()
    r = erp.stage_batch(GT, batch_of("B-X03"))
    sid = r["staged"][0]
    assert erp.approve(sid, "REVIEWER_X")["reason"] == "BAD_REVIEWER"
    assert erp.approve(sid, "REVIEWER_OLD")["reason"] == "BAD_REVIEWER"
    with pytest.raises(sqlite3.IntegrityError):
        erp.con.execute("UPDATE ApprovalLog SET reviewer = 'REVIEWER_X' WHERE staging_id = ?", (sid,))
    assert erp.approve(sid, "REVIEWER_A", current_source_sha="other")["reason"] == "STALE_SOURCE"
    before = erp.counts()
    assert erp.approve(sid, "REVIEWER_A", fail_after_write=True)["reason"] == "ROLLED_BACK"
    assert erp.counts() == before and erp.q("SELECT approval_status FROM ApprovalLog WHERE staging_id = ?", sid)[0][0] == "PENDING"
    assert erp.approve(sid, "REVIEWER_A")["ok"]
    assert erp.approve(sid, "REVIEWER_B")["reason"] == "ALREADY_DECIDED"
    with pytest.raises(sqlite3.DatabaseError):
        erp.con.execute("UPDATE ApprovalLog SET approval_status = 'REJECTED' WHERE staging_id = ?", (sid,))
    assert erp.q("SELECT COUNT(*) FROM ChangeHistory WHERE approval_id = ?", f"APR-{sid}")[0][0] == 1


def test_dry_run_writes_no_staging():
    erp = fresh()
    r = erp.stage_batch(GT, batch_of("B-DRY"))
    assert r["staged"] == [] and [d["operation"] for d in r["diff"]] == ["INSERT"] and erp.current("SalesOrder", {"order_id": "O031"}) is None


def test_update_keeps_history_before_after():
    erp = fresh()
    erp.stage_batch(GT, batch_of("B-M01"))
    r = erp.stage_batch(GT, batch_of("B-X02"))
    sid = r["staged"][0]
    assert erp.approve(sid, "REVIEWER_A", batch_of("B-X02")["source_sha256"])["ok"]
    hist = erp.q("SELECT operation, before_json, after_json FROM ChangeHistory WHERE target_entity = 'SalesOrder' AND target_key = ?", json.dumps({"order_id": "O021"}))
    assert [h[0] for h in hist] == ["INSERT", "UPDATE"] and json.loads(hist[1][1])["order_qty"] == "50" and json.loads(hist[1][2])["order_qty"] == "60"


@pytest.mark.xfail(strict=True, reason="v1 매퍼 기준선 결함(E10 보고서 D-1, v2에서 수정): 같은 행의 코드(FG002)와 품명(FG001)이 충돌해도 코드 후보가 품명 후보를 덮어쓰고 자동 승인됨")
def test_conflicting_code_and_name_requires_review():
    erp = fresh()
    r = erp.stage_batch(GT, batch_of("B-M13"))
    assert r["auto_committed"] == [] and erp.current("SalesOrder", {"order_id": "O032"}) is None


CONFLICT = json.loads((ROOT / "data" / "canonical" / "e10" / "conflict_set_v1.json").read_text(encoding="utf-8"))


def conflict_batch(bid):
    return next(st["stage"] for s in CONFLICT["scenarios"] for st in s["steps"] if "stage" in st and st["stage"]["batch_id"] == bid)


def fresh_v2(auto=None):
    erp = M.MockERP(mapper="v2", auto_policy=auto)
    erp.bootstrap(GT)
    return erp


@pytest.mark.parametrize("auto", [None, "experimental"])
def test_v2_code_name_conflict_blocked(auto):
    erp = fresh_v2(auto)
    for bid, key in (("B-M13", "O032"), ("B-C01", "O040")):
        src = batch_of(bid) if bid.startswith("B-M") else conflict_batch(bid)
        r = erp.stage_batch(GT, src)
        assert any(i["rule_id"] == "M-24" for d in r["diff"] if "issues" in d for i in d["issues"])
        assert r["auto_committed"] == [] and erp.current("SalesOrder", {"order_id": key}) is None
        assert erp.approve(r["staged"][0], "REVIEWER_A")["reason"] == "BLOCKING_ISSUES"


def test_v2_default_policy_never_auto_approves_and_agreeing_name_is_not_conflict():
    erp = fresh_v2()
    r = erp.stage_batch(GT, batch_of("B-M01"))
    assert r["auto_committed"] == [] and erp.q("SELECT review_required FROM StagingRecord WHERE staging_id = ?", r["staged"][0])[0][0] == 1
    r2 = erp.stage_batch(GT, conflict_batch("B-C02"))
    assert not any(i["rule_id"] == "M-24" for d in r2["diff"] if "issues" in d for i in d["issues"])


def test_v2_reimport_while_pending_is_duplicate():
    erp = fresh_v2()
    erp.stage_batch(GT, batch_of("B-M01"))
    r = erp.stage_batch(GT, {**batch_of("B-M01"), "batch_id": "B-M11"})
    assert r["staged"] == [] and r["duplicates"][0]["kind"] == "REIMPORT_SAME_SOURCE"


def test_v2_inactive_bom_line_flagged():
    erp = fresh_v2("experimental")
    r = erp.stage_batch(GT, conflict_batch("B-C04"))
    assert any(i["rule_id"] == "M-25" for d in r["diff"] if "issues" in d for i in d["issues"]) and r["auto_committed"] == []
