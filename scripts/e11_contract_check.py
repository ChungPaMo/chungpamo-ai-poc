"""E11 최소 계약 검증 — 데이터 계약 구조와 Hard Constraint 판정(FEASIBLE / INFEASIBLE / UNVERIFIED)만 시험한다.

    .\\.venv\\Scripts\\python.exe scripts\\e11_contract_check.py

예측·최적화·계획 생성은 구현하지 않는다 (예측·최적화 담당 범위). 계획안은 시험용으로 손으로 적은 입력이거나 E01 정답셋의 계획 평가값이다.
- 구조 검증: schemas/e11_scenario_contract.json의 사용 키워드(type·required·enum·const·pattern·properties·items·$ref·anyOf·minimum)만 해석하는 작은 검증기
- 판정: docs/e11_constraint_policy.md §3 (위반 → INFEASIBLE, 미확인 → UNVERIFIED, 둘 다 없음 → FEASIBLE, 순위는 FEASIBLE끼리만)
결과: results/E11_contract/results.json. 외부 호출 없음.
"""

from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import e05_dataset as D

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "e11_scenario_contract.json").read_text(encoding="utf-8"))
OUT = ROOT / "results" / "E11_contract"


def check(inst, sch, path="$") -> list[str]:
    """계약 스키마의 사용 키워드만 지원하는 검증기. 오류 경로 목록을 돌려준다."""
    if "$ref" in sch:
        return check(inst, SCHEMA["$defs"][sch["$ref"].split("/")[-1]], path)
    errs = []
    if "anyOf" in sch:
        if all(check(inst, s, path) for s in sch["anyOf"]):
            errs.append(f"{path}: anyOf 불일치")
        return errs
    t = sch.get("type")
    tmap = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "null": type(None), "number": (int, float)}
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        ok = any(isinstance(inst, tmap[x]) and not (x in ("integer", "number") and isinstance(inst, bool)) for x in ts)
        if not ok:
            return [f"{path}: 타입 {t} 아님"]
    if "const" in sch and inst != sch["const"]:
        errs.append(f"{path}: const {sch['const']} 아님")
    if "enum" in sch and inst not in sch["enum"]:
        errs.append(f"{path}: 허용값 아님 ({inst})")
    if "pattern" in sch and isinstance(inst, str) and not re.search(sch["pattern"], inst):
        errs.append(f"{path}: 형식 불일치 ({inst})")
    if "minimum" in sch and isinstance(inst, (int, float)) and inst < sch["minimum"]:
        errs.append(f"{path}: 최솟값 미만")
    if isinstance(inst, dict):
        for k in sch.get("required", []):
            if k not in inst:
                errs.append(f"{path}.{k}: 필수 필드 없음")
        for k, s in sch.get("properties", {}).items():
            if k in inst:
                errs += check(inst[k], s, f"{path}.{k}")
    if isinstance(inst, list) and "items" in sch:
        for i, x in enumerate(inst):
            errs += check(x, sch["items"], f"{path}[{i}]")
    for cond in sch.get("allOf", []):
        if not check(inst, cond.get("if", {}), path):
            errs += check(inst, cond.get("then", {}), path)
    return errs


def dd(x) -> Decimal:
    return Decimal(str(x))


def judge(plan_id: str, verdicts: list[dict], soft: dict | None = None) -> dict:
    """verdicts: [{constraint_id, kind, status: OK|VIOLATED|UNVERIFIED, ...}] → ScenarioEvaluation (정책 §3)."""
    viol = [v for v in verdicts if v["status"] in ("VIOLATED", "UNVERIFIED")]
    feas = "INFEASIBLE" if any(v["status"] == "VIOLATED" for v in viol) else ("UNVERIFIED" if viol else "FEASIBLE")
    ev = {"plan_id": plan_id, "feasibility": feas, "violations": [{k: v[k] for k in ("constraint_id", "kind", "status", "measured", "limit", "shortfall", "unit", "evidence")
                                                                   if k in v} | {"plan_id": plan_id} for v in viol],
          "comparable": feas == "FEASIBLE", "rank": None}
    if feas == "FEASIBLE" and soft:
        ev["soft_scores"] = [{"objective": k, "value": str(v)} for k, v in soft.items()]
    return ev


def rank(evals: list[dict], weights: dict) -> list[dict]:
    """FEASIBLE끼리만 가중합 오름차순 순위. INFEASIBLE·UNVERIFIED는 가중치와 무관하게 rank=None."""
    feas = [e for e in evals if e["feasibility"] == "FEASIBLE"]
    score = lambda e: sum(dd(weights.get(s["objective"], 0)) * dd(s["value"]) for s in e.get("soft_scores", []))
    for i, e in enumerate(sorted(feas, key=score)):
        e["rank"] = i + 1
    return evals


def t01(verified_outsourcing=False, verified_procurement=False):
    """T-01 독립 계산 (docs/e11_decision_interface.md §5). 수계산 식만 쓰고 다른 구현을 부르지 않는다."""
    demand, fg_inv, ss, mat_per, mat_oh, cap = dd(1000), dd(200), dd(100), dd(2), dd(1500), dd(800)
    req = max(Decimal(0), demand + ss - fg_inv)
    mat = req * mat_per
    short = max(Decimal(0), mat - mat_oh)
    over = max(Decimal(0), req - cap)
    calc = {"required_production": str(req), "required_material_kg": str(mat), "material_shortage_kg": str(short), "capacity_shortfall_units": str(over)}
    base = [{"constraint_id": "HC-CAP", "kind": "CAPACITY", "status": "VIOLATED" if req > cap else "OK", "measured": str(req), "limit": str(cap), "shortfall": str(over), "unit": "EA", "evidence": {}},
            {"constraint_id": "HC-MAT", "kind": "MATERIAL_SUPPLY", "status": "VIOLATED" if short > 0 else "OK", "measured": str(mat), "limit": str(mat_oh), "shortfall": str(short),
             "unit": "kg", "evidence": {"procurement": "없음"}}]
    extra = [{"constraint_id": "HC-CAP", "kind": "CAPACITY", "status": "OK", "measured": str(cap), "limit": str(cap), "unit": "EA", "evidence": {"inhouse": "800", "extra": str(over)}},
             {"constraint_id": "HC-OUT", "kind": "OUTSOURCING", "status": "OK" if verified_outsourcing else "UNVERIFIED", "measured": str(over), "limit": None, "unit": "EA",
              "evidence": {"fact": "외주 가능성·비용·납기·자재 제공 조건"}},
             {"constraint_id": "HC-MAT", "kind": "MATERIAL_SUPPLY", "status": "OK" if verified_procurement else "UNVERIFIED", "measured": str(mat), "limit": str(mat_oh),
              "shortfall": str(short), "unit": "kg", "evidence": {"fact": "300 kg 조달 리드타임"}}]
    soft = {"total_cost_krw": "1000", "due_slack_days": "0"}
    evals = [judge("T01-BASELINE", base), judge("T01-EXTRA-100", extra, soft)]
    return calc, evals


def e01_baseline(gt):
    """E01 정답셋 expected.plan_evaluation의 세 계획안을 같은 판정 규칙에 넣는다 (값 변경 없음)."""
    out = []
    for pid, v in gt["expected"]["plan_evaluation"].items():
        exc = [c for c in v["capacity"] if dd(c["excess_h"]) > 0]
        verd = [{"constraint_id": "HC-CAP", "kind": "CAPACITY", "status": "VIOLATED" if exc else "OK", "measured": str(sum(dd(c["required_h"]) for c in exc)) if exc else None,
                 "limit": None, "shortfall": v["capacity_excess_total_h"], "unit": "h", "evidence": {"rows_over": len(exc)}}]
        if v["outsourced_qty"]:
            verd.append({"constraint_id": "HC-OUT", "kind": "OUTSOURCING", "status": "UNVERIFIED", "measured": None, "limit": None, "unit": "EA",
                         "evidence": {"reason": "외주처 조건은 E01 합성 가정(parameters.outsourcers) — 실제 조건 미확인"}})
        out.append({"plan_id": pid, "evaluation": judge(pid, verd), "capacity_excess_total_h": v["capacity_excess_total_h"], "outsourced": bool(v["outsourced_qty"])})
    return out


def main() -> int:
    gt = D.load_gt()
    res = {"tests": []}

    def rec(name, ok, detail):
        res["tests"].append({"test": name, "ok": bool(ok), "detail": detail})

    calc, evals = t01()
    expect = {"required_production": "900", "required_material_kg": "1800", "material_shortage_kg": "300", "capacity_shortfall_units": "100"}
    rec("T-01 독립 계산값", calc == expect, calc)
    rec("T-01 정규 생산만 → INFEASIBLE", evals[0]["feasibility"] == "INFEASIBLE" and {v["constraint_id"] for v in evals[0]["violations"]} == {"HC-CAP", "HC-MAT"}, evals[0])
    rec("T-01 외주·잔업 100개 → UNVERIFIED (자동 FEASIBLE 금지)", evals[1]["feasibility"] == "UNVERIFIED", evals[1])
    ranked = rank(json.loads(json.dumps(evals)), {"total_cost_krw": "1"})
    rec("T-01 FEASIBLE 계획 없음 → 순위 없음", all(e["rank"] is None for e in ranked), [e["rank"] for e in ranked])
    _, ev2 = t01(verified_outsourcing=True, verified_procurement=True)
    rec("T-02 (대조) 외주·조달 조건 확인 시 → FEASIBLE", ev2[1]["feasibility"] == "FEASIBLE" and ev2[0]["feasibility"] == "INFEASIBLE", [e["feasibility"] for e in ev2])
    worst = rank(json.loads(json.dumps(ev2)), {"total_cost_krw": "-1000000", "due_slack_days": "1000000"})
    rec("가중치 극단값에도 INFEASIBLE은 비교 대상 아님", worst[0]["rank"] is None and worst[1]["rank"] == 1, [e["rank"] for e in worst])
    schema_errs = {e["plan_id"]: check(e, {"$ref": "#/$defs/ScenarioEvaluation"}) for e in evals + ev2}
    rec("ScenarioEvaluation 출력이 계약 스키마를 만족", all(not v for v in schema_errs.values()), schema_errs)
    bad = {"plan_id": "X", "feasibility": "INFEASIBLE", "violations": [], "comparable": True, "rank": 1}
    rec("계약 위반 예(INFEASIBLE인데 rank·comparable 설정)를 검증기가 잡음", bool(check(bad, {"$ref": "#/$defs/ScenarioEvaluation"})), check(bad, {"$ref": "#/$defs/ScenarioEvaluation"}))
    pi = {"input_id": "T01", "dataset_ref": {"source": "T-01 수계산", "sha256": "0" * 64}, "reference_date": "2026-11-15",
          "horizon": {"start": "2026-11-16", "end": "2026-12-13", "grain": "WEEK"},
          "orders": [{"order_id": "T-O1", "product_id": "P", "order_qty": "1000", "unit": "EA", "due_date": "2026-12-13", "status": "OPEN"}],
          "inventory": [{"item_type": "PRODUCT", "item_id": "P", "on_hand_qty": "200", "unit": "EA"}, {"item_type": "MATERIAL", "item_id": "M", "on_hand_qty": "1500", "unit": "kg"}],
          "items": [{"item_type": "PRODUCT", "item_id": "P", "base_unit": "EA", "safety_stock_qty": "100"}, {"item_type": "MATERIAL", "item_id": "M", "base_unit": "kg", "safety_stock_qty": "0"}],
          "boms": [{"product_id": "P", "bom_id": "B-P", "lines": [{"component_type": "MATERIAL", "component_id": "M", "qty_per": "2", "unit": "kg"}]}],
          "capacity": [{"resource_id": "R", "regular_hours_per_day": "8", "overtime_hours_per_day_max": "0", "unit": "EA_PER_PERIOD", "units_per_period": "800"}],
          "routings": [], "supply": [], "unverified_facts": [{"fact": "외주 가능성·비용·납기·자재 제공", "reason": "업체 미확인"}, {"fact": "자재 300 kg 조달 리드타임", "reason": "공급사 미확인"}]}
    rec("T-01 PlanningInput이 계약 스키마를 만족", not check(pi, {"$ref": "#/$defs/PlanningInput"}), check(pi, {"$ref": "#/$defs/PlanningInput"}))
    pi_bad = {**pi, "orders": [{**pi["orders"][0], "order_qty": "1e3"}]}
    rec("지수 표기 수량(1e3)을 계약이 거부 (E05·E06 결함 대응)", bool(check(pi_bad, {"$ref": "#/$defs/PlanningInput"})), check(pi_bad, {"$ref": "#/$defs/PlanningInput"}))
    base = e01_baseline(gt)
    rec("E01 계획안 판정: 능력 초과가 있는 계획은 INFEASIBLE, 외주 계획은 미확인 조건 포함",
        all((b["evaluation"]["feasibility"] == "INFEASIBLE") == (dd(b["capacity_excess_total_h"]) > 0) for b in base), [(b["plan_id"], b["evaluation"]["feasibility"],
                                                                                                                  b["capacity_excess_total_h"], b["outsourced"]) for b in base])
    res["t01"] = {"calc": calc, "evaluations": evals}
    res["e01_plans"] = base
    res["summary"] = {"passed": sum(t["ok"] for t in res["tests"]), "total": len(res["tests"])}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "results.json"
    if p.exists():
        prev = json.loads(p.read_text(encoding="utf-8"))
        if prev != json.loads(json.dumps(res, ensure_ascii=False, default=str)):
            print("주의: 이전 결과와 다름 — 덮어쓰기", file=sys.stderr)
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    for t in res["tests"]:
        print(("PASS " if t["ok"] else "FAIL ") + t["test"])
    print(res["summary"], [(b["plan_id"], b["evaluation"]["feasibility"]) for b in base])
    return 0 if res["summary"]["passed"] == res["summary"]["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
