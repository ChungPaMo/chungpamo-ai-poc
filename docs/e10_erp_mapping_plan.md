# E10 모의 ERP 매핑 PoC — 설계

> 작성 2026-10-21. 상태 **RUNNING** — 2026-10-21 1차 실행(최소 검증 코드·평가셋 v1), 결과 [e10_erp_mapping_report.md](e10_erp_mapping_report.md). DEC-20261021-04.
> 관련: [e10_data_contract.md](e10_data_contract.md)(입력·후보·승인 계약), [e10_evaluation_protocol.md](e10_evaluation_protocol.md)(시나리오·정답·지표), [schemas/e10_mock_erp.sql](../schemas/e10_mock_erp.sql)(실행하지 않는 DDL 초안), [configs/e10_mapping_rules.json](../configs/e10_mapping_rules.json)(규칙 초안)

**모의 ERP는 실제 기업 ERP가 아니다.** 수요기업의 ERP 보유 여부·스키마·반입 권한·승인 절차는 확인되지 않았으며(D-036), 아래 구조는 E01 공통 데이터 모델을 ERP 형태로 옮긴 합성 실험 환경이다. 실제 ERP에 쓰는 기능은 설계·구현하지 않는다.

## 1. 목적

파서 출력(공통 IR 0.2)의 값이 모의 ERP 필드로 들어가는 경로에서, 다음이 지켜지는지 실측한다.

1. 후보 탐색(어느 엔터티·필드인가)과 값 검증(값이 맞는가)과 저장 승인(반영해도 되는가)이 분리되어 있다.
2. **잘못된 값이 승인 후 반영되는 비율(Wrong-value Commit Rate)** 이 낮다 — 가장 중요한 안전성 지표.
3. 승인되지 않은 데이터는 본 테이블에 들어가지 않는다.
4. 같은 원본을 다시 반입해도 중복 레코드가 생기지 않는다.
5. 반영된 모든 값은 원본 파일·위치까지 추적된다.

## 2. 모의 ERP 데이터 구조 (E01 정답셋 v2 재사용)

E01 스키마([manufacturing_data_schema.md](manufacturing_data_schema.md) §3, `scripts/e01_models.py`)를 확인하고 대응시켰다. 필드명·타입·단위·ID는 E01 그대로 쓴다. **E01에 없는 값은 만들지 않는다.**

| 모의 ERP 엔터티 | E01 엔터티 | 키 | 주요 필드 (E01 필드명) | 비고 |
|---|---|---|---|---|
| ProductMaster | Product | product_id | product_name, product_type, base_unit, safety_stock_qty, manuf_lead_time_days, outsourcing_allowed, outsourcing_unit_cost | — |
| MaterialMaster | Material | material_id | material_name, base_unit, unit_cost, safety_stock_qty | — |
| SupplierMaster | Supplier | supplier_id | supplier_name | — |
| SupplierItem | SupplierMaterial | (supplier_id, material_id) | lead_time_days, min_order_qty, is_preferred | 요청 목록에 없으나 리드타임(E11 입력)이 여기에만 있어 포함 |
| UnitMaster | Unit | unit_code | dimension, base_unit_code, to_base_factor | 단위 불일치 검증에 필요 |
| BOMHeader | BOM | bom_id | product_id, bom_version, status, is_active, valid_from, valid_to, min_qty, max_qty, site_id, base_qty | 버전·유효기간·수량 구간 그대로 |
| BOMLine | BOMLine | (bom_id, line_no) | component_type, component_material_id, component_product_id, qty_per, unit, scrap_rate, line_type | — |
| Order (DDL 테이블명 SalesOrder) | Order | order_id | product_id, order_qty, unit, order_date, due_date, priority, status | "Order"는 SQL 예약어라 DDL에서는 SalesOrder |
| Inventory | Inventory | (item_type, item_id, as_of_date) | on_hand_qty, allocated_qty, on_order_qty, expected_receipt_date, unit | — |
| ProductionCapacity | Resource | resource_id | resource_name, resource_type, regular_hours_per_day, overtime_hours_per_day_max, cost_per_hour, overtime_cost_per_hour | **E01 능력은 시간(h/일) 단위**. 제품 수량 기준 능력(예: 800개/기간)은 E01에 없음 → E11 필수 시나리오의 800개는 시나리오 전용 합성값 |
| Routing | Operation | operation_id | product_id, sequence_no, resource_id, run_time_per_unit_h, setup_time_h | 시간 능력 → 수량 환산에 필요 |

ERP 본 테이블에 넣지 않는 E01 엔터티: ProductionPlan·ProductionPlanLine(계획 결과 — E11 출력), SalesHistory(예측 입력 — E11 ForecastResult 쪽).

필요한 합성값은 별도 가정으로 둔다 (실제 존재하는 값처럼 쓰지 않음):

| 가정 ID | 내용 | 사용처 |
|---|---|---|
| E10-ASM-01 | 업체 코드 → 사내 코드 대응표는 E02 설정(`configs/e02_vendor_mapping.json` `codes`)을 사내 기준정보로 간주 | 규칙 기반 매핑 |
| E10-ASM-02 | 승인자는 역할 코드(`REVIEWER_A` 등)로만 표기, 실명·계정 없음 | ApprovalLog |
| E10-ASM-03 | 단일 사이트(site_id = null), 통화 KRW | 전체 |

## 3. 승인 대기 구조 (staging)

```
IR(파서 출력) ─► ImportBatch ─► MappingCandidate ─► ValidationIssue
                                     │ (검증 통과/실패)
                                     ▼
                               StagingRecord ──(ApprovalLog: APPROVED)──► 모의 ERP 본 테이블
                                     │                                     (resulting_record_id)
                                     └──(REJECTED / 승인 없음)──► 반영 안 됨
```

| 테이블 | 역할 |
|---|---|
| ImportBatch | 반입 단위. 원본 파일 sha256·파서명·문서 버전·dry-run 여부. 같은 sha256 재반입 탐지 |
| MappingCandidate | 원본 값 1개 → (엔터티, 필드, 값) 후보. 생성 방식(matching_method), 검증 상태, 검토 필요 여부 |
| ValidationIssue | 후보별 검증 오류 (E05 규칙 ID 재사용) |
| StagingRecord | 후보들을 모은 레코드 단위 변경안 (INSERT/UPDATE, 변경 전·후 값) |
| ApprovalLog | 승인·반려 기록. 승인자·시각·반려 사유·반영된 레코드 ID |

원칙: **승인 이전에는 staging만 허용**한다. DDL 초안은 본 테이블 INSERT·UPDATE에 승인 기록(APPROVED) 존재를 트리거로 요구한다. dry-run 반입은 승인 대상이 아니며 변경 전·후 비교만 낸다.

## 4. 평가 시나리오 (요약)

정답·판정 기준 상세는 [e10_evaluation_protocol.md](e10_evaluation_protocol.md) §3. 각 시나리오는 E01 정답셋에서 독립적으로 정답을 만들 수 있도록 정의했다.

| ID | 시나리오 | 기대 처리 |
|---|---|---|
| M01 | 정확한 제품코드 | 자동 매핑 후보, 검증 통과 |
| M02 | 유사 제품명 (예: "가정용히터A") | 후보 제시, 검토 필요 |
| M03 | 동일 명칭의 서로 다른 제품 | 자동 확정 금지, 검토 필요 |
| M04 | 잘못된 제품코드 | 매핑 실패 또는 반려 |
| M05 | 단위 불일치 | 검증 오류(ERR-UNIT), 반영 금지 |
| M06 | 수량 오류 | 검증 오류, 반영 금지 |
| M07 | 중복 주문 | 중복 탐지 |
| M08 | 구버전 BOM | 현재 유효 버전과 구분, 덮어쓰기 금지 |
| M09 | 유효기간 충돌 | 검증 오류(ERR-BOMVER) |
| M10 | 참조 대상 누락 | 검증 오류(ERR-BADREF) |
| M11 | 재반입 시 중복 | 같은 원본 재반입 → 신규 레코드 0 |
| M12 | 승인되지 않은 데이터 반영 시도 | 본 테이블 변경 0 |

## 5. 비교 방식과 공통 인터페이스

| 방식 | 이번 범위 |
|---|---|
| 1. 규칙 기반 매핑 (Baseline) | 규칙 초안만 작성 (`configs/e10_mapping_rules.json`) |
| 2. BM25·키워드 검색 | 인터페이스만 |
| 3. 임베딩 검색 | 인터페이스만 (외부 API 사용 시 승인 필요) |
| 4. Tri-CHEF | 인터페이스만 — **구현은 검색·에이전트 담당 범위** |
| 5. LLM 매핑 후보 제안 | 인터페이스만 (외부 API 사용 시 승인 필요, 합성 데이터만) |

모든 방식은 같은 입력(`MappingInput`, [데이터 계약 §1](e10_data_contract.md))을 받고 같은 출력(`MappingCandidate` 목록)을 낸다. 방식은 **후보만** 만들고, 검증·승인 단계는 방식과 무관하게 공통이다. 방식별 점수(`score`)는 그 방식이 실제로 점수를 내는 경우에만 채우고, 임의 신뢰도를 만들지 않는다.

## 6. 평가 지표 (정의는 평가 프로토콜 §4)

Field Mapping Accuracy, Wrong-field Mapping Rate, **Wrong-value Commit Rate**, Duplicate Detection Rate, Auto-accept Coverage, Manual Review Rate, Rejection Accuracy, 처리시간, API 비용, 원본 추적 가능률. 목표값은 모두 `팀 합의 필요`(D-010).

## 7. 재사용

| 재사용 | 출처 |
|---|---|
| 정답 기준 데이터 | `data/canonical/ground_truth_v2.json` (변경 없음) |
| 업체 헤더·코드 대응 | `configs/e02_vendor_mapping.json` (참조만) |
| 파서 출력 형식 | 공통 IR 0.2 ([intermediate_representation.md](intermediate_representation.md), 변경 없음) |
| 값 검증 규칙 | E05 카탈로그 `configs/e05_validation_rules.json`, `scripts/e05_validate_python.py` / `e05_validate_sql.py` (변경 없음) |
| 채점 방식 | E05 `scripts/e05_score.py`의 판정 구분(정확·부분·오탐·미탐) 개념 |

## 8. 범위 밖

실제 ERP 접근·쓰기, ERP 공식 API 연동(조건부 검토), 웹 UI·FastAPI, Tri-CHEF·LLM 구현, 대량 데이터 성능.
