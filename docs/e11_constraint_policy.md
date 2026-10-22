# E11 제약 정책 — Hard Constraint와 Soft Objective

> 작성 2026-10-21 (정책 v0.1 초안, 미구현). 인터페이스: [e11_decision_interface.md](e11_decision_interface.md).
> 실제 기업의 업무상 필수 제약은 확인되지 않았다(D-036). 아래 목록은 E01 데이터 모델에서 계산 가능한 제약이며, 실제 규칙은 도메인·KPI 담당 조사 후 추가·수정한다.

## 1. 원칙

1. **Hard Constraint는 모든 계획안에 똑같이 적용한다.** 계획 생성기(규칙·최적화)가 아니라 공통 판정 모듈이 판정한다.
2. 가중치(soft_weights)를 어떻게 바꿔도 Hard Constraint 위반을 상쇄할 수 없다 — Hard 위반 계획은 점수를 매기지 않는다.
3. 제약을 만족하지 못하면 `INFEASIBLE`.
4. 판정에 필요한 사실이 확인되지 않았으면 `UNVERIFIED` — **실행 가능으로 가정하지 않는다.**
5. Soft Objective는 `FEASIBLE` 계획끼리만 비교한다. FEASIBLE 계획이 없으면 순위를 내지 않고 그 사실을 보고한다.

## 2. Hard Constraint 목록 (초안)

| ID | 종류 | 판정식 (기간·자원·품목별) | 근거 데이터 | 확인 상태 |
|---|---|---|---|---|
| HC-CAP | 생산능력 | Σ(계획 수량 × 단위 가공시간 + 준비시간) ≤ 정규시간 × 근무일 (+ 잔업 최대 × 근무일, 잔업 허용 시) | ProductionCapacity, Routing (decision_logic §6.1) | 데이터 모델상 계산 가능 |
| HC-MAT | 자재 공급 가능량 | 자재별 소요량 ≤ 가용 재고(보유 − 할당 + 기간 내 입고 예정) + 리드타임 안에 도착 가능한 조달량 | Inventory, SupplierItem (decision_logic §3·§4) | 조달 가능량 상한은 데이터에 없음 → 조달량을 쓰는 계획은 UNVERIFIED |
| HC-DUE | 필수 납기 | 필수 주문의 예상 완료일 ≤ due_date | SalesOrder, decision_logic §4 | "필수 주문" 정의 미확정 → 초안은 OPEN 주문 전부 |
| HC-OUT | 외주 조건 | 외주 수량 ≤ 외주처 능력, 외주 리드타임 안 입고, 자재 제공 조건 일치 | E01 `parameters.outsourcers`(합성 가정) | **미확인** (실제 외주처 조건 없음) → 외주를 쓰는 계획은 UNVERIFIED |
| HC-DATA | 데이터 유효성 | 계획 입력에 E05 ERROR 위반이 없음, BOM 선택이 정확히 1개 | E05 규칙, schema §3.6 | 계산 가능 |
| HC-BIZ | 기타 업무상 필수 제약 | (도메인·KPI 담당 확인 후 추가) | — | 미확인 |

## 3. 판정 규칙

```
for 계획 in 계획안들:
    위반 = [c for c in Hard 제약 if 판정(c, 계획) == VIOLATED]
    미확인 = [c for c in Hard 제약 if 판정(c, 계획) == UNVERIFIED]
    if 위반:        feasibility = INFEASIBLE
    elif 미확인:    feasibility = UNVERIFIED      # 자동 FEASIBLE 금지, 사람 확인 필요
    else:           feasibility = FEASIBLE
비교 대상 = [계획 for 계획 in 계획안들 if feasibility == FEASIBLE]
```

- 한 제약이 VIOLATED와 UNVERIFIED를 동시에 가질 수 있으면 VIOLATED가 우선한다.
- UNVERIFIED 계획은 "확인되면 실행 가능할 수 있음"으로만 표시하고, 확인해야 할 사실 목록(`unverified_facts`)을 함께 낸다.

## 4. 확인되지 않은 제약 (verified = false)

- 확인되지 않은 제약도 판정 대상에서 빼지 않는다. 그 제약에 의존하는 계획은 UNVERIFIED가 된다.
- 계획 생성기가 확인되지 않은 조건(외주 가능, 무한 조달 등)을 가정해 계획을 만들면, 그 가정은 `PlanCandidate.assumptions`에 남겨야 하고 판정 결과는 UNVERIFIED다.

## 5. Soft Objective (FEASIBLE끼리만)

| 목표 | 계산 | 상태 |
|---|---|---|
| 총비용 | 자재 + 정규 생산 + 잔업 + 외주 (decision_logic §5) | 계산 가능 |
| 재고 유지비 | — | E01 `미산정` (단가 미정) |
| 지연 위약금 | — | E01 `미산정` |
| 납기 여유 | 납기 − 예상 완료일 합 | 계산 가능 |
| 안전재고 충족률 | 기간 말 재고 / 안전재고 | 계산 가능 |

가중치는 도메인·KPI 담당이 정한다(팀 합의 필요). `미산정` 항목은 0으로 대체하지 않는다.

## 6. 테스트 기준

- T-01 (인터페이스 문서 §5): 정규 생산만 → INFEASIBLE(HC-CAP, HC-MAT), 외주·잔업 추가 → UNVERIFIED(HC-OUT 미확인, HC-MAT 조달 미확인), 비교 순위 없음.
- 가중치 변경 테스트(예정): soft_weights를 극단값으로 바꿔도 INFEASIBLE 계획이 비교 대상에 들어오지 않아야 한다.
- E01 Baseline(예정): `expected.plan_evaluation`(PLAN-REG·PLAN-OT·PLAN-OUT)의 능력 초과 행과 판정 일치.
