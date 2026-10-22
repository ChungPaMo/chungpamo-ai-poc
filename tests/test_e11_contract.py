"""E11 최소 계약 검증: T-01 독립 정답, Hard Constraint 판정(FEASIBLE / INFEASIBLE / UNVERIFIED), 계약 스키마 구조. 예측·최적화는 시험하지 않는다."""

from __future__ import annotations

import e05_dataset as D
import e11_contract_check as C


def test_t01_independent_answer_and_verdicts():
    calc, evals = C.t01()
    assert calc == {"required_production": "900", "required_material_kg": "1800", "material_shortage_kg": "300", "capacity_shortfall_units": "100"}
    assert [e["feasibility"] for e in evals] == ["INFEASIBLE", "UNVERIFIED"]
    assert all(e["rank"] is None for e in C.rank(evals, {"total_cost_krw": "1"}))


def test_unverified_conditions_never_feasible_and_weights_cannot_rescue_infeasible():
    _, only_out = C.t01(verified_outsourcing=True, verified_procurement=False)
    assert only_out[1]["feasibility"] == "UNVERIFIED"
    _, both = C.t01(verified_outsourcing=True, verified_procurement=True)
    ranked = C.rank(both, {"total_cost_krw": "-1000000"})
    assert ranked[0]["feasibility"] == "INFEASIBLE" and ranked[0]["rank"] is None and ranked[1]["rank"] == 1


def test_contract_schema_checker_accepts_valid_and_rejects_invalid():
    _, evals = C.t01()
    assert all(not C.check(e, {"$ref": "#/$defs/ScenarioEvaluation"}) for e in evals)
    assert C.check({"plan_id": "X", "feasibility": "UNVERIFIED", "violations": [], "comparable": True, "rank": 2}, {"$ref": "#/$defs/ScenarioEvaluation"})
    assert C.check({"value": "1e3"}, {"properties": {"value": {"$ref": "#/$defs/decimal"}}})


def test_e01_plans_all_exceed_capacity_so_none_feasible():
    base = C.e01_baseline(D.load_gt())
    assert {b["plan_id"]: b["evaluation"]["feasibility"] for b in base} == {"PLAN-REG": "INFEASIBLE", "PLAN-OT": "INFEASIBLE", "PLAN-OUT": "INFEASIBLE"}
