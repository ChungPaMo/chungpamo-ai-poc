# 온톨로지 설계 패턴 검토 — E01

- 작성일: 2026-10-20 (설계안, **RDF/OWL 미구현**)
- 판단 기준: [ontology_competency_questions.md](ontology_competency_questions.md)의 CQ에 답하는 데 필요한 구조만 채택한다.
- 데이터 모델: [manufacturing_data_schema.md](manufacturing_data_schema.md) §4 (SQL·RDF 대응표)

## 0. 출처와 지위 표기

| 출처 | 지위 | 이 문서에서의 확인 수준 |
|---|---|---|
| W3C "Defining N-ary Relations on the Semantic Web" https://www.w3.org/TR/swbp-n-aryRelations/ | **W3C Working Group Note (2006-04-12)** — 권고안(Recommendation)이 아님. 문서 스스로 "may be updated, replaced or obsoleted"라고 밝힘 | 원문 조회 [확인] |
| W3C PROV-O https://www.w3.org/TR/prov-o/ | W3C Recommendation (2013-04-30) | 원문 조회 [확인] |
| W3C Time Ontology in OWL https://www.w3.org/TR/owl-time/ | **W3C Candidate Recommendation Draft (2022-11-15)** — 최종 권고안 아님 | 원문 조회 [확인] |
| QUDT https://www.qudt.org/ | QUDT.org(비영리 단체) 발행 어휘, CC BY 4.0. W3C 표준 아님 | 홈페이지 조회 [확인]. 개별 클래스 정의는 [미확인] |
| Ontology Design Patterns 포털 (ontologydesignpatterns.org) | 연구 커뮤니티 카탈로그. 표준 아님 | 이번 조사에서 접근하지 않음 [미확인] |
| Dynamics 365 BOM(S1), Odoo BOM(S3) | 상용·오픈소스 ERP 문서. 표준 아님, 실무 구조의 근거 | 원문 조회 [확인] |

"국제표준"이라는 표현은 W3C Recommendation 등 공식 표준 지위가 확인된 경우에만 쓰고, Working Group Note·커뮤니티 패턴은 "참고 패턴"으로 부른다.

## 1. 판단 원칙: 직접 관계 vs 관계 클래스

| 경우 | 표현 | 이유 |
|---|---|---|
| 관계에 붙는 속성이 없고 1:N 또는 N:1 | **직접 관계** (객체 속성 1개, SQL FK 1개) | 가장 단순. 질의도 짧음 |
| 관계 자체에 수량·단위·기간·순서 등 속성이 있음 | **관계 클래스** (N-ary Relations Note의 Pattern 1: 관계를 클래스로 만들고 각 참여자를 별도 속성으로 연결) | RDF 트리플 하나에는 속성을 붙일 수 없으므로 중간 노드 필요. SQL에서는 연결 테이블과 같음 |
| 같은 대상의 시점별 값 (재고 수량 등) | **스냅숏 클래스** (관계 클래스의 일종) | 기준일마다 값이 다름 |

N-ary Note는 관계 클래스가 OWL 제약과 역관계 표현을 복잡하게 만든다는 단점도 적고 있다 [확인]. 따라서 속성이 없는 관계는 직접 관계로 둔다.

## 2. 관계별 검토

### 2.1 Product–BOM–Material

| 항목 | 내용 |
|---|---|
| 필요 CQ | CQ-04, 05, 06, 10, 17, 18 |
| 관계 속성 | 소요량, 단위, 손실률, 라인 번호, 소속 BOM 버전 |
| 결정 | **관계 클래스 `BOMLine` + 버전 노드 `BOM`** |
| 구조 | `Product ←bomFor— BOM ←partOfBOM— BOMLine —component→ Material | Product(반제품)` |
| 근거 | S1: BOM은 ID·이름·라인·버전으로 구성되고, 라인은 구성품별 계획 소비량과 속성을 가짐 [확인]. S3: Components 탭의 구성품별 행 [확인]. N-ary Note Use Case 1(관계에 속성 추가) [확인] |
| 직접 관계로 부족한 이유 | `Product hasComponent Material`만으로는 소요량·단위를 붙일 수 없고, 버전별 구성 차이를 표현할 수 없음 |
| 보조 선택지 | CQ-05·10처럼 경로만 필요한 질의를 단순화하려고 `Product hasComponent Material` 같은 **파생 직접 관계**를 질의 시점에 계산해 둘 수 있다(원본 사실 아님, 파생 표시 필요). 채택 여부는 E06에서 질의 복잡도를 보고 결정 |
| 참고(미확인) | 커뮤니티 카탈로그의 부분-전체(part-whole) 계열 패턴은 수량 속성을 다루지 않아 BOM에는 단독으로 부족할 것으로 보이나, 원문을 확인하지 않았다 |

### 2.2 Product–Operation–Resource

| 항목 | 내용 |
|---|---|
| 필요 CQ | CQ-01, 02, 03, 13, 14 |
| 관계 속성 | 공정 순서, 단위당 가공시간, 준비시간 |
| 결정 | **관계 클래스 `Operation`** (`forProduct`, `usesResource`, `sequenceNo`, 시간 속성) |
| 근거 | S1: BOM과 route(공정·자원)가 결합되어 원가 계산 기초가 됨 [확인]. S2: 생산오더는 생산 BOM과 route로 구성 [확인]. S3: Operation–Work Center–Default Duration [확인] |
| 직접 관계로 부족한 이유 | `Product producedOn Resource`로는 순서와 시간을 표현할 수 없음 |
| 참고 | 제조 운영 영역의 국제표준으로 IEC 62264(ISA-95) 계열이 있으나 온톨로지가 아니며, 이번 조사에서 원문을 검토하지 않았다. 용어 대응은 후속 검토 대상 |

### 2.3 Order–Product–DueDate

| 항목 | 내용 |
|---|---|
| 필요 CQ | CQ-03, 07, 11, 12, 13 |
| 관계 속성 | 수량·단위·납기는 **주문 자체의 속성** (주문 1건 = 제품 1개 가정) |
| 결정 | **직접 관계** `Order orderedProduct Product` + 데이터 속성 `orderQty`, `unit`, `orderDate`, `dueDate`(xsd:date) |
| 근거 | S2: 생산오더는 무엇을·얼마나·언제까지(계획 완료일) 정보를 가짐 [확인] |
| OWL-Time 사용 여부 | **사용하지 않음**. 납기는 하루 단위 날짜 하나이며 `xsd:date` 비교로 CQ에 답할 수 있다. OWL-Time은 CRD 상태이기도 하다 |
| 확장 시 | 한 주문에 여러 제품이 들어가면 `OrderLine` 관계 클래스가 필요하다. 현재 CQ에는 없어 두지 않는다 |

### 2.4 Supplier–Material–LeadTime

| 항목 | 내용 |
|---|---|
| 필요 CQ | CQ-09, 10, 11, 13 |
| 관계 속성 | 리드타임, 최소주문량, 우선 공급사 여부 — **공급사와 자재 쌍**에 속함 |
| 결정 | **관계 클래스 `SupplierMaterial`** (SQL 테이블과 같은 이름. 이전 안의 `SupplyAgreement`는 같은 개념이라 폐기 — [schema §4.1](manufacturing_data_schema.md)) |
| 근거 | N-ary Note Use Case 1 [확인]. 리드타임은 자재 단독 속성이 아니라 공급사마다 다름(설계 가정 A) |
| 단순화 대안 | 자재당 공급사를 1곳으로 고정하면 `Material leadTimeDays` 직접 속성으로 충분하다. CQ-09(복수 공급사 비교)를 유지할지에 따라 결정 — 현재는 CQ-09를 유지하므로 관계 클래스 채택 |

### 2.5 Inventory–Item–Quantity

| 항목 | 내용 |
|---|---|
| 필요 CQ | CQ-06, 07, 08, 11, 13 |
| 관계 속성 | 기준일, 보유·할당·입고예정 수량, 단위 |
| 결정 | **스냅숏 성격의 관계 클래스 `Inventory`** (`ofItem`, `asOfDate`, 수량 속성, `unit`). SQL 테이블과 같은 이름. 이전 안의 `InventorySnapshot`은 같은 개념이라 폐기 |
| 수량 표현 | **평면 패턴**: 수량 리터럴(`xsd:decimal`)과 단위 IRI를 같은 노드에 둔다. QUDT의 "Quantity Triad Pattern"(홈페이지 언급 [확인]) 같은 별도 수량 노드는 쓰지 않는다 — 수량마다 노드가 생겨 트리플 수와 질의 길이가 늘고, CQ에 필요한 기능(단위 환산)은 `Unit` 표로 충분하다 |
| 단위 식별자 | 프로젝트 `Unit` 표를 기본으로 하고, 필요하면 각 단위에 QUDT 단위 IRI를 대응 속성으로 붙일 수 있다(QUDT 단위 IRI 형식은 [미확인], 적용 시 확인) |

### 2.6 기간·버전 관리

| 대상 | 결정 | 근거 |
|---|---|---|
| BOM 버전 유효 조건 | BOM 노드의 데이터 속성 `validFrom`, `validTo`(xsd:date), `minQty`, `maxQty`(xsd:decimal), `siteId`, `status`, `isActive` | S1: 버전 유효성은 기간·수량·사이트 등으로 제한되고, 활성화 시 유일성 검증 [확인]. 충돌 검사(CQ-17)는 날짜·수량 구간 비교로 충분 → OWL-Time 불필요. 판정식은 [schema §3.6, §5 QR-06](manufacturing_data_schema.md) |
| 재고·판매 시점 값 | `Inventory`의 `asOfDate` / `SalesHistory`의 `periodStart` | §2.5 |
| 데이터셋 버전 | PROV-O `prov:wasRevisionOf` + 프로젝트 확장 `cpm:datasetVersion` | [data_provenance_design.md](data_provenance_design.md) §2 |
| 데이터셋별 그래프 분리 | 선택지: RDF 데이터셋의 이름 있는 그래프(named graph)를 데이터셋 버전별로 사용. SQL의 버전 열과 같은 역할. 채택 여부는 E06/E07에서 결정 | RDF 1.1 Concepts의 RDF Dataset 개념 (원문 이번 조사에서 미조회) |

## 3. 결정 요약

| 관계 | 표현 | 관계 클래스 이름(안) |
|---|---|---|
| Product–BOM–Material | 관계 클래스 + 버전 노드 | BOM, BOMLine |
| Product–Operation–Resource | 관계 클래스 | Operation |
| Order–Product–DueDate | 직접 관계 + 데이터 속성 | — |
| Supplier–Material–LeadTime | 관계 클래스 | SupplierMaterial |
| Inventory–Item–Quantity | 스냅숏 성격 관계 클래스, 평면 수량 | Inventory |
| 기간·버전 | 데이터 속성(날짜) + PROV-O | — |

모든 결정은 SQL 모델과 1:1 대응한다(관계 클래스 = 연결 테이블). 따라서 E05~E07 비교에서 **모델 표현력 차이가 아니라 저장·검증·질의 방식 차이**만 비교된다.

## 4. 미확정·후속 확인

- 파생 직접 관계(`hasComponent`) 사용 여부 — E06
- 이름 있는 그래프로 데이터셋 버전 분리 여부 — E06/E07
- 커뮤니티 패턴 카탈로그(ODP 포털), IEC 62264 용어 대응 — 필요성이 확인되면 원문 검토
- 네임스페이스·URI 정책(`cpm:` 등 이름) — E06 착수 시 결정
