# E11 ERP 기반 의사결정 PoC — 데이터 계약·인터페이스

> 작성 2026-10-21 (계약 v0.1 초안). 상태 **NOT_STARTED** — 예측모델·최적화 엔진은 구현하지 않았다. 담당 간 데이터 계약만 확정 가능한 범위에서 정했다.
> 제약 정책: [e11_constraint_policy.md](e11_constraint_policy.md). JSON Schema 초안: [schemas/e11_scenario_contract.json](../schemas/e11_scenario_contract.json). 계산 규칙 기준: [decision_logic.md](decision_logic.md).

## 1. 흐름과 담당 경계

```
E10 승인된 모의 ERP 레코드 ─► PlanningInput ─┬─► (예측) ForecastResult ─┐
                                              │                           ▼
ScenarioConfig + HardConstraint ──────────────┴─► (계획 생성) PlanCandidate ×2~3
                                                          │
                                         (공통 제약 판정) ConstraintViolation
                                                          ▼
                                                 ScenarioEvaluation (FEASIBLE끼리만 비교)
```

| 역할 | 범위 |
|---|---|
| 파서·데이터 통합 담당 | PlanningInput 생성(E10 승인 데이터), 계약 검증, 제약 판정 공통 모듈, 통합 인터페이스 |
| 예측·최적화 담당 | ForecastResult, PlanCandidate 생성(규칙·최적화 모델), OR-Tools 사용 여부 제안 |
| 검색·에이전트 담당 | 입력 데이터의 검색·추출 후보 (E10 경유) |
| 도메인·KPI 담당 | HardConstraint 목록·필수 납기 정의, Soft Objective(KPI)와 가중치 |

(공개 저장소 규칙에 따라 실명 대신 역할명으로 쓴다.)

## 2. 입력 데이터 (PlanningInput)

| 항목 | 출처 (E10 모의 ERP / E01) | 필드 |
|---|---|---|
| 주문 | SalesOrder | order_id, product_id, order_qty, unit, due_date, priority, status |
| 수요예측값 | ForecastResult (예측·최적화 담당) | §3.2 |
| 완제품 재고 | Inventory (item_type = PRODUCT) | on_hand_qty, allocated_qty, on_order_qty, expected_receipt_date |
| 안전재고 | ProductMaster·MaterialMaster | safety_stock_qty |
| BOM | BOMHeader·BOMLine | 버전 선택 규칙(schema §3.6) 적용 후 1개 버전 |
| 자재 재고 | Inventory (item_type = MATERIAL) | 위와 같음 |
| 생산능력 | ProductionCapacity·Routing | regular/overtime_hours_per_day, run_time_per_unit_h, setup_time_h |
| 납기 | SalesOrder.due_date + 필수 여부(HardConstraint) | — |
| 조달 리드타임 | SupplierItem (is_preferred) | lead_time_days, min_order_qty |
| 비용 및 제약 | 자재 unit_cost, 자원 cost_per_hour·overtime_cost_per_hour, 외주 단가·외주처 조건 | 외주처 조건은 E01에서 합성 가정(`parameters.outsourcers`) |

## 3. 데이터 계약 (필수·선택, 타입)

타입 표기: `string`, `date`(ISO YYYY-MM-DD), `decimal`(10진 문자열 — 부동소수점 금지), `integer`, `boolean`, `enum`. 모든 수량은 품목 기준 단위로 환산한 값과 단위를 함께 둔다.

### 3.1 PlanningInput

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| input_id | string | 필수 | — |
| dataset_ref | {source: string, sha256: string} | 필수 | 승인된 모의 ERP 스냅샷 또는 E01 정답셋 해시 |
| reference_date | date | 필수 | 기준일 |
| horizon | {start: date, end: date, grain: enum(WEEK, DAY)} | 필수 | 계획 기간 |
| orders | Order[] | 필수 | §2 필드 |
| inventory | InventoryItem[] | 필수 | — |
| items | Item[] (product/material, base_unit, safety_stock_qty) | 필수 | — |
| boms | {product_id, bom_id, lines[]}[] | 필수 | 선택된 버전만 |
| capacity | {resource_id, regular_hours_per_day, overtime_hours_per_day_max, unit: "h"}[] | 필수 | — |
| routings | {product_id, sequence_no, resource_id, run_time_per_unit_h, setup_time_h}[] | 필수 | — |
| supply | {material_id, supplier_id, lead_time_days, min_order_qty, is_preferred}[] | 필수 | — |
| costs | {item_or_resource_id, cost_type: enum, value: decimal, currency: "KRW"}[] | 선택 | 없으면 비용 지표는 `미산정` |
| unverified_facts | {fact, reason}[] | 필수 | 확인되지 않은 조건 목록 (예: 외주 가능성). 비어 있지 않으면 해당 조건에 의존하는 계획은 FEASIBLE이 될 수 없다 |

### 3.2 ForecastResult

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| forecast_id | string | 필수 | — |
| model | {name, version} | 필수 | 예측·최적화 담당 모델 |
| product_id | string | 필수 | — |
| period_start | date | 필수 | — |
| quantity | decimal | 필수 | 점 예측 |
| unit | string | 필수 | — |
| interval | {lower: decimal, upper: decimal, level: decimal} | 선택 | 모델이 실제로 낸 경우만 |
| training_data_ref | string | 필수 | 학습 데이터 출처 (SalesHistory 등) |

### 3.3 HardConstraint

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| constraint_id | string | 필수 | 예: HC-CAP, HC-MAT, HC-DUE, HC-DATA |
| kind | enum(CAPACITY, MATERIAL_SUPPLY, MANDATORY_DUE_DATE, OUTSOURCING, BUSINESS_RULE, DATA_VALIDITY) | 필수 | [제약 정책 §2](e11_constraint_policy.md) |
| scope | {product_id?, resource_id?, material_id?, order_id?, period?} | 필수 | — |
| limit | decimal \| null | 선택 | 수치 한도가 있는 경우 |
| source | string | 필수 | 근거 (모의 ERP 필드, 도메인 규칙 문서 등) |
| verified | boolean | 필수 | 근거가 확인된 제약인가 (false면 정책 §4) |

### 3.4 ScenarioConfig

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| scenario_id | string | 필수 | — |
| plan_style | enum(BASELINE, COST_FIRST, DUE_FIRST, SAFETY_STOCK_FIRST) | 필수 | 실제 비교는 2~3개로 제한 (§4) |
| demand_source | enum(ORDERS, FORECAST, MAX_ORDERS_FORECAST) | 필수 | decision_logic §1 |
| include_safety_stock | boolean | 필수 | — |
| allow_overtime | boolean | 필수 | — |
| allow_outsourcing | boolean | 필수 | 허용해도 외주 조건이 미확인이면 FEASIBLE 불가 |
| soft_weights | {objective: weight}[] | 선택 | Soft Objective 가중치 (도메인·KPI 담당) |

### 3.5 PlanCandidate

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| plan_id | string | 필수 | — |
| scenario_id | string | 필수 | — |
| generated_by | enum(RULE, OPTIMIZER, MANUAL) | 필수 | E01 ProductionPlan.generated_by와 같은 값 |
| lines | {product_id, period_start, planned_qty, unit, production_mode: enum(INHOUSE, OUTSOURCE), resource_id?}[] | 필수 | E01 ProductionPlanLine과 같은 구조 |
| procurement | {material_id, qty, unit, order_date, expected_receipt_date}[] | 선택 | — |
| assumptions | string[] | 필수 | 계획이 의존하는 가정 (unverified_facts 참조) |

### 3.6 ConstraintViolation

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| plan_id | string | 필수 | — |
| constraint_id | string | 필수 | — |
| kind | enum | 필수 | HardConstraint.kind |
| status | enum(VIOLATED, UNVERIFIED) | 필수 | VIOLATED = 한도 초과 확인, UNVERIFIED = 판정에 필요한 사실 미확인 |
| measured | decimal \| null | 선택 | 예: 필요 생산량 |
| limit | decimal \| null | 선택 | 예: 정규 능력 |
| shortfall | decimal \| null | 선택 | 예: 100 |
| unit | string \| null | 선택 | — |
| evidence | object | 필수 | 계산 근거 |

### 3.7 ScenarioEvaluation

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| plan_id | string | 필수 | — |
| feasibility | enum(FEASIBLE, INFEASIBLE, UNVERIFIED) | 필수 | [제약 정책 §3](e11_constraint_policy.md) |
| violations | ConstraintViolation[] | 필수 | — |
| soft_scores | {objective, value: decimal \| "미산정"}[] | FEASIBLE일 때만 | 비용·납기 여유·재고 등 |
| rank | integer \| null | 선택 | FEASIBLE 계획끼리만 순위. INFEASIBLE·UNVERIFIED는 null |
| comparable | boolean | 필수 | FEASIBLE일 때만 true |

## 4. 계획안 (비교는 2~3개로 제한)

| 계획 스타일 | 설명 | 이번 비교 대상 | E01 대응 |
|---|---|---|---|
| BASELINE 기준형 | 정규 생산능력만 | 예 | PLAN-REG |
| DUE_FIRST 납기 우선형 | 잔업 허용 (외주는 조건 확인 시) | 예 | PLAN-OT |
| COST_FIRST 비용 우선형 | 외주 포함 최소 비용 (필수 납기는 Hard) | 예 | PLAN-OUT |
| SAFETY_STOCK_FIRST 안전재고 우선형 | 안전재고 보충 우선 | 아니오 (후속) | — |

E01 정답셋의 세 계획안(`expected.plan_evaluation`)이 이미 같은 입력으로 독립 계산되어 있으므로, E11 1차 평가의 Baseline 정답으로 재사용한다 (값 변경 없음).

## 5. 필수 테스트 시나리오 — 독립 계산 정답 (T-01)

decision_logic.md §1~§3의 업무분장 예시와 같은 수치. 모든 값은 수계산으로 정했고 어떤 구현의 출력도 쓰지 않았다. 가정: 단일 제품·단일 자재·단일 기간, 완제품 할당·입고예정 0, 자재 할당·입고예정·안전재고 0, 손실률 0.

| 단계 | 식 | 정답 |
|---|---|---|
| 필요 생산량 | max(0, 수요 1,000 + 안전재고 100 − 완제품 재고 200) | **900개** |
| 필요 자재 | 900개 × 2 kg/개 | **1,800 kg** |
| 자재 부족량 | max(0, 1,800 − 보유 1,500) | **300 kg** |
| 생산능력 초과 | 900 − 정규 능력 800 | **100개** 초과 |

판정 정답:

| 계획 | 판정 | 이유 |
|---|---|---|
| 정규 생산만 (BASELINE) | **INFEASIBLE** | HC-CAP 위반: 필요 900 > 능력 800 (부족 100개). 자재 300 kg 부족도 조달 조건 없이는 HC-MAT 위반 |
| 추가 100개를 외주·잔업으로 (DUE_FIRST·COST_FIRST) | **UNVERIFIED** — 자동 FEASIBLE 금지 | 외주 가능성·비용·납기·자재 제공 조건이 확인되지 않음 (unverified_facts). 자재 300 kg 조달 리드타임도 미확인 |
| 모든 계획 | 비교 순위 없음 (rank = null) | FEASIBLE 계획이 없으므로 Soft Objective 비교를 하지 않는다 |

정답 위반 예: 외주 단가만 보고 비용 우선형을 "최적 계획"으로 선택하는 출력은 오답이다.

## 6. 미확정

- ERP 자체의 생산계획 계산 기능 유무 (D-036) — 있으면 E11 계획 생성은 비교 대상이 바뀜.
- 필수 납기 정의(모든 주문인가, 우선순위 URGENT만인가) — 도메인·KPI 담당.
- 제품 수량 기준 능력(800개)과 E01의 시간 기준 능력 간 환산 규칙 — Routing 기반 환산을 기본으로 제안, 팀 합의 필요.
- OR-Tools 사용 여부 (조건부 검토, D-035).
