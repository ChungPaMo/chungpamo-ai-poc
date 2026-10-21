# E05 검증 규칙 카탈로그 v1

> 원본: `configs/e05_validation_rules.json` (이 문서는 그 JSON을 표로 옮긴 것이다. 두 내용이 다르면 JSON이 기준). 작성 2026-10-21.

## 1. 원칙

- 기존 문서(schema §3·§5, evaluation_protocol §2.4, decision_logic, E01 모델·GT 가정)에 근거가 있는 규칙만 **ERROR**로 둔다.
- 근거가 없지만 실험상 확인해 볼 만한 규칙은 `synthetic_assumption = true`로 표시하고 **WARNING**으로만 둔다. 이는 **합성 실험용 가정이며 실제 기업 규칙이 아니다.**
- 근거도 없고 검증 방법도 정할 수 없는 항목은 규칙을 만들지 않고 **NOT_MEASURED**로 남긴다 (§4).
- V13(생산능력 초과)은 정상 데이터에도 의도적으로 존재하는 계산 결과이므로 **INFO**로 두고 정확도 채점에서 제외, GT `expected.plan_evaluation`과 값으로 대조한다.
- 오류 코드 ERR-ENUM·ERR-IDFMT는 프로토콜 §2.4에 없어서 E05에서 추가했다 — **팀 확인 필요**.
- B12 허용오차 0.0005는 실험 설정값이다(근거 문서 없음, 팀 합의 필요).

## 2. 요약

- 실행 규칙 42개 (채점 대상 41개 + INFO 1개), NOT_MEASURED 6개
- 계층별: schema 8, referential 7, relational 14, business 13
- 심각도별: ERROR 36, WARNING 5, INFO 1
- 합성 가정 규칙: S07, B09, B10, V11, V12
- SHACL 적합도(설계 추정, E06에서 확인): CORE 20, SPARQL 15, PARTIAL 6, NOT_SUITABLE 1

## 3. 규칙

| ID | 계층 | 대상 | 설명 | 오류 코드 | 심각도 | Python 방법 | SQL 방법 | 입력 필드 | 기대 결과 | 근거 | 합성 가정 | SHACL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | schema | 모든 엔터티 | 필수 필드 누락 (null 또는 빈 문자열) | ERR-MISSING | ERROR | pydantic 필수 필드(missing·None) + 빈 문자열 사전 검사 | 필수 열 IS NULL OR = '' | 엔터티별 필수 필드 (schema §3 필수=Y) | 레코드·필드 단위 보고 | SCHEMA §3 필수 열, MODEL 필수 필드, PROTOCOL ERR-MISSING | 아니오 | CORE |
| S02 | schema | 숫자 필드 | 숫자 형식 오류 (decimal·integer로 해석 불가) | ERR-NUMFMT | ERROR | pydantic Decimal/int 변환 실패 | CAST 왕복 비교·GLOB 숫자 패턴 | decimal·integer 필드 | 레코드·필드 | SCHEMA §5 ERR-NUMFMT, MODEL 타입 | 아니오 | CORE |
| S03 | schema | 날짜 필드 | 날짜 형식 오류·존재하지 않는 날짜 (QR-04 ①) | ERR-DATE | ERROR | pydantic date 변환 실패 (ISO YYYY-MM-DD) | date(x) = x (SQLite date()는 2026-02-30을 2026-03-02로 바꾸므로 왕복 비교 필수) | date 필드 | 레코드·필드 | SCHEMA §5 QR-04 ① | 아니오 | CORE |
| S04 | schema | 열거형 필드 | 허용되지 않은 열거값 (대소문자 포함 완전 일치) | ERR-ENUM | ERROR | pydantic Literal | NOT IN (허용값) | product_type, status, component_type, priority, item_type, resource_type, generated_by, production_mode, dimension, period_grain, generation_method, origin_class, line_type | 레코드·필드 | SCHEMA §3 enum, MODEL Literal | 아니오 | CORE |
| S05 | schema | 모든 엔터티 | record_uid 형식 오류 (^rec_[0-9a-f]{16}$) | ERR-IDFMT | ERROR | pydantic pattern | GLOB 'rec_' + 16자리 16진수 | record_uid | 레코드·필드 | MODEL _Base.record_uid 패턴 | 아니오 | CORE |
| S06 | schema | 수량·비율 필드 | 숫자 범위 위반 (소요량·주문량·기준수량 > 0, 그 밖 수량 ≥ 0, 손실률 0 이상 1 미만, 배분 비율 0 초과 1 이하) | ERR-NUMFMT | ERROR | pydantic gt/ge/lt/le | CHECK 조건과 같은 WHERE | qty_per, order_qty, base_qty, min_qty, unit_cost, safety_stock_qty, lead_time_days, scrap_rate, allocation_share, regular_hours_per_day, run_time_per_unit_h, planned_qty 등 (재고 보유 수량은 V01) | 레코드·필드 | SCHEMA §3 키·관계 열, MODEL Field 제약 | 아니오 | CORE |
| S07 | schema | 선택 문자열 필드 | 선택 필드에 빈 문자열 (null이어야 함) | ERR-MISSING | WARNING | 사전 검사 | = '' | site_id, valid_to, source_series_id 등 선택 필드 | 레코드·필드 경고 | 합성 가정: 빈 문자열과 null을 구분하는 규칙은 기존 문서에 없음 | 예 | CORE |
| S08 | schema | 모든 엔터티 (Inventory 제외) | 업무 키 중복 (QR-01) — 단일 키 또는 복합 키(BOMLine bom_id+line_no, SupplierMaterial, SalesHistory, Operation, PlanLine) | ERR-DUPID | ERROR | 키별 그룹 개수 | GROUP BY 키 HAVING COUNT(*) > 1 (PK 제약 대신 사전 집계) | 엔터티별 PK | 관련 레코드 전부, 필드 * | SCHEMA §3 PK, §5 QR-01 | 아니오 | SPARQL |
| R01 | referential | BOM, BOMLine, Order, Operation, ProductionPlanLine, SalesHistory, Inventory(PRODUCT) | 존재하지 않는 제품 참조 (QR-02) | ERR-BADREF | ERROR | ID 집합 조회 | LEFT JOIN … IS NULL | product_id, component_product_id, item_id | 참조 레코드, FK 필드 | SCHEMA §3 FK, §5 QR-02 | 아니오 | PARTIAL |
| R02 | referential | BOMLine, SupplierMaterial, Inventory(MATERIAL) | 존재하지 않는 자재 참조 (QR-02) — 매핑되지 않은 외부(업체) 코드 포함 | ERR-BADREF | ERROR | ID 집합 조회 | LEFT JOIN … IS NULL | component_material_id, material_id, item_id | 참조 레코드, FK 필드 | SCHEMA §5 QR-02 | 아니오 | PARTIAL |
| R03 | referential | SupplierMaterial | 존재하지 않는 공급사 참조 (QR-02) | ERR-BADREF | ERROR | ID 집합 조회 | LEFT JOIN … IS NULL | supplier_id | 참조 레코드, FK 필드 | SCHEMA §3.5 FK, §5 QR-02 | 아니오 | PARTIAL |
| R04 | referential | BOMLine | 존재하지 않는 BOM 참조 | ERR-BADREF | ERROR | ID 집합 조회 | LEFT JOIN … IS NULL | bom_id | 참조 레코드, FK 필드 | SCHEMA §3.7 FK→BOM | 아니오 | PARTIAL |
| R05 | referential | Operation, ProductionPlanLine | 존재하지 않는 생산 자원 참조 (QR-08 ①) | ERR-RESREL | ERROR | ID 집합 조회 | LEFT JOIN … IS NULL | resource_id | 참조 레코드, resource_id | SCHEMA §5 QR-08 ①, §3.13 FK→Resource | 아니오 | PARTIAL |
| R06 | referential | ProductionPlanLine | 존재하지 않는 계획 참조 | ERR-BADREF | ERROR | ID 집합 조회 | LEFT JOIN … IS NULL | plan_id | 참조 레코드, plan_id | SCHEMA §3.13 FK→Plan | 아니오 | PARTIAL |
| R07 | referential | 단위 필드가 있는 엔터티 | 단위가 Unit 목록에 없음 (QR-03 ①) | ERR-UNIT | ERROR | Unit 코드 집합 조회 | LEFT JOIN Unit | unit, base_unit, base_unit_code | 레코드, 단위 필드 | SCHEMA §5 QR-03 ① | 아니오 | CORE |
| B01 | relational | BOM·BOMLine | 다단계 BOM 순환 (자기 참조 포함, QR-05) | ERR-BOMCYCLE | ERROR | 제품→반제품 그래프 깊이 우선 탐색 | 재귀 CTE 경로 전개, 출발 제품 재등장 | BOM.product_id, BOMLine.component_product_id | 순환 경로의 BOMLine 레코드 전부 | SCHEMA §5 QR-05 | 아니오 | SPARQL |
| B02 | relational | BOM | 같은 제품의 활성·승인 버전 유효 조건 중복 (기간·수량·사이트 동시 겹침, QR-06 ①) | ERR-BOMVER | ERROR | 제품별 버전 쌍 비교 | 자기 조인 + schema §5 판정식 | valid_from, valid_to, min_qty, max_qty, site_id | 충돌 BOM 레코드 전부 | SCHEMA §5 QR-06 ① 판정식 (종료일 포함, 수량 상한 미포함) | 아니오 | SPARQL |
| B03 | relational | BOM | 미승인(DRAFT) 버전이 활성 (QR-06 ②) | ERR-BOMVER | ERROR | pydantic model_validator | is_active AND status <> 'APPROVED' | status, is_active | 레코드 | SCHEMA §3.6 S1 ②③, §5 QR-06 ② | 아니오 | CORE |
| B04 | relational | BOM | 같은 제품·버전 표기 중복 (QR-06 ③, UK product_id+bom_version) | ERR-BOMVER | ERROR | 그룹 개수 | GROUP BY product_id, bom_version | product_id, bom_version | 관련 레코드 | SCHEMA §3.6 UK, §5 QR-06 ③ | 아니오 | SPARQL |
| B05 | relational | BOM | 유효 조건 자체 오류: valid_to < valid_from, max_qty ≤ min_qty (QR-04 ③, QR-06 ④) | ERR-BOMVER | ERROR | pydantic model_validator | 비교 조건 | valid_from, valid_to, min_qty, max_qty | 레코드, 조건 필드 | SCHEMA §5 QR-06 ④ | 아니오 | CORE |
| B06 | relational | ProductionPlanLine(INHOUSE) | 계획 라인의 (제품, 기간 시작일, 계획 수량)에 적용 가능한 활성 BOM이 0개(선택 불가) 또는 2개 이상(모호) (QR-06 ⑤, BOM 선택 규칙) | ERR-BOMVER | ERROR | BOM 선택 규칙 적용 | 계획 라인 × BOM 후보 조인 집계 | plan line product_id, period_start, planned_qty; BOM 유효 조건 | 계획 라인 레코드 | SCHEMA §3.6 BOM 버전 선택 규칙, GT parameters.plan_bom_selection_date=period_start | 아니오 | SPARQL |
| B07 | relational | BOMLine | component_type과 구성품 ID 열 불일치 | ERR-BADREF | ERROR | pydantic model_validator | 조건식 | component_type, component_material_id, component_product_id | 레코드 | SCHEMA §3.7 조건부 FK, MODEL BOMLine._component | 아니오 | CORE |
| B08 | relational | BOMLine, Order, Inventory, ProductionPlanLine | 수량 단위의 차원이 품목 기준 단위 차원과 다름 (예: kg 자재에 EA, QR-03 ②). 같은 차원 다른 단위(g↔kg)는 정상 | ERR-UNIT | ERROR | Unit.dimension 비교 | Unit 두 번 조인해 dimension 비교 | unit, 품목 base_unit | 레코드, unit | SCHEMA §3.7 unit 열, §5 QR-03 ② | 아니오 | SPARQL |
| B09 | relational | BOM | 라인이 하나도 없는 BOM (구성품 누락) | ERR-BOMVER | WARNING | BOM별 라인 수 | NOT EXISTS | BOM.bom_id, BOMLine.bom_id | BOM 레코드 경고 | 합성 가정: BOM 1—N BOMLine의 최소 개수(N≥1)는 기존 문서에 명시되지 않음 | 예 | CORE |
| B10 | relational | BOMLine | 같은 BOM 안에 같은 구성품이 두 번 이상 | ERR-DUPID | WARNING | 그룹 개수 | GROUP BY bom_id, 구성품 | bom_id, component_*_id | 라인 레코드 경고 | 합성 가정: 기존 문서에 금지 규칙 없음 (실무에서는 정상일 수도 있음) | 예 | SPARQL |
| B11 | relational | SupplierMaterial | 자재당 우선 공급사(is_preferred=TRUE)가 정확히 1개가 아님 (공급 관계가 있는 자재 기준) | ERR-DUPID | ERROR | 자재별 개수 | GROUP BY material_id HAVING SUM(is_preferred) <> 1 | material_id, is_preferred | 해당 자재의 공급 관계 레코드 | SCHEMA §3.5 is_preferred '자재당 TRUE 1개', GT 가정 5 (우선 공급사 리드타임 사용) | 아니오 | SPARQL |
| B12 | relational | SalesHistory(ALLOCATED) | 같은 원본 레코드에서 배분한 행들의 allocation_share 합 ≠ 1 (허용오차 0.0005) | ERR-NUMFMT | ERROR | 원본별 합계 | GROUP BY derived_from_record_uid | derived_from_record_uid, allocation_share | 해당 원본에서 나온 행 전부 | SCHEMA §3.9 allocation_share 합 = 1 | 아니오 | SPARQL |
| B13 | relational | SalesHistory | ALLOCATED 행에 원본 레코드·배분 비율 없음 | ERR-MISSING | ERROR | pydantic model_validator | 조건식 | generation_method, derived_from_record_uid, allocation_share | 레코드 | SCHEMA §3.9 조건부 필수, MODEL SalesHistory._allocation | 아니오 | CORE |
| B14 | relational | Product | 외주 단가는 외주 허용 제품에만 있음 | ERR-MISSING | ERROR | pydantic model_validator | 조건식 | outsourcing_allowed, outsourcing_unit_cost | 레코드 | MODEL Product._outsourcing | 아니오 | CORE |
| V01 | business | Inventory | 음수 보유 재고 (QR-07 ①) | ERR-INVQTY | ERROR | pydantic ge=0 | on_hand_qty < 0 | on_hand_qty | 레코드, on_hand_qty | SCHEMA §5 QR-07 ① | 아니오 | CORE |
| V02 | business | Inventory | 할당 수량 > 보유 수량 (QR-07 ②, 사용 가능 재고 음수) | ERR-INVQTY | ERROR | pydantic model_validator | allocated_qty > on_hand_qty | allocated_qty, on_hand_qty | 레코드, allocated_qty | SCHEMA §5 QR-07 ②, E02→E05 이관 E01-ERR-012 | 아니오 | CORE |
| V03 | business | Inventory | 단위가 EA인데 소수 수량 (QR-07 ③) | ERR-INVQTY | ERROR | Decimal 정수 여부 | CAST 비교 | unit, on_hand_qty, allocated_qty, on_order_qty | 레코드, 수량 필드 | SCHEMA §5 QR-07 ③ | 아니오 | SPARQL |
| V04 | business | Inventory | 같은 품목·기준일 재고 중복 (QR-07 ④) | ERR-INVQTY | ERROR | 키별 그룹 | GROUP BY item_type, item_id, as_of_date | item_type, item_id, as_of_date | 관련 레코드, 필드 * | SCHEMA §3.10 PK, §5 QR-07 ④ | 아니오 | SPARQL |
| V05 | business | Inventory | 입고 예정 수량 > 0인데 입고 예정일 없음 (QR-04 ⑤) | ERR-DATE | ERROR | pydantic model_validator | on_order_qty > 0 AND expected_receipt_date IS NULL | on_order_qty, expected_receipt_date | 레코드, expected_receipt_date | SCHEMA §5 QR-04 ⑤ | 아니오 | CORE |
| V06 | business | Inventory | 재고 기준일 > 데이터셋 기준일(reference_date) (QR-04 ④) | ERR-DATE | ERROR | 날짜 비교 | as_of_date > :reference_date | as_of_date, parameters.reference_date | 레코드, as_of_date | SCHEMA §5 QR-04 ④, GT parameters.reference_date | 아니오 | CORE |
| V07 | business | Order | 납기일 < 주문일 (QR-04 ②) | ERR-DATE | ERROR | pydantic model_validator | due_date < order_date | order_date, due_date | 레코드, due_date | SCHEMA §5 QR-04 ②, E02→E05 이관 E01-ERR-009 | 아니오 | CORE |
| V08 | business | Order(OPEN), ProductionPlanLine(INHOUSE) | 주문·자체 생산 계획 대상 제품에 공정(Operation)이 없음 (QR-08 ②) | ERR-RESREL | ERROR | 제품별 공정 존재 | NOT EXISTS | product_id, Operation.product_id | 주문·계획 라인 레코드, product_id | SCHEMA §5 QR-08 ② | 아니오 | SPARQL |
| V09 | business | ProductionPlanLine(INHOUSE) | 계획 라인의 자원이 그 제품 공정에 없는 자원 (QR-08 ③) | ERR-RESREL | ERROR | 제품별 공정 자원 집합 | NOT EXISTS (Operation product+resource) | product_id, resource_id | 계획 라인, resource_id | SCHEMA §3.13 resource_id, §5 QR-08 ③ | 아니오 | SPARQL |
| V10 | business | ProductionPlanLine | 외주 라인에 자원이 있거나 자체 생산 라인에 자원이 없음 (QR-08 ④의 v2 형태) | ERR-RESREL | ERROR | pydantic model_validator | 조건식 | production_mode, resource_id | 계획 라인, resource_id | MODEL ProductionPlanLine._mode, SCHEMA §3.13 | 아니오 | CORE |
| V11 | business | ProductionPlanLine(OUTSOURCE) | 외주 불가 제품(outsourcing_allowed=false)의 외주 라인 | ERR-RESREL | WARNING | 제품 속성 조회 | 조인 조건 | production_mode, Product.outsourcing_allowed | 계획 라인 경고 | 합성 가정: outsourcing_allowed 필드는 있으나 계획 라인과의 제약은 문서에 명시되지 않음 | 예 | SPARQL |
| V12 | business | ProductionPlanLine | 계획 라인 기간 시작일이 계획 기간(horizon) 밖 | ERR-DATE | WARNING | 날짜 비교 | BETWEEN | period_start, horizon_start, horizon_end | 계획 라인 경고 | 합성 가정: 라인 날짜와 계획 기간의 관계는 문서에 명시되지 않음 | 예 | SPARQL |
| V13 | business | ProductionPlan × Resource × 주 | 자원·주별 필요시간이 가용시간을 넘음 (생산능력 초과 — 계획 평가 결과, 데이터 오류 아님) | CAPACITY_EXCEEDED | INFO | 자체 생산 라인마다 제품의 모든 공정 (수량×단위 가공시간 + 준비시간) 합, 가용 = 정규×5 (+잔업안 잔업최대×5) | 조인·GROUP BY 집계 | ProductionPlanLine, Operation, Resource, ProductionPlan.overtime_allowed | GT expected.plan_evaluation.capacity와 자원·주별 필요시간·초과시간 일치 | LOGIC §4 ② CAPACITY_EXCEEDED, §6.1 5절 ②③ | 아니오 | NOT_SUITABLE |

## 4. NOT_MEASURED (규칙을 만들지 않은 항목)

| ID | 항목 | 사유 |
|---|---|---|
| N01 | 업무 ID 형식 (product_id 등의 패턴) | 기존 문서에 형식 정의 없음 — 규칙을 새로 만들지 않음 |
| N02 | 주문 수량 허용 범위(상·하한) | order_qty > 0 외에 허용 범위 정의 없음 (S06이 > 0만 검사) |
| N03 | 납기 실현 가능성(주문별 납기 준수) | decision_logic §4 계산 결과(expected.order_feasibility)이며 데이터 오류 규칙이 아님 — E05 범위 밖, CQ 비교는 E06·E07 |
| N04 | 자재 재고 부족(사용 가능 재고 < 소요량) | 계산 결과(expected.material_shortage)이며 데이터 모순이 아님 — E05 범위 밖 |
| N05 | 공급사–자재 관계의 실무 유효성(계약·단가 등) | 데이터 모델에 정의 없음 |
| N06 | SalesHistory 공개 원본과의 대응 정확성 | 원본 스테이징은 data/raw(Git 제외)이며 E01에서 검증 완료 — E05는 배분 비율 합(B12)만 검사 |

## 5. 메타

- 근거 문서 약어: SCHEMA = docs/manufacturing_data_schema.md (§3 필드 정의, §5 QR-01~QR-08); PROTOCOL = docs/evaluation_protocol.md (§2.4 오류 코드, §4.1 판정); MODEL = scripts/e01_models.py (E01 pydantic 모델, 수정하지 않고 재사용); LOGIC = docs/decision_logic.md (§4·§5·§6.1 계산 규칙); GT = data/canonical/ground_truth_v2.json (dataset.assumptions, expected)
- SHACL 적합도 정의: CORE = SHACL Core로 표현 가능 (schema §5 설계안 기준); SPARQL = SHACL-SPARQL 필요; PARTIAL = 일부만 Core; NOT_SUITABLE = 계산·집계 위주로 SHACL 비교 대상 아님
