# 공통 제조업 데이터 모델 명세 — E01

- 작성일: 2026-10-20 (E01 명세 단계, 검토 대기)
- 범위: 데이터 구조·관계·검증 규칙 정의. **합성 데이터는 아직 생성하지 않았다.**
- 근거 표기: S1~S5 = [data_source_research.md](data_source_research.md)의 출처 ID, **P** = 1단계 계획·업무분장, **A** = PoC 설계 가정(실제 기업 기준 아님), **CQ** = [ontology_competency_questions.md](ontology_competency_questions.md)
- 실자료 확인: `예`(원문 확인) / `2차`(2차 출처로만 확인) / `아니오`
- 출처·변환 추적 필드(`record_uid` 등)는 [data_provenance_design.md](data_provenance_design.md), 실제/합성 구분 규칙은 [data_provenance_policy.md](data_provenance_policy.md)에서 정의한다.

---

## 1. 설계 원칙

1. **CQ 기반 최소 모델** — [CQ 목록](ontology_competency_questions.md)에 답하는 데 필요한 엔터티·필드만 둔다. CQ에 쓰이지 않는 필드는 추가하지 않는다.
2. **SQL/JSON과 RDF에 같은 모델** — 같은 엔터티·키·관계를 관계형 테이블과 RDF 클래스로 1:1 대응시킨다(대응표 §4).
3. **업무 ID와 원본 레코드 ID 분리** — `product_id` 같은 업무 ID는 중복·오류가 있을 수 있는 값이다. 원본 행마다 별도의 `record_uid`를 부여해, 중복 ID가 RDF 변환에서 합쳐져 사라지지 않게 한다([data_provenance_design.md](data_provenance_design.md) §3).
4. **수량에는 항상 단위** — 모든 수량 필드는 단위 필드와 짝을 이루며, 환산은 `Unit` 표로만 한다.
5. **단일 사업장 가정(A)** — PoC는 사업장·창고를 1개로 둔다. 다중 사업장은 범위 밖. 단, BOM 버전 검증 규칙은 사이트 조건을 포함해 정의해 둔다(§3.6).
6. **한 개념 = 한 이름** — SQL 테이블명과 RDF 클래스명을 같게 쓴다(§4.1 통일표).

## 1.1 초기 실험 범위 (초기 제안값, 2026-10-20)

아래 값은 **PoC 데이터 생성을 위한 명시적 가정**이며 실제 기업 수치가 아니다. 팀 검토로 바뀔 수 있다(decisions.md D-005, D-010).

| ID | 항목 | 초기 제안값 | 비고 |
|---|---|---|---|
| ASM-01 | 제품 | 5종 = 완제품 3 + 반제품 2 | 반제품은 다단계 BOM 구성용 |
| ASM-02 | 자재 | 10종 | |
| ASM-03 | BOM 라인 | 약 20행 (전체 BOM 버전 합계) | |
| ASM-04 | BOM 깊이 | 최대 2단계 (완제품 → 반제품 → 자재). 완제품 BOM에 자재를 직접 넣는 것도 허용 | 순환 검증용 오류 주입은 별도 데이터셋 |
| ASM-05 | BOM 버전 | 완제품 1종 이상에 버전 2개(기간이 이어지는 정상 교체) | BOM 버전 규칙 검증용. 충돌 버전은 오류 주입본에만 |
| ASM-06 | 주문 | 20건, 모두 계획 기간 안에 납기, 주문 1건 = 제품 1종 | |
| ASM-07 | 자원 | 3종 | |
| ASM-08 | 계획 단위 | 주간(`WEEK`). 계획 기간 4주 | 기간 길이 4주는 가정 |
| ASM-09 | 근무 달력 | 주 5일, 공휴일 없음 | 주간 가용시간 = regular_hours_per_day × 5 |
| ASM-10 | 화폐 | KRW (원, 소수점 없음) | 단가 값은 생성 시 가정값으로 정하고 매니페스트에 기록 |
| ASM-11 | 단위 | `EA`(개), `kg`, `g`, `h`(시간) | 리드타임은 단위표가 아니라 필드명(`_days`)으로 일 단위를 고정 |
| ASM-12 | 공급사 | 4곳, 자재 10종 중 2종은 공급사 2곳 (CQ-09 비교용) | |
| ASM-13 | 재고 기준일 | 1개 (계획 기간 시작일 전날) | 품목 15종(제품 5 + 자재 10) × 1 |
| ASM-14 | 반복 측정 | 3회 | evaluation_protocol §3.2 |
| ASM-15 | 사이트 | 1곳 (`site_id` 비움 = 전 사이트 적용) | BOM 버전 사이트 조건 검증은 오류 주입본에서만 사용 |

## 2. 엔터티 개요

| 엔터티 | 설명 | 레코드 단위 | 주 근거 | 실데이터 확보 | 합성 |
|---|---|---|---|---|---|
| Unit (보조) | 단위와 환산 계수 | 단위 1개 | A (QUDT 참고 가능) | 해당없음 | 필요(수작업 정의) |
| Product | 완제품·반제품 | 제품 1개 | S1, S3, P | 아니오 | 필요 |
| Material | 원자재·구매품 | 자재 1개 | S1, P | 아니오 | 필요 |
| Supplier | 공급사 | 공급사 1개 | P | 아니오 | 필요 |
| SupplierMaterial (관계 엔터티) | 공급사별 자재 공급 조건(리드타임 등) | 공급사×자재 | P, A | 아니오 | 필요 |
| BOM (버전 단위) | 제품별 BOM 버전과 유효 조건(기간·수량·사이트·활성) | BOM 버전 1개 | S1 | 아니오(구조만 확인) | 필요 |
| BOMLine | BOM의 구성품 1줄 | BOM×라인 | S1, S3 | 아니오(구조만 확인) | 필요 |
| Order | 고객 주문(납기 포함) | 주문 1건 | S2, P | 아니오 | 필요 |
| SalesHistory | 기간별 판매·수요 실적 | 제품×기간 | S4, S5 | 2차(S4) / 예(S5, 집계형) | 부분(공개 패턴 기반 파생 가능) |
| Inventory | 기준일 재고 | 품목×기준일 | P | 아니오 | 필요 |
| Resource | 설비·라인·작업장 | 자원 1개 | S1(route), S3(Work Center) | 아니오 | 필요 |
| Operation | 제품별 공정 단계와 사용 자원 | 제품×공정순서 | S1, S2, S3 | 아니오(구조만 확인) | 필요 |
| ProductionPlan / ProductionPlanLine | 비교 대상 생산계획안과 계획 수량 | 계획안 / 계획×제품×기간 | S2, P | 아니오 | 필요(계산 결과) |

추가된 보조 엔터티(Unit, SupplierMaterial, BOM 버전, ProductionPlanLine)는 모두 특정 CQ에 필요해서 두었다. 근거는 [ontology_design_patterns.md](ontology_design_patterns.md) 참고.

## 3. 엔터티별 필드

공통 열 표기: 필수 = Y/N, 키 = PK(기본키)·FK(외래키)·UK(유일), 실자료 = 실제 자료로 확인했는지, 합성 = 합성 필요 여부.
모든 테이블에는 추적 열 `record_uid`, `source_ref`가 추가로 붙는다([data_provenance_design.md](data_provenance_design.md) §4).

### 3.1 Unit (보조)

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| unit_code | 단위 코드 — 초기 범위 `EA`(개), `kg`, `g`, `h`(시간) (ASM-11) | string | — | Y | PK | A | 해당없음 | 필요 |
| dimension | 차원 (`MASS`, `COUNT`, `TIME`) | enum | — | Y | | A | 해당없음 | 필요 |
| base_unit_code | 같은 차원의 기준 단위 | string | — | Y | FK→Unit | A | 해당없음 | 필요 |
| to_base_factor | 기준 단위로 바꾸는 곱셈 계수 (g→kg = 0.001) | decimal | — | Y | | A | 해당없음 | 필요 |

### 3.2 Product

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| product_id | 제품 업무 ID | string | — | Y | PK(정상 데이터 기준 유일) | P | 아니오 | 필요 |
| product_name | 제품명 | string | — | Y | | P | 아니오 | 필요 |
| product_type | `FINISHED` / `SEMI_FINISHED` (반제품은 상위 BOM의 구성품이 될 수 있음) | enum | — | Y | | S1 | 예(개념) | 필요 |
| base_unit | 재고·생산 기준 단위 | string | — | Y | FK→Unit | A | 아니오 | 필요 |
| safety_stock_qty | 안전재고 | decimal | base_unit | N | | P(업무분장 예시) | 아니오 | 필요 — 기업별 기준 미확정 |
| manuf_lead_time_days | 생산 리드타임(확정→완료) | integer | day | N | | S3 (Manuf Lead Time) | 예(필드 개념) | 필요 |
| outsourcing_allowed | 외주 생산 가능 여부 | boolean | — | N | | P | 아니오 | 필요 — 기업별 미확정 |
| outsourcing_unit_cost | 외주 단가 | decimal | 통화/base_unit | N | | P | 아니오 | 필요 — 통화·금액 기준 팀 합의 필요 |

### 3.3 Material

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| material_id | 자재 업무 ID | string | — | Y | PK | P | 아니오 | 필요 |
| material_name | 자재명 | string | — | Y | | P | 아니오 | 필요 |
| base_unit | 기준 단위 (예: kg) | string | — | Y | FK→Unit | A | 아니오 | 필요 |
| unit_cost | 표준 단가 | decimal | 통화/base_unit | N | | S1(원가 개념) | 아니오 | 필요 — 통화 팀 합의 필요 |
| safety_stock_qty | 안전재고 | decimal | base_unit | N | | A | 아니오 | 필요 |

### 3.4 Supplier

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| supplier_id | 공급사 업무 ID | string | — | Y | PK | P | 아니오 | 필요 |
| supplier_name | 공급사명 (가상 명칭) | string | — | Y | | P | 아니오 | 필요 |

### 3.5 SupplierMaterial (관계 엔터티)

공급사–자재 쌍의 공급 조건이다. 이전 설계안의 RDF 클래스명 `SupplyAgreement`는 **같은 개념**이므로 폐기하고 SQL·RDF 모두 `SupplierMaterial`로 통일한다. 계약(가격 협상, 계약 기간 등)을 뜻하지 않는다.

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| supplier_id | 공급사 | string | — | Y | PK, FK→Supplier | P | 아니오 | 필요 |
| material_id | 자재 | string | — | Y | PK, FK→Material | P | 아니오 | 필요 |
| lead_time_days | 구매 리드타임 | integer | day | Y | | P | 아니오 | 필요 |
| min_order_qty | 최소 주문량 | decimal | Material.base_unit | N | | A | 아니오 | 필요 |
| is_preferred | 우선 공급사 여부 | boolean | — | Y | 자재당 TRUE 1개 | A | 아니오 | 필요 |

### 3.6 BOM (버전 단위)

**S1 근거 [확인]**: ① BOM 버전은 BOM을 생산 가능한 제품과 연결하며, 유효성은 기간·수량·사이트·제품 차원 등으로 제한할 수 있다. ② 버전은 승인되어야 계획·생산에 쓸 수 있고, BOM이 승인된 경우에만 버전을 승인할 수 있다. ③ 기본 버전으로 쓰려면 활성화해야 하며, 활성화할 때 주어진 제약(기간, 사이트, 수량 등)에 대한 유일성을 검증하고 이미 활성인 버전과 충돌하면 오류를 낸다. ④ 활성 버전이 아니어도 승인된 버전은 대안 BOM으로 선택할 수 있다.

**PoC 단순화 (A)**: D365는 BOM(라인 묶음)과 BOM 버전(제품 연결·유효 조건)을 별개 엔터티로 두지만, PoC는 **BOM 1행 = BOM 버전 1개**로 합치고 라인을 버전에 직접 소속시킨다. BOM 승인과 버전 승인은 `status` 하나로 합친다. 대안 BOM 선택(④)은 쓰지 않고 **활성 버전만** 적용한다. 제품 차원(변형)은 쓰지 않는다.

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| bom_id | BOM 버전 ID | string | — | Y | PK | S1 (BOM ID) | 예(개념) | 필요 |
| product_id | 생산 대상 제품 (유효 조건: 제품) | string | — | Y | FK→Product | S1 ① | 예(개념) | 필요 |
| bom_version | 버전 표기 | string | — | Y | UK(product_id, bom_version) | S1 | 예(개념) | 필요 |
| status | `DRAFT` / `APPROVED` | enum | — | Y | | S1 ② | 예(개념) | 필요 |
| is_active | 활성(기본) 버전 여부 | boolean | — | Y | `APPROVED`일 때만 TRUE 가능 | S1 ③ | 예(개념) | 필요 |
| valid_from | 유효 시작일 (포함) | date | — | Y | | S1 ① 기간 | 예(개념) | 필요 |
| valid_to | 유효 종료일 (포함, null = 무기한) | date | — | N | ≥ valid_from | S1 ① 기간 | 예(개념) | 필요 |
| min_qty | 적용 생산수량 하한 (포함, 기본 0) | decimal | Product.base_unit | Y | ≥ 0 | S1 ① 수량 | 예(개념). **범위 표현 방식과 필드명은 PoC 가정** (S1 페이지는 "quantity"로만 기술) | 필요 |
| max_qty | 적용 생산수량 상한 (미포함, null = 상한 없음) | decimal | Product.base_unit | N | > min_qty | S1 ① 수량 | 동일 | 필요 |
| site_id | 적용 사이트 (null = 전 사이트) | string | — | N | | S1 ① 사이트 | 예(개념) | 필요 (ASM-15: 정상 데이터는 null) |
| base_qty | 소요량 정의 기준 수량 | decimal | Product.base_unit | Y | > 0, 기본 1 | A | 아니오 | 필요 |

**BOM 버전 선택 규칙** (decision_logic §0의 "적용 BOM")

입력 (제품 p, 기준일 d, 생산수량 q, 사이트 s)에 대해 후보 = `product_id = p` ∧ `status = APPROVED` ∧ `is_active` ∧ `valid_from ≤ d ≤ valid_to(또는 null)` ∧ `min_qty ≤ q < max_qty(또는 null)` ∧ (`site_id = s` ∨ `site_id` is null).

| 후보 수 | 결과 |
|---|---|
| 1 | 그 버전을 적용 |
| 0 | **적용 BOM 없음** → 해당 제품 계산 중단, ERR-BOMVER(선택 불가)로 보고 |
| 2 이상 | **버전 선택 모호** → 계산 중단, ERR-BOMVER(모호)로 보고 |

이 규칙은 계산 시점(특정 d, q, s)의 판정이고, §5 QR-06은 수요와 무관하게 **데이터 자체에 모호해질 수 있는 조합이 있는지**를 정적으로 검사한다.

### 3.7 BOMLine

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| bom_id | 소속 BOM | string | — | Y | PK, FK→BOM | S1 | 예(개념) | 필요 |
| line_no | 라인 번호 | integer | — | Y | PK | A | 아니오 | 필요 |
| component_type | `MATERIAL` / `PRODUCT`(반제품) | enum | — | Y | | S1 | 예(개념) | 필요 |
| component_material_id | 자재 구성품 | string | — | 조건부 | FK→Material, component_type=MATERIAL일 때만 값 | S1 | 예(개념) | 필요 |
| component_product_id | 반제품 구성품 | string | — | 조건부 | FK→Product, component_type=PRODUCT일 때만 값 | S1 | 예(개념) | 필요 |
| qty_per | base_qty당 소요량 | decimal | `unit` 필드 | Y | > 0 | S1(계획 소비량) | 예(개념). 필드명은 [미확인] | 필요 |
| unit | 소요량 단위 | string | — | Y | FK→Unit, 구성품 base_unit과 같은 차원 | S3 Unit of Measure(필드명만, 설명 미확인) | 아니오 | 필요 |
| scrap_rate | 손실률 (0.05 = 5%) | decimal | 비율 | N | 0 이상 1 미만 | A | 아니오 | 필요 — 기업별 미확정 |
| line_type | `ITEM` (PoC는 ITEM만 사용; `PHANTOM` 등은 예약) | enum | — | Y | | S1 (Item, Phantom, Pegged supply, Vendor) | 예 | 필요 |

### 3.8 Order

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| order_id | 주문 업무 ID | string | — | Y | PK | P | 아니오 | 필요 |
| product_id | 주문 제품 | string | — | Y | FK→Product | S2 | 예(개념) | 필요 |
| order_qty | 주문 수량 | decimal | `unit` 필드 | Y | > 0 | S2 | 예(개념) | 필요 |
| unit | 수량 단위 | string | — | Y | FK→Unit | A | 아니오 | 필요 |
| order_date | 주문일 | date | — | Y | | P | 아니오 | 필요 |
| due_date | 납기일 | date | — | Y | ≥ order_date | S2(계획 완료일 개념), P | 아니오 | 필요 |
| priority | `NORMAL` / `URGENT` | enum | — | N | | S5(긴급/비긴급 주문 구분 개념) | 예(개념만) | 필요 |
| status | `OPEN` / `CLOSED` / `CANCELLED` | enum | — | Y | | A | 아니오 | 필요 |

### 3.9 SalesHistory

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| product_id | 제품 | string | — | Y | PK, FK→Product | P | 아니오 | 부분 |
| period_start | 기간 시작일 | date | — | Y | PK | S4(`date`, `wm_yr_wk`) | 2차 | 부분 |
| period_grain | `DAY` / `WEEK` | enum | — | Y | PK | S4, S5 | 2차 / 예 | 부분 |
| sales_qty | 판매(수요) 수량 | decimal | Product.base_unit | Y | ≥ 0 | S4(판매 개수), S5(Target) | 2차 / 예 | 부분 |
| source_series_id | 공개 데이터 원본 시계열 ID (예: M5 `item_id`+`store_id`) | string | — | N | 원본 매핑 | S4 | 2차 | 해당없음 |
| origin_class | `SYNTHETIC` / `PUBLIC_DERIVED` 등 (정책 §1) | enum | — | Y | | 정책 | 해당없음 | 해당없음 |
| generation_method | `GENERATED`(직접 합성) / `ALLOCATED`(공개 총량을 제품별로 배분) / `MAPPED`(공개 시계열 1개를 가상 제품 1개에 대응) / `TRANSFORMED`(공개 값을 의미 유지 변환, origin_class=PUBLIC_DERIVED) | enum | — | Y | | 정책 §4.2 | 해당없음 | 해당없음 |
| derived_from_record_uid | 배분·대응·변환의 원본 공개 레코드 | string | — | 조건부 | GENERATED 외에는 필수, →공개 원본 스테이징 레코드 | 정책 §4.2 | 해당없음 | 해당없음 |
| allocation_share | 배분 비율 (합성 가정값) | decimal | 비율 | 조건부 | ALLOCATED면 필수. 같은 원본 레코드에서 나온 행들의 합 = 1 | 정책 §4 | 아니오 | 필요 |
| date_is_synthetic | `period_start`가 합성 날짜인지 (UCI 배분분은 TRUE) | boolean | — | Y | | 정책 §4.1 | 해당없음 | 해당없음 |
| source_day_of_week_code | 공개 원본의 요일 코드 숫자 그대로 (의미 미확인, 날짜 계산에 쓰지 않음) | integer | — | N | | S5 | 예(값) / 아니오(의미) | 해당없음 |

**공개 원본은 SalesHistory에 넣지 않는다.** UCI 등 공개 원본은 원래 컬럼 그대로 스테이징 테이블(`stg_public_uci_daily_orders` 등, 원본 1행 = 1레코드, `record_uid` 부여. E01 구현: `data/raw/public/uci_daily_demand/staging_uci_daily_orders_v1.json`, Git 미추적)에 보존하고, SalesHistory에는 그로부터 만든 행만 넣는다. 원본값(스테이징)과 배분된 합성값(SalesHistory, `ALLOCATED`)은 항상 다른 레코드다.

UCI Daily Demand는 **일별 집계 주문 자료**다. 개별 제품별 주문으로 해석하지 않으며, `Order type A/B/C` 등의 열을 제품으로 대응시키지 않는다. 원본에 날짜가 없으므로 달력 날짜를 붙이는 것도 합성 가정이다([data_provenance_policy.md](data_provenance_policy.md) §4). 공개 데이터 연결 여부 자체는 미결정이다.

### 3.10 Inventory

품목×기준일의 재고 상태 1건이다. 이전 설계안의 RDF 클래스명 `InventorySnapshot`은 **같은 개념**이므로 폐기하고 SQL·RDF 모두 `Inventory`로 통일한다(레코드 1건이 곧 기준일 스냅숏).

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| item_type | `PRODUCT` / `MATERIAL` | enum | — | Y | PK | P | 아니오 | 필요 |
| item_id | 품목 ID | string | — | Y | PK, FK→Product 또는 Material(item_type 기준) | P | 아니오 | 필요 |
| as_of_date | 재고 기준일 | date | — | Y | PK | P | 아니오 | 필요 |
| on_hand_qty | 보유 수량 | decimal | `unit` 필드 | Y | ≥ 0 | P | 아니오 | 필요 |
| allocated_qty | 이미 할당(예약)된 수량 | decimal | `unit` 필드 | N | 0 ≤ allocated ≤ on_hand | S1(pegged supply 예약 개념), A | 아니오 | 필요 |
| on_order_qty | 입고 예정 수량(미입고 구매) | decimal | `unit` 필드 | N | ≥ 0 | A | 아니오 | 필요 |
| expected_receipt_date | on_order_qty 입고 예정일 | date | — | 조건부 | on_order_qty > 0이면 필수 | A | 아니오 | 필요 |
| unit | 수량 단위 | string | — | Y | FK→Unit | A | 아니오 | 필요 |

### 3.11 Resource

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| resource_id | 자원 업무 ID | string | — | Y | PK | S3(Work Center) | 예(개념) | 필요 |
| resource_name | 자원명 | string | — | Y | | S3 | 예(개념) | 필요 |
| resource_type | `MACHINE` / `LINE` / `WORKCENTER` | enum | — | Y | | S1, S3 | 예(개념) | 필요 |
| regular_hours_per_day | 정규 가용시간 | decimal | h/day | Y | > 0 | S3(작업장 가용능력 개념) | 아니오 | 필요 |
| overtime_hours_per_day_max | 잔업 가능 최대시간 | decimal | h/day | N | ≥ 0 | P | 아니오 | 필요 — 기업별 미확정 |
| cost_per_hour | 정규 시간당 비용 | decimal | 통화/h | N | | S1(원가 개념) | 아니오 | 필요 |
| overtime_cost_per_hour | 잔업 시간당 비용 | decimal | 통화/h | N | | P | 아니오 | 필요 — 기업별 미확정 |

근무일 달력은 PoC에서 "주 5일, 공휴일 없음"으로 단순화한다(A, 팀 합의 필요).

### 3.12 Operation

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| operation_id | 공정 ID | string | — | Y | PK | S3(Operation) | 예(개념) | 필요 |
| product_id | 대상 제품 | string | — | Y | FK→Product, UK(product_id, sequence_no) | S1(route), S2 | 예(개념) | 필요 |
| sequence_no | 공정 순서 | integer | — | Y | | S1 | 예(개념) | 필요 |
| resource_id | 사용 자원 | string | — | Y | FK→Resource | S3(Work Center) | 예(개념) | 필요 |
| run_time_per_unit_h | 단위당 가공시간 | decimal | h/base_unit | Y | > 0 | S3(Default Duration 개념) | 예(개념) | 필요 |
| setup_time_h | 1회 준비시간 | decimal | h | N | ≥ 0 | A | 아니오 | 필요 |

### 3.13 ProductionPlan / ProductionPlanLine

| 컬럼명 | 설명 | 자료형 | 단위 | 필수 | 키·관계 | 근거 | 실자료 | 합성 |
|---|---|---|---|---|---|---|---|---|
| plan_id | 계획안 ID | string | — | Y | PK (Plan) | P | 아니오 | 필요 |
| plan_name | 계획안 이름 (예: 정규생산안, 잔업안, 외주안 — 이름은 예시) | string | — | Y | | P | 아니오 | 필요 |
| horizon_start / horizon_end | 계획 기간 | date | — | Y | start ≤ end | P | 아니오 | 필요 |
| generated_by | 생성 방식 (`RULE` / `OPTIMIZER` / `MANUAL`) | enum | — | Y | | P | 아니오 | 필요 |
| overtime_allowed | 자체 생산에 잔업 가용시간을 더하는지 (잔업안만 TRUE). v2에서 추가 | boolean | — | Y | | P | 아니오 | 필요 |
| (Line) plan_id, line_no | 계획 라인 | string, integer | — | Y | PK, FK→Plan | P | 아니오 | 필요 |
| (Line) product_id | 생산 제품 | string | — | Y | FK→Product | S2 | 예(개념) | 필요 |
| (Line) period_start | 생산 기간 시작일 | date | — | Y | | P | 아니오 | 필요 |
| (Line) planned_qty | 계획 수량 | decimal | Product.base_unit | Y | ≥ 0 | S2 | 예(개념) | 필요 |
| (Line) production_mode | `INHOUSE` / `OUTSOURCE` (v2. v1의 `REGULAR`/`OVERTIME` 라인 구분은 폐기 — 잔업은 계획의 `overtime_allowed`로 결정) | enum | — | Y | | P | 아니오 | 필요 |
| (Line) resource_id | 사용 자원 (외주면 null) | string | — | 조건부 | FK→Resource, 해당 제품의 Operation에 있는 자원이어야 함 | S1, S3 | 예(개념) | 필요 |

## 4. 관계 요약과 SQL·RDF 대응

| 관계 | 카디널리티 | SQL 표현 | RDF 표현(설계안, 미구현) |
|---|---|---|---|
| Product 1 — N BOM | 제품당 버전 여러 개 | BOM.product_id FK | `:BOM :bomFor :Product` |
| BOM 1 — N BOMLine | | BOMLine.bom_id FK | `:BOMLine :partOfBOM :BOM` |
| BOMLine N — 1 Material / Product | 구성품 | 조건부 FK 2개 | `:BOMLine :component :Material` 또는 `:Product` |
| Product 1 — N Operation N — 1 Resource | 공정 경로 | Operation FK 2개 | `:Operation :forProduct`, `:usesResource` |
| Supplier N — M Material | 관계 속성(리드타임) 있음 | SupplierMaterial | `:SupplierMaterial :supplier`, `:material` |
| Order N — 1 Product | | Order.product_id FK | `:Order :orderedProduct :Product` |
| Inventory N — 1 Product/Material | 기준일별 | 복합키 + item_type | `:Inventory :ofItem` |
| SalesHistory N — 1 Product | 기간별 | 복합키 | `:SalesHistory :ofProduct` |
| ProductionPlan 1 — N ProductionPlanLine | | FK | `:ProductionPlanLine :inPlan` |
| 모든 레코드 → 원본 위치 | | `record_uid`, `source_ref` | PROV-O ([data_provenance_design.md](data_provenance_design.md)) |

관계 자체에 속성이 있는 경우(BOMLine, SupplierMaterial, Inventory, SalesHistory, ProductionPlanLine)는 관계 클래스로 표현한다.

### 4.1 엔터티 이름 통일표 (2026-10-20 정리)

| 통일 이름 (SQL 테이블 = RDF 클래스) | 폐기한 이름 | 판정 |
|---|---|---|
| SupplierMaterial | SupplyAgreement | 같은 개념 (공급사–자재 쌍의 리드타임·최소주문량·우선 여부) |
| Inventory | InventorySnapshot | 같은 개념 (품목×기준일 재고 1건) |
| SalesHistory | SalesObservation | 같은 개념 (제품×기간 판매 1건) |
| ProductionPlanLine | PlanLine | 같은 개념 (계획×제품×기간 계획 수량 1건) |

같은 업무 사실은 SQL 1행 = RDF 관계 클래스 인스턴스 1개로 표현하며, 열 이름과 RDF 속성 이름은 snake_case ↔ camelCase로만 다르다(예: `lead_time_days` ↔ `:leadTimeDays`).

**구분이 필요한 비슷한 개념**

| 개념 A | 개념 B | 차이 |
|---|---|---|
| Inventory (재고 사실) | 원본 재고 레코드 (`stg_*`, record_uid 계층) | A는 검증·매핑 후 업무 사실, B는 원본 행 그대로. 중복 ID 검증은 B에서 수행([provenance 설계 §3](data_provenance_design.md)) |
| SalesHistory (`ALLOCATED`/`GENERATED`) | 공개 원본 스테이징 (`stg_public_*`) | B는 공개 원본값, A는 그로부터 만든 합성값. §3.9 |
| SupplierMaterial.lead_time_days (구매 리드타임) | Product.manuf_lead_time_days (생산 리드타임) | 구매 리드타임은 공급사–자재 쌍, 생산 리드타임은 제품 속성 | 근거와 단순 관계로 충분한 경우는 [ontology_design_patterns.md](ontology_design_patterns.md) 참고.

---

## 5. 데이터 품질·관계 검증 규칙

오류 코드는 [evaluation_protocol.md](evaluation_protocol.md) §2.4와 같은 체계를 쓴다. 기존 7개 코드에 E01에서 5개(ERR-DATE, ERR-BOMCYCLE, ERR-BOMVER, ERR-INVQTY, ERR-RESREL)를 추가했다. 탐지 판정·집계는 프로토콜 §4.1을 따른다.

**공통 전제 (SQL/JSON과 RDF/SHACL 동등 비교용)**

- 두 방식 모두 **같은 원본 레코드 집합**을 입력으로 받는다. 각 원본 행은 `record_uid`를 가진다.
- RDF는 원본 행을 **레코드 노드**로 먼저 표현하고, 업무 ID는 리터럴 값으로 둔다. 업무 개체(제품 등)로의 병합은 검증 이후 단계에서 한다. 그래야 중복 ID 같은 오류가 RDF 변환에서 사라지지 않는다([data_provenance_design.md](data_provenance_design.md) §3).
- 오류 보고는 두 방식 모두 (`record_uid`, 필드, 오류 코드)로 출력해 같은 채점기로 채점한다.
- 날짜 기준일(`reference_date`)은 데이터셋 매니페스트에 고정한다.

| 규칙 ID | 오류 코드 | 정의 | SQL / JSON(Pydantic) 탐지 | RDF / SHACL 탐지 (설계안) | 보고 단위 |
|---|---|---|---|---|---|
| QR-01 | ERR-DUPID | 같은 엔터티에서 업무 ID(`product_id` 등)가 2개 이상 레코드에 나타남 | 적재 전 `GROUP BY id HAVING COUNT(*)>1` (PK 제약은 첫 위반에서 중단되므로 사전 집계로 탐지) | SHACL-SPARQL 제약: 레코드 노드 중 같은 ID 리터럴을 가진 다른 노드가 있으면 위반 (SHACL Core만으로는 불가) | 관련 레코드 전부, 필드 = `*` |
| QR-02 | ERR-BADREF | BOMLine·Order·Inventory·Operation·SupplierMaterial이 존재하지 않는 제품·자재·자원·공급사를 참조 | `LEFT JOIN ... WHERE parent IS NULL` (SQLite는 `PRAGMA foreign_keys=ON` 필요) | SHACL Core `sh:class`(대상 노드 클래스 확인) + 참조 ID 리터럴과 일치하는 레코드가 없는 경우 SHACL-SPARQL | 참조하는 레코드, 해당 FK 필드 |
| QR-03 | ERR-UNIT | ① 단위가 `Unit`에 없음 ② 수량 단위의 차원이 구성품 기준 단위와 다름(예: kg 자재에 EA) ③ 단위 누락 | Pydantic enum/검증기 + Unit 조인으로 차원 비교 | `sh:in`(허용 단위) + 차원 비교는 SHACL-SPARQL | 레코드, 단위 필드 |
| QR-04 | ERR-DATE | ① 날짜 형식 오류·존재하지 않는 날짜(2026-02-30) ② due_date < order_date ③ valid_to < valid_from ④ as_of_date > reference_date ⑤ on_order_qty > 0인데 입고 예정일 없음 | 파싱 단계에서 형식 검증, 이후 비교 조건 | `sh:datatype xsd:date`(형식) + `sh:lessThanOrEquals`(SHACL Core, 두 날짜 비교) | 레코드, 날짜 필드 |
| QR-05 | ERR-BOMCYCLE | 반제품 구성으로 BOM이 순환(A→B→A). 자기 자신 참조 포함 | 재귀 CTE로 경로 전개, 출발 제품 재등장 시 위반 | SHACL-SPARQL + SPARQL 속성 경로(`+`)로 자기 도달 여부 확인 | 순환 경로의 BOMLine 레코드 전부 |
| QR-06 | ERR-BOMVER | ① **유효 조건 중복(모호)**: 같은 제품의 활성 버전 두 개가 기간·수량·사이트 조건에서 **동시에** 겹침 (S1 활성화 유일성 검증과 같은 개념, 판정식은 아래) ② 미승인(`DRAFT`) 버전이 활성 ③ 같은 제품·버전 표기 중복 ④ 유효 조건 자체 오류(valid_to < valid_from, max_qty ≤ min_qty) ⑤ 기준일·계획 수량에 대해 적용 가능한 활성 버전이 0개(선택 불가) | 자기 조인으로 ① 판정식 검사, ⑤는 계획 시점 검사 | SHACL-SPARQL (①⑤), SHACL Core `sh:lessThanOrEquals`(④ 날짜) | 충돌 BOM 레코드 전부, 필드 = 겹친 조건 필드 |
| QR-07 | ERR-INVQTY | ① on_hand < 0 ② allocated > on_hand ③ 단위가 `EA`인데 소수 수량 ④ 같은 품목·기준일 재고 중복 | CHECK 제약 + 조건 질의 | `sh:minInclusive 0` (SHACL Core), 필드 간 비교는 `sh:lessThanOrEquals` | 레코드, 수량 필드 |
| QR-08 | ERR-RESREL | ① Operation이 존재하지 않는 자원 참조 ② 주문·계획 대상 제품에 공정(Operation)이 없음 ③ 계획 라인의 자원이 그 제품 공정에 없는 자원 ④ REGULAR/OVERTIME 계획 라인에 자원 없음 | 조인·NOT EXISTS 질의 | SHACL-SPARQL | 레코드, `resource_id` |
| (기존) | ERR-MISSING | 필수 필드 누락 | Pydantic 필수 필드 | `sh:minCount 1` | 레코드, 필드 |
| (기존) | ERR-NUMFMT | 숫자 형식 오류, 음수 수량, 0 이하 소요량 | 파싱·검증기 | `sh:datatype xsd:decimal`, `sh:minExclusive 0` | 레코드, 필드 |

**QR-06 ① 판정식** — 같은 `product_id`의 서로 다른 BOM 버전 X, Y가 모두 `APPROVED`이고 `is_active`일 때, 아래 세 조건이 **모두** 참이면 버전 선택이 모호해질 수 있으므로 오류다.

| 조건 | 겹침 판정 (null 처리 포함) |
|---|---|
| 기간 | `X.valid_from ≤ coalesce(Y.valid_to, ∞)` ∧ `Y.valid_from ≤ coalesce(X.valid_to, ∞)` (종료일 포함 구간) |
| 수량 | `X.min_qty < coalesce(Y.max_qty, ∞)` ∧ `Y.min_qty < coalesce(X.max_qty, ∞)` (상한 미포함 구간) |
| 사이트 | `X.site_id is null` ∨ `Y.site_id is null` ∨ `X.site_id = Y.site_id` |

- 기간은 겹치지만 수량 구간이 나뉘어 있으면(예: 0~100 미만 / 100 이상) 정상이다. 사이트가 다르면 정상이다.
- 버전 교체는 `X.valid_to = 2026-11-30`, `Y.valid_from = 2026-12-01`처럼 이어지게 만들며, 같은 날짜를 공유하면(종료일 포함 규칙) 겹침으로 본다.
- 오류 주입본(ASM-05)에는 기간 겹침, 수량 겹침, 사이트 null 중복을 각각 1건 이상 넣는 것을 제안한다(건수는 팀 합의 필요).

- SHACL Core만으로 되는 규칙과 SHACL-SPARQL이 필요한 규칙을 E06 결과에서 따로 집계한다(구현 부담 비교 근거).
- 검증 순서: 형식(MISSING, NUMFMT, DATE①) → 참조(BADREF, UNIT) → 관계·구조(DUPID, BOMCYCLE, BOMVER, RESREL) → 수량 논리(INVQTY). 앞 단계 오류로 생기는 연쇄 보고는 프로토콜 §4.1의 파생 보고 규칙을 따른다.

## 6. 미확정 사항

- §1.1 초기 제안값(ASM-01~15)의 팀 확인 — D-005, D-010
- 안전재고·손실률·외주 가능 여부·비용 단가(KRW) 값 — 생성 시 가정값으로 정하되 기업별 기준은 아님
- 수량 범위(min_qty/max_qty) 표현이 실제 ERP 필드와 다를 수 있음 — D365 BOM 버전 화면의 수량 필드 원문 확인 시 갱신
- SalesHistory에 공개 데이터 패턴을 쓸지 — 라이선스 확인 및 사용자 결정 필요
