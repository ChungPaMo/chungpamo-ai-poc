# 데이터 출처 조사 — E01 데이터 구조 조사

- 작성일: 2026-10-20 (E01 명세 단계, 검토 대기)
- 조사 방법: 사용자가 지정한 공개 웹페이지 5건을 읽기 전용으로 조회(2026-10-20). **데이터 파일은 다운로드하지 않았다.** Kaggle M5 페이지는 내용을 읽지 못해 2차 출처를 보조로 조회했다.
- 관련 문서: [manufacturing_data_schema.md](manufacturing_data_schema.md), [decision_logic.md](decision_logic.md), [data_provenance_policy.md](data_provenance_policy.md)

## 0. 확인 수준 표기

| 표기 | 의미 |
|---|---|
| **[확인]** | 지정 원문 페이지에서 직접 읽은 내용 |
| **[2차]** | 원문이 아닌 제3자 문서(패키지 문서 등)에서 읽은 내용. 원본 파일로 다시 확인하기 전에는 확정하지 않음 |
| **[미확인]** | 원문에서 찾지 못했거나 접근하지 못함 |
| **[가정]** | PoC 설계를 위해 둔 가정. 실제 자료가 아님 |

---

## 1. 출처별 요약

| ID | 출처 | 종류 | 접근 결과 | 제조 PoC 관련성 |
|---|---|---|---|---|
| S1 | Microsoft Dynamics 365 SCM — Bills of materials and formulas | ERP 공식 문서(개념) | 페이지 조회 성공 (문서 날짜 2025-07-10) | BOM 구조·버전·라인 유형의 근거 |
| S2 | Microsoft Dynamics 365 SCM — Production order lifecycle overview | ERP 공식 문서(개념) | 페이지 조회 성공 (문서 날짜 2025-01-31) | 생산오더 구성 요소의 근거 |
| S3 | Odoo 18.0 — Bill of materials 설정 | ERP 공식 문서(사용자 매뉴얼) | 페이지 조회 성공 | BOM·공정·작업장·리드타임 필드의 근거 |
| S4 | Kaggle M5 Forecasting – Accuracy (Walmart) | 실제 판매 데이터 | **원문 조회 실패**(JavaScript 렌더링, 본문 없음). 2차 출처만 조회 | 수요(판매 이력) 시계열 패턴 |
| S5 | UCI Daily Demand Forecasting Orders | 실제 주문 데이터 | 페이지 조회 성공 | 일별 주문량 시계열(소규모) |

S1~S3은 **데이터셋이 아니라 업무 구조(개념 모델)의 근거**다. 실제 레코드 값을 제공하지 않는다.

---

## 2. S1 — Dynamics 365 BOM

- URL: https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/bill-of-material-bom
- 파일 형식·라이선스: 해당없음(문서). 데이터 제공 없음.

| 항목 | 내용 | 수준 |
|---|---|---|
| BOM 정의 | 제품 생산에 필요한 구성품을 정의. 구성품은 원자재, 반제품, 재료이며 서비스가 들어갈 수도 있음 | [확인] |
| BOM 식별 정보 | BOM ID, BOM name, BOM lines, BOM versions | [확인] |
| 단일 수준 | "A single BOM describes a single level". 구성품은 자체 BOM을 가질 수 있고 BOM 버전으로 참조됨 → 다단계 BOM은 BOM 간 참조로 구성 | [확인] |
| BOM 버전 | 생산 가능한 제품(변형)과 BOM을 연결. 유효성은 기간, 수량, 사이트, 제품 차원 등으로 제한 가능 | [확인] |
| 승인 | BOM과 BOM 버전은 각각 승인/미승인. BOM이 미승인이면 모든 버전도 미승인. 버전은 BOM이 승인된 경우에만 승인 가능 | [확인] |
| 활성화(기본 버전) | 활성화 시 제약 조건(기간·사이트·수량 등)에 대한 버전 유일성을 검증하고, 이미 활성인 버전과 충돌하면 오류를 냄 → **BOM 버전 충돌 검증 규칙의 근거** | [확인] |
| BOM 라인 | 자재·서비스·재료마다 1개 라인. 지정한 제품 변형의 계획 소비량과 관련 속성을 정의 | [확인] |
| 라인 유형 | Item, Phantom, Pegged supply, Vendor | [확인] |
| 원가 | BOM과 공정(route)을 결합하면 제품 추정 원가 계산의 기초가 됨 | [확인] |
| BOM 라인의 수량·단위·스크랩 필드명 | 이 페이지에서 필드명 수준으로 설명하지 않음 | [미확인] |

## 3. S2 — Dynamics 365 생산오더

- URL: https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/create-production-orders

| 항목 | 내용 | 수준 |
|---|---|---|
| 생산오더 내용 | 무엇을 생산할지, 생산 수량, 계획 완료일, 소비할 자재, 따를 공정 | [확인] |
| 주요 엔터티 | 생산 BOM과 생산 공정(route)을 선택 품목·수량에 따라 생산오더로 복사. 시작 전 편집 가능 | [확인] |
| 상태 | 생성 시 *Created*, 완료 시 *Ended*. 중간 상태는 이 페이지에 나열되지 않음 | [확인] / 중간 상태 [미확인] |
| 생성 경로 | 마스터 플래닝(자재 수요 기반), 판매오더 라인 또는 상위 생산오더에서(pegged supply), 수동 | [확인] |

## 4. S3 — Odoo 18.0 BOM

- URL: https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/manufacturing/basic_setup/bill_configuration.html

| 영역 | 확인된 필드명 | 수준 |
|---|---|---|
| BoM 설정 | BoM Type = "Manufacture this Product" (Kit, Subcontracting은 링크로만 언급) | [확인] |
| BoM 헤더 | Product, Product Variant, Quantity, Reference — 이 페이지에서 설명하지 않음 | [미확인] |
| Components 탭 | Component, (선택 열) Apply on Variants, Consumed in Operation, Manual Consumption | [확인] |
| Components 수량·단위 | Quantity, Unit of Measure — 이 페이지에서 설명하지 않음 | [미확인] |
| Operations 탭 | Operation, Work Center, Apply on Variants, Duration Computation, Default Duration, Company, Work Sheet | [확인] |
| By-products 탭 | By-product, Quantity, Unit of Measure, Produced in Operation | [확인] |
| Miscellaneous 탭 | Manufacturing Readiness, Version(PLM 앱 사용 시), Flexible Consumption(Blocked / Allowed / Allowed with Warning), Routing, Analytic Distribution, Manuf Lead Time, Days to prepare Manufacturing Order | [확인] |

시사점: 공정(Operation)은 작업장(Work Center)에 묶이고 기본 소요시간(Default Duration)으로 작업장 가용능력 계획에 쓰인다 [확인]. → PoC의 `Operation`–`Resource` 관계 근거.

## 5. S4 — Walmart M5 (Kaggle)

- URL: https://www.kaggle.com/competitions/m5-forecasting-accuracy/data
- **원문 조회 결과: 실패.** 페이지 본문이 JavaScript로 렌더링되어 제목 외 내용을 읽지 못함. 파일 목록·크기·컬럼·라이선스(대회 규칙)는 원문 기준으로 **모두 [미확인]**.
- 보조 조회(2차 출처):
  - R `m5` 패키지 `tiny_m5` 문서: https://search.r-project.org/CRAN/refmans/m5/html/tiny_m5.html
  - Python `prefgraph` M5 로더 소스(검색 결과 요약): https://prefgraph.readthedocs.io/en/latest/_modules/prefgraph/datasets/_m5.html

| 항목 | 내용 | 수준 |
|---|---|---|
| 실제 출처 | Walmart 판매 데이터, Kaggle M5 대회(주최 Spyros Makridakis) | [2차] |
| 파일 | `sales_train_evaluation.csv`, `sell_prices.csv`, `calendar.csv` (로더가 요구하는 파일명). 그 밖의 파일·크기 | [2차] / 나머지 [미확인] |
| 판매 파일 구조 | 와이드 형식, 일자별 열 `d_1 … d_N` | [2차] |
| 식별 컬럼 | `item_id`, `dept_id`, `cat_id`, `store_id`, `state_id` | [2차] (tiny_m5 파생본 기준) |
| 달력 | `wm_yr_wk`(주 ID), `weekday`, `wday`, `month`, `year`, `event_name_1`, `event_type_1`, `event_name_2`, `event_type_2`, SNAP 여부 | [2차] (tiny_m5는 SNAP을 `snap` 하나로 통합. 원본 열 구성은 [미확인]) |
| 가격 | `sell_price` — 상점·주 단위 평균 가격, 판매가 없으면 비어 있음. 연결키 `store_id`, `item_id`, `wm_yr_wk` | [2차] |
| 레코드 단위 | 판매: 품목×상점×일자의 판매 수량(개수). 가격: 품목×상점×주 | [2차] |
| 라이선스·활용 제한 | Kaggle 대회 규칙 동의가 필요한 것으로 알려져 있으나 원문 확인 못 함. 재배포·상업적 이용 조건 | **[미확인] — 사용 전 확인 필수** |
| 접근 조건 | Kaggle 계정 로그인 및 대회 규칙 동의 필요 가능성 | [미확인] |

**PoC 활용 가능 범위(제안)**: 소매 판매 데이터이므로 제조 BOM·재고·설비 정보는 없다. `SalesHistory`의 **수요 패턴**(계절성, 간헐 수요, 이벤트 효과)만 참고하며, 합성 제품에 연결할 경우 "공개 데이터 기반 파생"으로 표시한다([data_provenance_policy.md](data_provenance_policy.md)). 라이선스 확인 전에는 사용하지 않는다.

## 6. S5 — UCI Daily Demand Forecasting Orders

- URL: https://archive.ics.uci.edu/dataset/409/daily+demand+forecasting+orders

| 항목 | 내용 | 수준 |
|---|---|---|
| 실제 출처 | 브라질 물류 회사의 실제 데이터베이스, 60일간 수집 (구체 날짜 없음) | [확인] |
| 기증자·기증일 | Ricardo Ferreira 외 4인, 2017-11-20 | [확인] |
| 규모 | 인스턴스 60, 특성 12 + 목표 변수 1, 결측 없음 | [확인] |
| 파일 형식 | CSV `Daily_Demand_Forecasting_Orders.csv`(약 5KB), zip `daily+demand+forecasting+orders.zip`(약 5.2KB), Weka ARFF 헤더 제공 | [확인] |
| 변수 (페이지 표기) | Week of the month(Integer), Day of the week(Integer, 월~금), Non-urgent order, Urgent order, Order type A, Order type B, Order type C, Fiscal sector orders (이상 Continuous), Orders from the traffic controller sector, Banking orders (1), Banking orders (2), Banking orders (3) (Integer), Target (Total orders) | [확인] (Banking orders (2)·(3)은 페이지 변수표가 잘려 ARFF 헤더로 확인) |
| CSV 파일의 실제 헤더 문자열·구분자 | 파일을 열지 않아 확인 못 함 (페이지 표기와 다를 수 있음) | [미확인] |
| 단위 | 페이지에 단위 표기 없음 (주문 "건수"로 추정되나 확정 못 함) | [미확인] |
| 기본키 | 명시적 ID·날짜 열 없음. 행 순서가 곧 일자로 보이나 확인 필요 | [미확인] |
| 라이선스 | Creative Commons Attribution 4.0 International (CC BY 4.0) | [확인] |
| 인용 | Ferreira et al. (2016), DOI 10.24432/C5BC8T | [확인] |

**PoC 활용 가능 범위(제안)**: 제조가 아닌 물류 주문 데이터이며 제품 ID가 없다. **일별 집계 주문 자료로만 취급**하며 개별 제품별 주문으로 해석하지 않는다(`Order type A/B/C`도 제품이 아님). 가상 제품에 배분해 쓰는 경우 원본값과 배분 합성값을 분리한다([data_provenance_policy.md](data_provenance_policy.md) §4). CC BY 4.0이므로 출처 표기를 지키면 가공·재배포 가능.

---

## 7. 실제 자료 대비 공백

| 필요 데이터 | S4 M5 | S5 UCI | S1~S3 | 결론 |
|---|---|---|---|---|
| 제품 마스터 | 품목·분류 ID만 [2차] | 없음 | 구조만 | **합성** |
| 판매·수요 이력 | 있음 [2차] | 있음(총량) [확인] | — | 공개 데이터 참고 가능 (라이선스 조건부) |
| 주문(납기 포함) | 없음 | 일별 집계만, 납기 없음 | 구조만 | **합성** |
| 자재·BOM | 없음 | 없음 | 구조만 | **합성** |
| 재고 | 없음 | 없음 | — | **합성** |
| 공급사·리드타임 | 없음 | 없음 | Manuf Lead Time 필드 [확인] | **합성** |
| 설비·공정·능력 | 없음 | 없음 | Work Center·Default Duration [확인] | **합성** |
| 원가·단가 | 판매가만 [2차] | 없음 | 원가 계산 개념 [확인] | **합성** (기업별 기준은 미확정) |

## 8. 원본 다운로드 승인 요청 목록 (승인 전 미실행)

| # | 대상 | 방법 | 크기 | 조건 | 다운로드 후 검증 항목 |
|---|---|---|---|---|---|
| DL-1 | UCI `daily+demand+forecasting+orders.zip` | UCI 데이터셋 페이지의 Download 링크 | 약 5.2KB | 로그인 불필요, CC BY 4.0 | 실제 헤더·구분자·인코딩, 행 수(60), 자료형, 결측, SHA-256 |
| DL-2 | Kaggle M5 Accuracy 데이터 (`calendar.csv`, `sell_prices.csv`, `sales_train_evaluation.csv` 등) | Kaggle 웹 또는 Kaggle API | [미확인] (수백 MB 규모로 알려짐, 확인 필요) | Kaggle 계정·대회 규칙 동의 필요 가능성. **규칙의 재배포·이용 조건을 사용자가 먼저 확인** | 원문 파일 목록·컬럼, 키(`item_id`+`store_id`) 유일성, 일자 범위, 가격 결측 의미, SHA-256 |

- 받은 원본은 `data/raw/public/<데이터셋>/`에 두고 Git에 추적하지 않는다(재배포 조건 미확인). 매니페스트(출처·일시·해시)는 추적한다.
- Kaggle API 토큰은 사용자 PC에만 두고 결과·로그에 기록하지 않는다.
- M5 대신 라이선스가 명확한 다른 공개 데이터를 쓸지 여부는 산업데이터·KPI 조사 담당의 공개 데이터 조사 결과와 함께 결정한다.
