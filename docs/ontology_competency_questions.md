# 온톨로지 Competency Questions (CQ) — E01

- 작성일: 2026-10-20 (설계안, 검토 대기)
- 목적: 온톨로지·데이터 모델이 **답해야 하는 질문**을 먼저 정하고, 그 질문에 필요한 개념만 모델에 넣는다. CQ는 Grüninger & Fox(1995)가 제안한 온톨로지 요구사항 정의 방식이며, Noy & McGuinness "Ontology Development 101"(Stanford, 2001)에서도 범위 결정 단계로 사용한다(방법론 참고이며 표준 아님).
- 데이터 정의: [manufacturing_data_schema.md](manufacturing_data_schema.md) / 계산식: [decision_logic.md](decision_logic.md) / 추적: [data_provenance_design.md](data_provenance_design.md)
- 실험 연계: E05(SQL/JSON), E06(RDF/SHACL), E07(GraphDB/SPARQL)에서 **같은 CQ 세트**로 비교한다([evaluation_protocol.md](evaluation_protocol.md) §5.4).

## 0. 표기

- **SQL/JSON**, **RDF/SPARQL**: `가능` / `가능(조건)` — 조건은 비고에 적음. 판단은 설계상 예상이며 E05~E07에서 실제로 확인한다.
- **실데이터**: `없음(합성)` / `부분(공개 파생 가능)` — [data_source_research.md](data_source_research.md) §7 기준.
- **정답 검증**: 정답 원천(canonical JSON)에서 **질의 대상 시스템과 독립된 방법**(별도 Python 계산 또는 수계산)으로 기대 결과를 미리 만들고 비교한다. 오류 관련 CQ는 오류 주입 목록(`injected_errors`)과 대조한다.

## 1. CQ 목록

### 1.1 생산계획 및 생산능력

| CQ ID | 의사결정 목적 | 질문 | 엔터티·관계 | 필요 필드 | 기대 결과 형태 | SQL/JSON | RDF/SPARQL | 실데이터 | 정답 검증 |
|---|---|---|---|---|---|---|---|---|---|
| CQ-01 | 능력 초과 여부 판단 | 계획안 X에서 자원별 필요시간이 가용시간을 넘는 자원과 초과 시간은? | ProductionPlan–ProductionPlanLine–Product–Operation–Resource | planned_qty, run_time_per_unit_h, setup_time_h, regular_hours_per_day, horizon | 표 (resource_id, 필요시간, 가용시간, 초과시간) | 가능 | 가능(조건: 집계·산술은 SPARQL 1.1 집계로 가능, 근무일 계산은 사전 계산값 필요) | 없음(합성) | 독립 계산 기대값과 수치 일치(허용 오차 0, decimal) |
| CQ-02 | 생산 경로 확인 | 제품 P는 어떤 공정 순서로 어떤 자원을 사용하는가? | Product–Operation–Resource | sequence_no, resource_id | 순서 있는 목록 | 가능 | 가능 | 없음(합성) | 정답 원천의 공정 목록과 순서까지 일치 |
| CQ-03 | 설비 장애 영향 분석 | 자원 R을 쓸 수 없으면 영향받는 제품과 OPEN 주문은? (반제품을 거친 간접 영향 포함) | Resource–Operation–Product–BOMLine(상위 제품)–Order | resource_id, component_product_id, order status | 제품 목록 + 주문 목록 | 가능(조건: 간접 영향은 재귀 CTE) | 가능(속성 경로) | 없음(합성) | 기대 집합과 완전 일치 |

### 1.2 BOM과 원자재 소요량

| CQ ID | 의사결정 목적 | 질문 | 엔터티·관계 | 필요 필드 | 기대 결과 형태 | SQL/JSON | RDF/SPARQL | 실데이터 | 정답 검증 |
|---|---|---|---|---|---|---|---|---|---|
| CQ-04 | 구성 확인 | 기준일에 제품 P의 적용 BOM 구성품과 단위당 소요량(단위 포함)은? | Product–BOM(활성·유효)–BOMLine–Material/Product | bom status, is_active, valid_from/to, qty_per, unit, base_qty | 표 (구성품, 소요량, 단위) | 가능 | 가능 | 없음(합성) | 기대 표 완전 일치 |
| CQ-05 | 자재 영향 범위 | 자재 M을 직·간접으로 사용하는 모든 완제품은? | Material←BOMLine–BOM–Product (반제품 경유 재귀) | component ids, product_type | 제품 목록 | 가능(조건: 재귀 CTE) | 가능(속성 경로 `+`) | 없음(합성) | 기대 집합 완전 일치 |
| CQ-06 | 자재 소요 계획 | 기간 H의 생산필요량을 충족하려면 자재별 총소요량(기준 단위)은 얼마인가? | Order–Product–BOM–BOMLine–Material–Unit, Inventory(반제품 차감) | decision_logic §1·§2 입력 전부 | 표 (material_id, 총소요량, 기준 단위) | 가능(조건: 다단계 전개는 재귀 CTE 또는 Python) | 가능(조건: 다단계 수량 곱셈 누적은 SPARQL만으로 어려움 → 수준별 반복 질의 또는 외부 계산 필요 가능성) | 없음(합성) | decision_logic §2 독립 계산값과 일치 |

### 1.3 재고 및 자재 부족

| CQ ID | 의사결정 목적 | 질문 | 엔터티·관계 | 필요 필드 | 기대 결과 형태 | SQL/JSON | RDF/SPARQL | 실데이터 | 정답 검증 |
|---|---|---|---|---|---|---|---|---|---|
| CQ-07 | 생산량 결정 | 기간 H에 제품별 생산필요량은? | Order–Product–Inventory | order_qty, due_date, on_hand, allocated, on_order, safety_stock | 표 (product_id, 생산필요량) | 가능 | 가능(집계) | 부분(수요를 공개 파생으로 쓸 경우) | decision_logic §1 독립 계산값과 일치 |
| CQ-08 | 구매 결정 | 기간 H 계획 기준 부족한 자재와 부족량은? | CQ-06 결과–Inventory | 총소요량, on_hand, allocated, on_order | 표 (material_id, 부족량, 단위) | 가능 | 가능(조건: CQ-06과 동일) | 없음(합성) | decision_logic §3 독립 계산값과 일치 |

### 1.4 공급사·구매 리드타임

| CQ ID | 의사결정 목적 | 질문 | 엔터티·관계 | 필요 필드 | 기대 결과 형태 | SQL/JSON | RDF/SPARQL | 실데이터 | 정답 검증 |
|---|---|---|---|---|---|---|---|---|---|
| CQ-09 | 공급사 선택 | 자재 M을 공급할 수 있는 공급사와 각 리드타임·최소주문량, 우선 공급사는? | Material–SupplierMaterial–Supplier | lead_time_days, min_order_qty, is_preferred | 표 | 가능 | 가능 | 없음(합성) | 기대 표 완전 일치 |
| CQ-10 | 장납기 위험 파악 | 우선 공급사 리드타임이 N일 이상인 자재를 직·간접으로 포함하는 제품은? | Product–BOM–BOMLine–Material–SupplierMaterial | lead_time_days, is_preferred | 제품 목록 (+해당 자재) | 가능(조건: 재귀 CTE) | 가능 | 없음(합성) | 기대 집합 완전 일치 |
| CQ-11 | 지연 영향 분석 | 자재 M 입고가 D일 늦어지면 납기를 못 맞추게 되는 주문은? | Material–BOMLine–Product–Order, Inventory(expected_receipt_date) | decision_logic §4 입력 | 주문 목록 + 사유 | 가능(조건: 계산은 Python 규칙) | 가능(조건: 날짜 연산은 SPARQL 구현체별 차이 → 사전 계산값 필요 가능성) | 없음(합성) | decision_logic §4 독립 판정과 일치 |

### 1.5 납기 및 주문 영향

| CQ ID | 의사결정 목적 | 질문 | 엔터티·관계 | 필요 필드 | 기대 결과 형태 | SQL/JSON | RDF/SPARQL | 실데이터 | 정답 검증 |
|---|---|---|---|---|---|---|---|---|---|
| CQ-12 | 수요 파악 | 기간 H 안에 납기가 있는 OPEN 주문을 제품별로 합하면? | Order–Product | order_qty, unit, due_date, status | 표 (product_id, 수량 합) | 가능 | 가능 | 없음(합성) | 기대 표 일치 |
| CQ-13 | 납기 약속 | 주문 O를 납기 안에 공급할 수 있는가? 아니면 어떤 사유(자재·능력·완료일·데이터)인가? | Order–Product–BOM–Material–SupplierMaterial–Operation–Resource–Inventory | decision_logic §4 입력 전부 | {feasible, reasons[], 예상완료일, 여유일} | 가능(조건: 판정 로직은 Python 규칙) | 가능(조건: 사실 조회까지만, 판정 계산은 외부) | 없음(합성) | 독립 판정 결과·사유 코드 일치 |
| CQ-14 | 계획안 선택 | 계획안들의 비용 항목과 제약 위반 지표는 각각 얼마인가? | ProductionPlan–ProductionPlanLine–Operation–Resource–Material–Order | decision_logic §5 입력 | 계획안 × 지표 비교표 | 가능(조건: 계산은 Python) | 가능(조건: 사실 조회까지만) | 없음(합성) | decision_logic §5 독립 계산값 일치 (미확정 항목은 `미산정` 일치) |

### 1.6 데이터 오류 및 버전 변경

| CQ ID | 의사결정 목적 | 질문 | 엔터티·관계 | 필요 필드 | 기대 결과 형태 | SQL/JSON | RDF/SPARQL | 실데이터 | 정답 검증 |
|---|---|---|---|---|---|---|---|---|---|
| CQ-15 | 데이터 신뢰성 | 같은 업무 ID를 가진 서로 다른 원본 레코드와 각 원본 위치는? | 원본 레코드(record_uid)–source_ref | business_id, record_uid, file/sheet/row | 표 (업무 ID, record_uid 목록, 위치) | 가능(조건: 스테이징 테이블 사용) | 가능(조건: 레코드 노드 계층 사용, [provenance 설계 §3](data_provenance_design.md)) | 없음(합성) | injected_errors(ERR-DUPID)와 대조 |
| CQ-16 | 데이터 신뢰성 | 존재하지 않는 품목·자원을 참조하는 레코드와 원본 위치는? | BOMLine/Order/Operation/Inventory–참조 대상 | FK 필드, record_uid, source_ref | 표 | 가능 | 가능 | 없음(합성) | injected_errors(ERR-BADREF, ERR-RESREL)와 대조 |
| CQ-17 | BOM 변경 관리 | 기준일·생산수량·사이트 조건에서 제품 P에 적용 가능한 활성 BOM 버전이 정확히 1개인가? 아니면 0개(선택 불가)·2개 이상(모호)이며 어떤 조건이 겹치는가? | Product–BOM | bom_version, status, is_active, valid_from/to, min_qty/max_qty, site_id | {후보 수, 충돌 버전 쌍, 겹친 조건} | 가능 | 가능 | 없음(합성) | injected_errors(ERR-BOMVER)와 대조 |
| CQ-18 | BOM 구조 무결성 | BOM에 순환 참조가 있는가? 있다면 경로는? | BOM–BOMLine–Product(반제품) | component_product_id | 경로 목록 | 가능(조건: 재귀 CTE + 순환 감지) | 가능(조건: 경로 반환은 SPARQL만으로 제한적, 순환 존재 여부는 속성 경로로 가능) | 없음(합성) | injected_errors(ERR-BOMCYCLE)와 대조 |
| CQ-19 | 근거 추적 | 이 값(예: BOMLine 소요량)은 어느 파일·시트·행·열에서 왔고 어떤 변환을 거쳤나? | 레코드–source_ref–변환 Activity | record_uid, source_ref, transform_run_id | {파일, 시트, 행, 열, 변환 단계 목록} | 가능 | 가능(PROV-O) | 없음(합성) | 데이터셋 매니페스트의 위치 정보와 일치 |
| CQ-20 | 다기업 데이터 통합 | Vendor A의 `product_id` X와 Vendor B의 `품목번호` Y는 같은 공통 제품인가? 근거 규칙은? | 원본 레코드–mappedTo–공통 개체, mappingRule | business_id, mappedTo, mappingRule | {공통 ID, 매핑 규칙} | 가능(조건: 매핑 테이블) | 가능 | 없음(합성) | 정답 매핑표와 일치 |

## 2. 1단계 질의셋(Q1~Q5)과의 대응

[evaluation_protocol.md](evaluation_protocol.md) §5.2의 초안 질의는 CQ의 부분집합으로 흡수한다.

| 기존 | CQ |
|---|---|
| Q1 제품 P의 BOM 자재 목록과 소요량 | CQ-04 |
| Q2 자재 M을 사용하는 모든 제품 | CQ-05 |
| Q3 주문 O 충족에 필요한 자재별 총소요량 | CQ-06 |
| Q4 재고 부족 자재와 부족량 | CQ-08 |
| Q5 리드타임 기준 이상 자재를 포함하는 제품 | CQ-10 |

## 3. 엔터티 ↔ CQ 추적 (불필요한 개념 점검)

| 엔터티·개념 | 사용하는 CQ |
|---|---|
| Product | 01~07, 10~14, 17, 18, 20 |
| Material | 04~06, 08~11 |
| Unit | 04, 06, 08 |
| Supplier, SupplierMaterial | 09, 10, 11, 13 |
| BOM (버전 단위) | 04~06, 17, 18 |
| BOMLine | 03~06, 10, 11, 18 |
| Order | 03, 07, 11~14 |
| SalesHistory | (CQ 직접 사용 없음 — 수요 예측 입력, `demand_source=FORECAST`일 때 CQ-07 간접 사용) |
| Inventory | 06~08, 11, 13 |
| Resource, Operation | 01~03, 13, 14 |
| ProductionPlan / ProductionPlanLine | 01, 14 |
| 원본 레코드·source_ref·변환 Activity | 15, 16, 19, 20 |

- **SalesHistory**는 어떤 CQ도 직접 조회하지 않는다. 예측 모델(예측·최적화 담당)의 입력이므로 데이터 모델에는 두되, **온톨로지(RDF) 범위에는 넣지 않는 것을 제안**한다(E06 착수 시 확정).

**의도적으로 제외한 개념** (답할 CQ가 없음)

| 개념 | 제외 이유 |
|---|---|
| 고객(Customer) | 고객별 질문 없음. 주문에 `customer_ref`도 두지 않음 |
| 사업장·창고(Site/Warehouse/Location) | 단일 사업장 가정 |
| 제품 변형(Variant), Phantom·Pegged supply·Vendor 라인 유형 | S1에 있으나 PoC CQ에 없음 |
| 교대·작업자·숙련도 | 능력은 자원 시간 단위로만 다룸 |
| 센서·설비 상태 관측 | 설비 데이터 CQ 없음 → SOSA/SSN 미적용([ontology_standards_review.md](ontology_standards_review.md)) |
| 원가 배분·회계 계정 | 비용은 계획안 비교 수준만 |

## 4. 미확정 사항

- CQ 우선순위와 E05~E07에서 실제로 쓸 CQ 수 (전부 / 핵심 일부) — 팀 합의 필요
- 계산형 CQ(06, 08, 11, 13, 14)를 RDF 방식에서 "SPARQL 단독"으로 평가할지 "SPARQL 조회 + 외부 계산"으로 평가할지 — E06 착수 전 결정 필요 (SQL 방식도 같은 조건으로 맞춤)
- 기준일, 계획 기간 H, N(리드타임 기준), D(지연일) 값 — 정답셋 구성 시 확정
