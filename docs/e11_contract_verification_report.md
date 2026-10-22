# E11 최소 계약 검증 보고

> 작성 2026-10-22. 상태 **RUNNING** (계약·판정 규칙만 검증, 예측·최적화·계획 생성 미구현 — 예측·최적화 담당 범위). 로컬·미커밋.
> 코드 `scripts/e11_contract_check.py`, 테스트 `tests/test_e11_contract.py`, 결과 `results/E11_contract/results.json`. OR-Tools·웹 UI 없음, 새 패키지 없음.

## 1. 무엇을 검증했나

- 계약 구조: `schemas/e11_scenario_contract.json`의 키워드(type·required·enum·const·pattern·properties·items·$ref·anyOf·minimum·allOf if/then)만 해석하는 작은 검증기로 PlanningInput·ScenarioEvaluation을 검사.
- Hard Constraint 판정: [e11_constraint_policy.md](e11_constraint_policy.md) §3 — 위반 → INFEASIBLE, 판정에 필요한 사실 미확인 → UNVERIFIED, 둘 다 없음 → FEASIBLE, 순위는 FEASIBLE끼리만.
- 계획안은 시험용 입력(T-01·T-02)과 E01 정답셋의 계획 평가값(PLAN-REG·OT·OUT, 값 변경 없음)뿐이다.

## 2. 결과 — 11/11 통과

| 시험 | 결과 |
|---|---|
| T-01 독립 계산 | 생산 900, 자재 1,800 kg, 부족 300 kg, 능력 초과 100 (수계산 식, 다른 구현 호출 없음) |
| T-01 정규 생산만 | **INFEASIBLE** (HC-CAP 900 > 800, HC-MAT 300 kg 부족) |
| T-01 외주·잔업 100개 | **UNVERIFIED** — 외주 조건·조달 리드타임 미확인, 자동 FEASIBLE 아님 |
| FEASIBLE 계획 없음 | 순위 없음 (rank = null) |
| T-02 대조 (외주·조달 조건을 "확인됨"으로 둔 경우) | 추가안만 FEASIBLE, 정규안은 여전히 INFEASIBLE — 판정기가 무조건 UNVERIFIED를 내는 것이 아님을 확인 |
| 가중치 극단값 (비용 −10⁶ 등) | INFEASIBLE 계획은 비교 대상에 들어오지 않음 |
| ScenarioEvaluation 출력 | 계약 스키마 만족 |
| 계약 위반 예 (INFEASIBLE인데 rank·comparable 설정) | 검증기가 거부 |
| T-01 PlanningInput | 계약 스키마 만족 (`unverified_facts`에 미확인 사실 2개 명시) |
| 지수 표기 수량 `1e3` | 계약의 decimal 형식이 거부 (E05·E06의 lax 숫자 결함 대응) |
| E01 계획안 3개 | **PLAN-REG·PLAN-OT·PLAN-OUT 모두 INFEASIBLE** (능력 초과 36.5 h / 잔업안·외주안도 초과 행 존재), PLAN-OUT은 외주 조건 UNVERIFIED도 함께 |

## 3. 의미

- 확인되지 않은 생산능력·외주 조건이 자동으로 FEASIBLE이 되지 않음을 판정 규칙 수준에서 확인했다.
- **E01 합성 데이터의 계획안은 모두 실행 불가**로 판정된다 → E01 데이터만으로는 Soft Objective 비교(계획 간 순위)를 시험할 수 없다. 계획 생성기 시험에는 실행 가능한 계획이 나오는 시나리오가 따로 필요하다 (예측·최적화 담당과 합의 필요).
- 능력 판정은 E01 Routing 기반 시간 단위, T-01은 수량 단위(800개) — 두 단위 사이 환산 규칙은 아직 정하지 않았다(인터페이스 문서 §6).

## 4. 미검증

예측 결과(ForecastResult) 생성, 계획 생성(PlanCandidate)·최적화, HC-DUE(필수 납기)·HC-BIZ(업무 제약) 판정, 실제 외주·조달 조건, 처리시간(측정하지 않음).
