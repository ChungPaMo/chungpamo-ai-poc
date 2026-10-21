"""E05 채점기: 검증 보고 ↔ 독립 정답(eval_set_v1.json의 truth). 검증기 코드를 import하지 않는다.

판정 (evaluation_protocol §4.1 기반)
- 정확한 탐지(TP): (규칙, record_uid, 필드)가 기대 항목과 일치 (필드 '*'는 어느 필드와도 일치)
- 파생 보고: 정답의 derived (규칙, record_uid) — 탐지율·오탐에서 제외, 따로 집계
- 허용 보고: 정답의 acceptable — 같은 원인의 다른 규칙 보고, 오탐 아님
- 부분 탐지: 기대 레코드는 맞지만 규칙·필드가 다름 — 탐지율 분자 제외, 오탐 아님
- 오탐(FP): 위 어디에도 해당하지 않는 보고 (정상·경계 통과 데이터의 보고는 전부 오탐)
- 미탐지(FN): 보고되지 않은 기대 항목
- TN: (규칙, 레코드) 쌍 기준 근사 — 규칙 대상 엔터티의 레코드 수 합 − 위 판정에 쓰인 쌍
규칙 단위 지표와 사건 단위 지표(주입 1건 = 사건 1건)를 따로 낸다. 심각도 ERROR와 WARNING 규칙을 따로 집계하고 INFO(V13)는 넣지 않는다.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "configs" / "e05_validation_rules.json").read_text(encoding="utf-8"))
SEV = {r["rule_id"]: r["severity"] for r in CATALOG["rules"]}
CODE = {r["rule_id"]: r["error_code"] for r in CATALOG["rules"]}
ALL_ENT = ["Unit", "Product", "Material", "Supplier", "SupplierMaterial", "BOM", "BOMLine", "Order", "SalesHistory", "Inventory", "Resource",
           "Operation", "ProductionPlan", "ProductionPlanLine"]
RULE_ENTITIES = {"S01": ALL_ENT, "S02": ALL_ENT, "S03": ALL_ENT, "S04": ALL_ENT, "S05": ALL_ENT, "S06": ALL_ENT, "S07": ALL_ENT,
                 "S08": [e for e in ALL_ENT if e != "Inventory"], "R01": ["BOM", "BOMLine", "Order", "Operation", "ProductionPlanLine", "SalesHistory", "Inventory"],
                 "R02": ["BOMLine", "SupplierMaterial", "Inventory"], "R03": ["SupplierMaterial"], "R04": ["BOMLine"], "R05": ["Operation", "ProductionPlanLine"],
                 "R06": ["ProductionPlanLine"], "R07": ["Unit", "Product", "Material", "BOMLine", "Order", "Inventory", "ProductionPlanLine"],
                 "B01": ["BOMLine"], "B02": ["BOM"], "B03": ["BOM"], "B04": ["BOM"], "B05": ["BOM"], "B06": ["ProductionPlanLine"], "B07": ["BOMLine"],
                 "B08": ["BOMLine", "Order", "Inventory", "ProductionPlanLine"], "B09": ["BOM"], "B10": ["BOMLine"], "B11": ["SupplierMaterial"],
                 "B12": ["SalesHistory"], "B13": ["SalesHistory"], "B14": ["Product"], "V01": ["Inventory"], "V02": ["Inventory"], "V03": ["Inventory"],
                 "V04": ["Inventory"], "V05": ["Inventory"], "V06": ["Inventory"], "V07": ["Order"], "V08": ["Order", "ProductionPlanLine"],
                 "V09": ["ProductionPlanLine"], "V10": ["ProductionPlanLine"], "V11": ["ProductionPlanLine"], "V12": ["ProductionPlanLine"]}


def score_dataset(ds: dict, reports: list[dict], entity_counts: dict, implemented: set[str]) -> dict:
    t = ds["truth"]
    exp = []
    for x in t["expected"]:
        for u in x["record_uids"]:
            exp.append({"rule": x["rule"], "uid": u, "field": x["field"], "event": x.get("from", ds["dataset_id"])})
    target_uids = {e["uid"] for e in exp}
    acceptable = [(a["rule"], set(a["record_uids"]) if a["record_uids"] is not None else target_uids) for a in t["acceptable"]]
    derived = {(d["rule"], u) for d in t["derived"] for u in d["record_uids"]}
    matched = set()
    cls = Counter()
    fps, partial = [], []
    seen = set()
    for r in reports:
        if r.get("severity") == "INFO":
            continue
        key = (r["rule_id"], r.get("record_uid"), r.get("field"))
        if key in seen:
            cls["duplicate"] += 1
            continue
        seen.add(key)
        hit = [i for i, e in enumerate(exp) if e["rule"] == r["rule_id"] and e["uid"] == r.get("record_uid") and (e["field"] == r.get("field") or "*" in (e["field"], r.get("field")))]
        if hit:
            new = [i for i in hit if i not in matched]
            matched.update(hit)
            cls["tp_reports" if new else "duplicate"] += 1
            continue
        if (r["rule_id"], r.get("record_uid")) in derived:
            cls["derived"] += 1
            continue
        if any(r["rule_id"] == rule and r.get("record_uid") in uids for rule, uids in acceptable):
            cls["acceptable"] += 1
            continue
        if r.get("record_uid") in target_uids:
            cls["partial"] += 1
            partial.append({k: r.get(k) for k in ("rule_id", "entity", "record_uid", "field")})
            continue
        cls["fp"] += 1
        fps.append({k: r.get(k) for k in ("rule_id", "entity", "record_uid", "field", "severity")})
    by_sev = {}
    for sev in ("ERROR", "WARNING"):
        e_idx = [i for i, e in enumerate(exp) if SEV.get(e["rule"]) == sev]
        tp = sum(1 for i in e_idx if i in matched)
        fn_items = [exp[i] for i in e_idx if i not in matched]
        fp = sum(1 for f in fps if SEV.get(f["rule_id"], "ERROR") == sev)
        universe = sum(entity_counts.get(ent, 0) for rule in implemented if SEV.get(rule) == sev for ent in RULE_ENTITIES.get(rule, []))
        used = len({(exp[i]["rule"], exp[i]["uid"]) for i in e_idx}) + fp
        by_sev[sev] = {"tp": tp, "fn": len(fn_items), "fp": fp, "tn": max(0, universe - used), "fn_items": fn_items}
    events = defaultdict(list)
    for i, e in enumerate(exp):
        events[e["event"]].append(i in matched)
    return {"dataset_id": ds["dataset_id"], "kind": ds["kind"], "error_code": ds.get("error_code"), "severity": ds.get("severity"),
            "classes": dict(cls), "by_severity": by_sev, "false_positives": fps, "partial": partial,
            "events": {k: {"any": any(v), "all": all(v), "items": len(v)} for k, v in events.items()},
            "expected_rules": sorted({e["rule"] for e in exp}), "matched_rules": sorted({exp[i]["rule"] for i in matched})}


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"precision": None if p is None else round(p, 4), "recall": None if r is None else round(r, 4), "f1": None if f is None else round(f, 4)}


def aggregate(results: list[dict], implemented: set[str]) -> dict:
    out = {}
    for sev in ("ERROR", "WARNING"):
        tp = sum(r["by_severity"][sev]["tp"] for r in results)
        fp = sum(r["by_severity"][sev]["fp"] for r in results)
        fn = sum(r["by_severity"][sev]["fn"] for r in results)
        tn = sum(r["by_severity"][sev]["tn"] for r in results)
        out[sev] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, **prf(tp, fp, fn)}
    for sev in ("ERROR", "WARNING"):
        ev = [v for r in results if r["kind"] in ("single", "compound") and (r["severity"] or "ERROR") == sev for v in r["events"].values()]
        out[f"events_{sev}"] = {"total": len(ev), "detected_any": sum(1 for v in ev if v["any"]), "detected_all_items": sum(1 for v in ev if v["all"])}
    by_code = defaultdict(lambda: [0, 0])
    for r in results:
        if r["kind"] == "single":
            for k, v in r["events"].items():
                by_code[r["error_code"]][1] += 1
                by_code[r["error_code"]][0] += v["any"]
    out["event_recall_by_error_code"] = {k: f"{a}/{b}" for k, (a, b) in sorted(by_code.items())}
    expected_rules = {x for r in results for x in r["expected_rules"]}
    hit_rules = {x for r in results for x in r["matched_rules"]}
    out["rule_coverage"] = {"rules_with_expected_items": len(expected_rules), "rules_detected_at_least_once": len(hit_rules & expected_rules),
                            "implemented_rules": len(implemented), "never_detected": sorted(expected_rules - hit_rules)}
    out["classes"] = dict(sum((Counter(r["classes"]) for r in results), Counter()))
    out["fp_on_clean_and_pass"] = sum(len(r["false_positives"]) for r in results if r["kind"] in ("clean", "pass"))
    return out


def capacity_check(table: list[dict], gt_expected: dict) -> dict:
    exp = {(p, c["resource_id"], c["week_start"]): (float(c["required_h"]), float(c["excess_h"])) for p, v in gt_expected["plan_evaluation"].items() for c in v["capacity"]}
    got = {(c["plan_id"], c["resource_id"], c["week_start"]): (float(c["required_h"]), float(c["excess_h"])) for c in table}
    keys = set(exp) | set(got)
    ok = sum(1 for k in keys if abs(exp.get(k, (0.0, 0.0))[0] - got.get(k, (0.0, 0.0))[0]) < 1e-6 and abs(exp.get(k, (0.0, 0.0))[1] - got.get(k, (0.0, 0.0))[1]) < 1e-6)
    missing_zero = sum(1 for k in set(exp) - set(got) if exp[k] == (0.0, 0.0))
    return {"rows_compared": len(keys), "rows_equal": ok, "expected_rows_missing_in_output_with_zero_hours": missing_zero,
            "excess_rows_expected": sum(1 for v in exp.values() if v[1] > 0), "excess_rows_output": sum(1 for v in got.values() if v[1] > 0)}
