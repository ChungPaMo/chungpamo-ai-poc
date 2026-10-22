"""E10 실행: 평가셋 v1(해시 확인) → 승인자 정책 2종(ideal / rubber_stamp)으로 각각 새 모의 ERP에서 시나리오 실행 → 채점 → 결과 기록.

    .\\.venv\\Scripts\\python.exe scripts\\e10_run.py

결과: results/E10_erp_mapping/ (합성 데이터만). 외부 API·네트워크 사용 없음. 상태 RUNNING.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

import e05_dataset as D
import e10_mock_erp as M

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "data" / "canonical" / "e10" / "eval_set_v1.json"
MANIFEST = ROOT / "data" / "canonical" / "e10" / "manifest_v1.json"
OUT = ROOT / "results" / "E10_erp_mapping"
REPEATS = 3


SETS = {"eval": (SPEC, MANIFEST), "conflict": (ROOT / "data" / "canonical" / "e10" / "conflict_set_v1.json", ROOT / "data" / "canonical" / "e10" / "conflict_manifest_v1.json")}


def load_spec(which: str = "eval"):
    spec_p, man_p = SETS[which]
    man = json.loads(man_p.read_text(encoding="utf-8"))
    if hashlib.sha256(spec_p.read_bytes()).hexdigest() != man["eval_set_sha256"]:
        raise SystemExit("E10 평가셋 해시 불일치 → 중단")
    return json.loads(spec_p.read_text(encoding="utf-8")), man


def staging_of(erp, bid):
    return [r[0] for r in erp.q("SELECT staging_id FROM StagingRecord WHERE batch_id = ? ORDER BY staging_id", bid)]


def run_suite(policy: str, mapper: str = "v1", auto: str | None = None, which: str = "eval") -> dict:
    gt = D.load_gt()
    spec, _ = load_spec(which)
    erp = M.MockERP(mapper=mapper, auto_policy=auto)
    erp.bootstrap(gt)
    base_counts = erp.counts()
    truth_by_key = {}
    for s in spec["scenarios"]:      # ideal 승인자가 참조하는 정답 값: field_truth(행 단위)와 must_exist(최종 상태) 모두
        for row_ref, tbls in s["truth"].get("field_truth", {}).items():
            for table, vals in tbls.items():
                truth_by_key[(table, json.dumps({k: vals[k] for k in M.TABLES[table][1]}))] = vals
        for table, key, vals in s["truth"].get("must_exist", []):
            k = json.dumps({x: key[x] for x in M.TABLES[table][1]})
            truth_by_key[(table, k)] = {**truth_by_key.get((table, k), {}), **key, **vals}
    log = []
    for s in spec["scenarios"]:
        for st in s["steps"]:
            rec = {"scenario": s["id"], "step": next(iter(st))}
            if "stage" in st:
                r = erp.stage_batch(gt, st["stage"])
                rec.update({"batch_id": r["batch_id"], "reused": r["reused"], "staged": r["staged"], "auto_committed": r["auto_committed"], "duplicates": r["duplicates"],
                            "diff": [{k: d[k] for k in ("table", "key", "operation") if k in d} | ({"blocking": d["blocking"], "review_required": d["review_required"],
                                                                                                    "issues": [i["rule_id"] for i in d["issues"]]} if "blocking" in d else {})
                                     for d in r["diff"]]})
            elif "policy" in st:
                acts = []
                for sid in staging_of(erp, st["policy"]):
                    status, blocking = erp.q("SELECT a.approval_status, s.blocking_issue_count FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id "
                                             "WHERE a.staging_id = ?", sid)[0]
                    if status not in ("PENDING", "HOLD"):
                        continue
                    table, key, after = erp.q("SELECT target_entity, target_key, after_json FROM StagingRecord WHERE staging_id = ?", sid)[0]
                    issues = [x[0] for x in erp.q("SELECT i.rule_id FROM ValidationIssue i JOIN MappingCandidate c ON c.candidate_id = i.candidate_id "
                                                  "WHERE i.issue_id LIKE ?", f"ISS-{sid}-%")]
                    if policy == "rubber_stamp":
                        res = erp.approve(sid, "REVIEWER_A") if not blocking else {"ok": False, "reason": "BLOCKING_ISSUES"}
                        acts.append({"staging_id": sid, "action": "APPROVE" if res["ok"] else "LEFT_PENDING", "reason": res.get("reason")})
                        continue
                    want = truth_by_key.get((table, json.dumps({k: json.loads(key)[k] for k in M.TABLES[table][1]})))
                    after = json.loads(after)
                    ok_value = want is not None and all(v is None or str(after.get(k)) == str(v) for k, v in want.items()) and all(v is not None for v in want.values())
                    if blocking and "M-21" in issues:
                        erp.decide(sid, "REVIEWER_A", "HOLD", "모호한 품명 — 업체 확인 필요")
                        acts.append({"staging_id": sid, "action": "HOLD"})
                    elif blocking or not ok_value:
                        erp.decide(sid, "REVIEWER_A", "REJECTED", "검증 오류" if blocking else "정답과 다른 값")
                        acts.append({"staging_id": sid, "action": "REJECT"})
                    else:
                        res = erp.approve(sid, "REVIEWER_A")
                        acts.append({"staging_id": sid, "action": "APPROVE" if res["ok"] else "APPROVE_FAILED", "reason": res.get("reason")})
                rec["actions"] = acts
            elif "approve" in st:
                sid = staging_of(erp, st["approve"])[0]
                r = erp.approve(sid, st["reviewer"], st.get("current_source_sha"), st.get("fail_after_write", False))
                rec.update({"staging_id": sid, "result": r, "expected": st.get("expect", "OK"),
                            "as_expected": (r["ok"] and "expect" not in st) or (not r["ok"] and r.get("reason") == st.get("expect"))})
            elif "raw_insert_with_pending" in st:
                sid = staging_of(erp, st["raw_insert_with_pending"])[0]
                after = json.loads(erp.q("SELECT after_json FROM StagingRecord WHERE staging_id = ?", sid)[0][0])
                rec["result"] = erp.raw_insert_attempt("SalesOrder", after, f"APR-{sid}")
            elif "db_update_decided" in st:
                sid = staging_of(erp, st["db_update_decided"])[0]
                try:
                    erp.con.execute("UPDATE ApprovalLog SET approval_status = 'REJECTED', reviewer = 'REVIEWER_B' WHERE staging_id = ?", (sid,))
                    rec["result"] = {"blocked": False}
                except Exception as e:
                    rec["result"] = {"blocked": True, "error": str(e)}
            elif "db_set_reviewer" in st:
                sid = staging_of(erp, st["db_set_reviewer"])[0]
                try:
                    erp.con.execute("UPDATE ApprovalLog SET reviewer = ? WHERE staging_id = ?", (st["reviewer"], sid))
                    rec["result"] = {"blocked": False}
                    erp.con.execute("UPDATE ApprovalLog SET reviewer = NULL WHERE staging_id = ?", (sid,))
                except Exception as e:
                    rec["result"] = {"blocked": True, "error": str(e)}
            elif "check_rolled_back" in st:
                sid = staging_of(erp, st["check_rolled_back"])[0]
                rec["result"] = {"record_absent": erp.current("SalesOrder", st["key"]) is None,
                                 "approval_status": erp.q("SELECT approval_status FROM ApprovalLog WHERE staging_id = ?", sid)[0][0],
                                 "history_rows": erp.q("SELECT COUNT(*) FROM ChangeHistory WHERE approval_id = ?", f"APR-{sid}")[0][0]}
            log.append(rec)
    return {"policy": policy, "log": log, "erp": erp, "base_counts": base_counts, "spec": spec, "mapper": mapper, "auto": erp.auto_policy}


def score(run) -> dict:
    erp, spec, log = run["erp"], run["spec"], run["log"]
    res = {}
    # 1) 필드 매핑 정확도 (field_truth가 있는 행)
    ft_total = ft_ok = val_total = val_ok = wrong_field = cand_total = 0
    for s in spec["scenarios"]:
        for row_ref, tbls in s["truth"].get("field_truth", {}).items():
            bid, row = row_ref.split(":")
            cands = erp.q("SELECT proposed_entity, proposed_field, proposed_value FROM MappingCandidate WHERE batch_id = ? AND candidate_id LIKE ?", bid, f"CND-{bid}-{row}-%")
            expected = {(t, f): v for t, vals in tbls.items() for f, v in vals.items()}
            got = {(e, f): v for e, f, v in cands}
            cand_total += len(got)
            for (t, f), v in expected.items():
                ft_total += 1
                ft_ok += (t, f) in got
                if v is not None:
                    val_total += 1
                    val_ok += got.get((t, f)) == str(v)
            wrong_field += sum(1 for k in got if k not in expected)
    res["field_mapping_accuracy"] = {"correct": ft_ok, "total": ft_total, "rate": round(ft_ok / ft_total, 4)}
    res["value_mapping_accuracy"] = {"correct": val_ok, "total": val_total, "rate": round(val_ok / val_total, 4)}
    res["wrong_field_mapping_rate"] = {"wrong": wrong_field, "total_candidates": cand_total, "rate": round(wrong_field / cand_total, 4) if cand_total else None}
    # 2) 최종 상태 검사 (반영해야 할 것 / 반영되면 안 되는 것 / 바뀌면 안 되는 것)
    gt = D.load_gt()
    checks, wrong_commits = [], []
    for s in spec["scenarios"]:
        t = s["truth"]
        for table, key, vals in t.get("must_exist", []):
            cur = erp.current(table, key)
            ok = cur is not None and all(str(cur.get(k)) == str(v) for k, v in vals.items())
            checks.append({"scenario": s["id"], "check": "must_exist", "table": table, "key": key, "ok": ok})
        for table, key in t.get("must_not_exist", []):
            cur = erp.current(table, key) if all(v is not None for v in key.values()) else None
            ok = cur is None
            checks.append({"scenario": s["id"], "check": "must_not_exist", "table": table, "key": key, "ok": ok})
            if not ok:
                wrong_commits.append({"scenario": s["id"], "table": table, "key": key})
        for table, key in t.get("must_be_unchanged", []):
            ent = M.TABLES[table][0]
            src = next(r for r in gt["entities"][ent] if all(r[k] == v for k, v in key.items()))
            cur = erp.current(table, key)
            ok = all(str(cur.get(c)) == str(src.get(c)) for c in erp.cols[table])
            checks.append({"scenario": s["id"], "check": "must_be_unchanged", "table": table, "key": key, "ok": ok})
            if not ok:
                wrong_commits.append({"scenario": s["id"], "table": table, "key": key, "kind": "changed"})
        for table, key, vals in t.get("must_not_have", []):
            cur = erp.current(table, key)
            ok = cur is None or not all(str(cur.get(k)) == str(v) for k, v in vals.items())
            checks.append({"scenario": s["id"], "check": "must_not_have", "table": table, "key": key, "ok": ok})
            if not ok:
                wrong_commits.append({"scenario": s["id"], "table": table, "key": key, "kind": "wrong_value"})
        for table, key, n in t.get("max_count", []):
            k = M.TABLES[table][1]
            c = erp.q(f'SELECT COUNT(*) FROM "{table}" WHERE ' + " AND ".join(f"{x} = ?" for x in k), *[key[x] for x in k])[0][0]
            checks.append({"scenario": s["id"], "check": "max_count", "table": table, "key": key, "count": c, "ok": c <= n})
        for table, key, n in t.get("history_count", []):
            c = erp.q("SELECT COUNT(*) FROM ChangeHistory WHERE target_entity = ? AND target_key = ?", table, json.dumps(key, ensure_ascii=False))[0][0]
            checks.append({"scenario": s["id"], "check": "history_count", "table": table, "key": key, "count": c, "ok": c == n})
    # 3) 반영된 값 (부트스트랩 제외) 중 정답과 다른 값
    commits = erp.q("SELECT c.target_entity, c.target_key, c.after_json, c.approval_id, c.operation FROM ChangeHistory c JOIN ApprovalLog a ON a.approval_id = c.approval_id "
                    "WHERE a.reviewer <> 'SYSTEM_BOOTSTRAP' ORDER BY c.history_id")
    truth = {}
    for s in spec["scenarios"]:
        for table, key, vals in s["truth"].get("must_exist", []):
            truth[(table, json.dumps(key, ensure_ascii=False))] = vals
    committed = []
    for table, key, after, aid, op in commits:
        want = truth.get((table, key))
        a = json.loads(after)
        # 최종 정답은 마지막 반영 기준. 중간 반영(X02의 50)은 그 시점의 원본과 같으면 정답으로 본다
        mid_ok = table == "SalesOrder" and json.loads(key)["order_id"] == "O021" and op == "INSERT" and a["order_qty"] == "50"
        ok = (want is not None and all(str(a.get(k)) == str(v) for k, v in want.items())) or mid_ok
        committed.append({"table": table, "key": json.loads(key), "approval_id": aid, "operation": op, "correct": ok})
    wrong, seen = [], set()
    for c in [c for c in committed if not c["correct"]] + wrong_commits:     # 같은 레코드를 두 번 세지 않음
        k = (c["table"], json.dumps(c["key"], sort_keys=True))
        if k not in seen:
            seen.add(k)
            wrong.append(c)
    res["commits"] = committed
    res["wrong_value_commits"] = wrong
    res["wrong_value_commit_rate"] = {"wrong": len(wrong), "committed": len(committed), "rate": round(len(wrong) / len(committed), 4) if committed else None}
    res["state_checks"] = {"passed": sum(c["ok"] for c in checks), "total": len(checks), "failed": [c for c in checks if not c["ok"]]}
    # 4) 중복 탐지
    found = [d for r in log if r.get("duplicates") for d in r["duplicates"]] + [{"kind": "BATCH_RERUN", "key": {"batch_id": r["batch_id"]}} for r in log if r.get("reused")]
    exp_d = [d for s in spec["scenarios"] for d in s["truth"].get("duplicates", [])]
    hit = [d for d in exp_d if any(f["kind"] == d["kind"] and all(f["key"].get(k) == v for k, v in d["key"].items()) for f in found)]
    res["duplicate_detection"] = {"detected": len(hit), "expected": len(exp_d), "rate": round(len(hit) / len(exp_d), 4) if exp_d else None}
    # 5) 자동 승인·검토 비율 (부트스트랩 제외 staging)
    st = erp.q("SELECT s.staging_id, s.review_required, s.blocking_issue_count, a.approval_status, a.reviewer FROM StagingRecord s JOIN ApprovalLog a ON a.staging_id = s.staging_id "
               "WHERE s.batch_id <> 'BOOTSTRAP-E01-V2'")
    n = len(st)
    res["staging"] = {"total": n, "auto_accepted": sum(1 for x in st if x[4] == "AUTO_RULE"), "review_required": sum(1 for x in st if x[1]),
                      "blocked": sum(1 for x in st if x[2] > 0), "final_status": {k: sum(1 for x in st if x[3] == k) for k in ("PENDING", "APPROVED", "REJECTED", "HOLD")}}
    res["auto_accept_coverage"] = round(res["staging"]["auto_accepted"] / n, 4)
    res["manual_review_rate"] = round(res["staging"]["review_required"] / n, 4)
    # 6) 반려 정확도: 반영되면 안 되는 대상 중 실제로 반영되지 않은 비율 / 반영돼야 할 대상을 잘못 막은 수
    neg = [c for c in checks if c["check"] in ("must_not_exist", "must_be_unchanged", "must_not_have")]
    pos = [c for c in checks if c["check"] == "must_exist"]
    res["rejection_accuracy"] = {"correctly_not_committed": sum(c["ok"] for c in neg), "should_not_commit": len(neg),
                                 "wrongly_blocked_should_commit": sum(1 for c in pos if not c["ok"])}
    # 7) 안전성 단계 (명시 단계의 기대 결과)
    safety = []
    for r in log:
        if r["step"] == "approve" and "expected" in r:
            safety.append({"scenario": r["scenario"], "test": f"approve→{r['expected']}", "ok": r["as_expected"], "result": r["result"]})
        if r["step"] in ("raw_insert_with_pending", "db_update_decided", "db_set_reviewer"):
            safety.append({"scenario": r["scenario"], "test": r["step"], "ok": r["result"]["blocked"], "result": r["result"]})
        if r["step"] == "check_rolled_back":
            ok = r["result"]["record_absent"] and r["result"]["approval_status"] == "PENDING" and r["result"]["history_rows"] == 0
            safety.append({"scenario": r["scenario"], "test": "rollback_state", "ok": ok, "result": r["result"]})
        if r["step"] == "stage" and r["scenario"] == "DRY":
            ok = [d["operation"] for d in r["diff"]] == ["INSERT"] and not r["staged"]
            safety.append({"scenario": "DRY", "test": "dry_run_no_staging", "ok": ok, "result": r["diff"]})
    res["safety_tests"] = {"passed": sum(x["ok"] for x in safety), "total": len(safety), "items": safety}
    # 8) 원본 추적: 반영 레코드 → 승인 → staging → 후보 → 원본 파일·행
    traced = 0
    for c in committed:
        cids = json.loads(erp.q("SELECT s.candidate_ids FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = ?", c["approval_id"])[0][0])
        refs = [json.loads(x[0]) for cid in cids for x in erp.q("SELECT source_reference FROM MappingCandidate WHERE candidate_id = ?", cid)]
        traced += bool(refs) and all(r.get("source_file") and r.get("source_sha256") and r.get("location", {}).get("row") for r in refs)
    res["source_traceability"] = {"traced": traced, "committed": len(committed), "rate": round(traced / len(committed), 4) if committed else None}
    # 9) 규칙 기대·금지, 자동 승인 금지, 승인 없는 본 테이블 수정
    rule_checks = []
    for s in spec["scenarios"]:
        bids = [st["stage"]["batch_id"] for st in s["steps"] if "stage" in st]
        rules = {x[0] for b in bids for x in erp.q("SELECT i.rule_id FROM ValidationIssue i JOIN MappingCandidate c ON c.candidate_id = i.candidate_id WHERE c.batch_id = ?", b)}
        t = s["truth"]
        if t.get("expected_rules"):
            rule_checks.append({"scenario": s["id"], "check": "expected_rules", "want": t["expected_rules"], "got": sorted(rules), "ok": set(t["expected_rules"]) <= rules})
        if t.get("forbidden_rules"):
            rule_checks.append({"scenario": s["id"], "check": "forbidden_rules", "want_absent": t["forbidden_rules"], "got": sorted(rules), "ok": not set(t["forbidden_rules"]) & rules})
        nab = t.get("no_auto_approval") or (bids[0] if t.get("no_auto_approval_when_policy") == ("none" if run["auto"] is None else run["auto"]) else None)
        if nab:
            n = erp.q("SELECT COUNT(*) FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE s.batch_id = ? AND a.reviewer = 'AUTO_RULE'", nab)[0][0]
            rule_checks.append({"scenario": s["id"], "check": "no_auto_approval", "auto_approved": n, "ok": n == 0})
    res["rule_checks"] = {"passed": sum(c["ok"] for c in rule_checks), "total": len(rule_checks), "items": rule_checks}
    res["auto_approved_with_issues"] = erp.q("SELECT COUNT(DISTINCT s.staging_id) FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id "
                                             "JOIN ValidationIssue i ON i.issue_id LIKE 'ISS-' || s.staging_id || '-%' WHERE a.reviewer = 'AUTO_RULE'")[0][0]
    unapproved = 0
    for t in M.TABLES:
        unapproved += erp.q(f'SELECT COUNT(*) FROM "{t}" x LEFT JOIN ApprovalLog a ON a.approval_id = x.approved_by '
                            f"LEFT JOIN ChangeHistory h ON h.approval_id = x.approved_by WHERE a.approval_status IS NOT 'APPROVED' OR h.history_id IS NULL")[0][0]
    res["master_rows_without_approval_or_history"] = unapproved
    res["mapper"], res["auto_policy"] = run["mapper"], run["auto"]
    res["fk_enabled"] = erp.fk_on
    res["events"] = erp.events
    return res


def timing_child(policy, mapper="v1", auto=None, which="eval"):
    t0 = time.perf_counter()
    r = run_suite(policy, mapper, auto, which)
    t1 = time.perf_counter()
    s = score(r)
    t2 = time.perf_counter()
    mi = psutil.Process().memory_info()
    rows = json.loads(SETS[which][1].read_text(encoding="utf-8"))["input_rows"]
    print(json.dumps({"ok": True, "policy": policy, "run_s": t1 - t0, "score_s": t2 - t1, "input_rows": rows, "per_input_row_ms": (t1 - t0) / rows * 1000,
                      "self_peak_mb": round(getattr(mi, "peak_wset", mi.rss) / 1048576, 1), "wrong_value_commits": len(s["wrong_value_commits"])}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing-child")
    ap.add_argument("--mapper", default="v1")
    ap.add_argument("--auto", default=None, help="none | experimental (v2 기본 none)")
    ap.add_argument("--set", default="eval", choices=list(SETS))
    ap.add_argument("--out", default=None, help="결과 하위 폴더 (v1 기본 출력 외에는 필수)")
    a = ap.parse_args()
    if a.timing_child:
        return timing_child(a.timing_child, a.mapper, a.auto, a.set)
    global OUT
    if a.mapper != "v1" or a.set != "eval" or a.auto is not None:
        if not a.out:
            raise SystemExit("v1 기준선 외 실행은 --out 하위 폴더가 필요 (기존 결과 덮어쓰기 방지)")
        OUT = OUT / a.out
    if (OUT / "results.json").exists():
        raise SystemExit(f"{OUT.relative_to(ROOT)}에 결과가 이미 있음 → 덮어쓰지 않음")
    spec, man = load_spec(a.set)
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for policy in ("ideal", "rubber_stamp"):
        r = run_suite(policy, a.mapper, a.auto, a.set)
        s = score(r)
        out[policy] = {"score": s, "log": r["log"], "final_counts": r["erp"].counts(), "base_counts": r["base_counts"]}
        print(policy, json.dumps({k: s[k] for k in ("field_mapping_accuracy", "value_mapping_accuracy", "wrong_value_commit_rate", "duplicate_detection",
                                                    "auto_accept_coverage", "manual_review_rate", "rejection_accuracy")}, ensure_ascii=False),
              "state", s["state_checks"]["passed"], "/", s["state_checks"]["total"], "safety", s["safety_tests"]["passed"], "/", s["safety_tests"]["total"],
              "rules", s["rule_checks"]["passed"], "/", s["rule_checks"]["total"], "auto_with_issues", s["auto_approved_with_issues"],
              "unapproved_rows", s["master_rows_without_approval_or_history"], flush=True)
    timing = []
    for policy in ("ideal", "rubber_stamp"):
        runs = []
        for _ in range(REPEATS):
            with tempfile.TemporaryFile() as fo:
                cmd = [sys.executable, str(Path(__file__)), "--timing-child", policy, "--mapper", a.mapper, "--set", a.set] + (["--auto", a.auto] if a.auto else [])
                subprocess.run(cmd, cwd=ROOT, stdout=fo, check=True)
                fo.seek(0)
                runs.append(json.loads(fo.read().decode("utf-8").strip().splitlines()[-1]))
        med = lambda k: round(statistics.median(x[k] for x in runs), 4)
        timing.append({"policy": policy, "runs": len(runs), "run_s_median": med("run_s"), "run_s_min": round(min(x["run_s"] for x in runs), 4),
                       "run_s_max": round(max(x["run_s"] for x in runs), 4), "per_input_row_ms_median": med("per_input_row_ms"), "self_peak_mb_median": med("self_peak_mb"),
                       "input_rows": runs[0]["input_rows"], "repeat_wrong_value_commits": [x["wrong_value_commits"] for x in runs]})
    from importlib.metadata import version
    import sqlite3
    meta = {"experiment_id": "E10", "status": "RUNNING", "mapper": a.mapper, "auto_policy": a.auto or ("experimental" if a.mapper == "v1" else "none (REVIEW_REQUIRED)"),
            "set": a.set, "eval_set_sha256": man["eval_set_sha256"], "ground_truth_v2_sha256": D.GT_SHA256,
            "ddl_sha256": hashlib.sha256((ROOT / "schemas" / "e10_mock_erp.sql").read_bytes()).hexdigest(),
            "rules_sha256": hashlib.sha256((ROOT / "configs" / "e10_mapping_rules.json").read_bytes()).hexdigest(),
            "code_sha256": {f: hashlib.sha256((ROOT / "scripts" / f).read_bytes()).hexdigest() for f in ("e10_mock_erp.py", "e10_build_eval_set.py", "e10_run.py", "e05_validate_python.py")},
            "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "pydantic": version("pydantic"), "external_calls": 0,
            "comparators": {"implemented": ["rule_based (E02 헤더·코드표, 품명 정확 일치)", "master code check", "E05 Python 검증 규칙 재사용"],
                            "not_implemented": ["BM25", "embedding", "Tri-CHEF", "LLM"]},
            "auto_accept_policy": "configs/e10_mapping_rules.json auto_accept.experimental_policy_e10_v1 (실험 전용, 팀 합의 필요)"}
    for name, obj in (("results.json", out), ("timing.json", timing), ("run_meta.json", meta)):
        (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(timing, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
