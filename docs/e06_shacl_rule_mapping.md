# E06 SHACL 규칙 대응 — E05 규칙 42개 ↔ SHACL shape

> 작성 2026-10-21. 생성기 `scripts/e06_shapes.py` → `ontology/e06_shapes.ttl`(기본, shape 418개), `ontology/e06_shapes_core_compare.ttl`(비교 제약 Core 변형).
> 결과 대응: 모든 shape에 IRI와 `cp:ruleId`(E05 규칙 ID)·`cp:fieldName`(보고 필드)·`cp:engine`(CORE/SPARQL)을 달았다. 검증 결과의 `sh:sourceShape`로 규칙을 찾고, `sh:focusNode`(레코드 IRI)의 `cp:{엔터티}_record_uid`로 레코드를 찾는다. 대응되지 않은 결과는 `unmapped_results`로 따로 센다.

## 1. 분류 기준

1. SHACL Core로 직접 표현
2. SHACL-SPARQL(`sh:sparql` SELECT)로 표현
3. RDF 전처리 또는 외부 Python 검증 필요
4. SHACL보다 SQL/Python이 적합
5. 미지원 또는 검증 범위 밖

## 2. 규칙별 대응

| 규칙 | E05 오류 코드 | 분류 | SHACL 구성 | E05와의 의미 차이·비고 |
|---|---|---|---|---|
| S01 필수 누락 | ERR-MISSING | 1 | `sh:minCount 1` + `sh:minLength 1`(빈 문자열) | 빈 날짜·숫자는 `sh:datatype`도 함께 위반(S03·S02 추가 보고 = 부분 탐지) |
| S02 숫자 형식 | ERR-NUMFMT | 1 (+3) | `sh:datatype xsd:decimal/integer/boolean` | 판정은 rdflib 리터럴 해석에 의존(변환 단계). `NaN`·`1e3`·전각 숫자 등을 정상으로 봄 ([매핑 §4.1](e06_rdf_mapping.md)) |
| S03 날짜 형식 | ERR-DATE | 1 (+3) | `sh:datatype xsd:date` | `2026-02-30`은 위반, `2026-11-15T00:00`은 정상으로 봄 (rdflib) |
| S04 열거값 | ERR-ENUM | 1 | `sh:in (…)` | — |
| S05 record_uid 형식 | ERR-IDFMT | 1 | `sh:pattern` | — |
| S06 숫자 범위 | ERR-NUMFMT | 1 | `sh:minExclusive`·`minInclusive`·`maxExclusive`·`maxInclusive` | 형식이 틀린 값도 범위 위반으로 보고(부분 탐지). `NaN` 값이 있으면 pyshacl이 `InvalidOperation`으로 검증 전체 중단(평가셋에는 없음) |
| S07 선택 필드 빈 문자열 (합성 가정) | ERR-MISSING | 1 | `sh:minLength 1`, `sh:Warning` | — |
| S08 업무 키 중복 | ERR-DUPID | 2 | 같은 `cp:hasKey`를 가진 다른 레코드 | Core 대안: 키 노드에 `[sh:inversePath cp:hasKey] sh:maxCount 1` — 보고 대상이 키 노드가 되어 레코드 추적에 후처리가 필요 |
| R01~R07 참조 | ERR-BADREF·ERR-RESREL·ERR-UNIT | 1 | `sh:class cp:{대상}`. BOMLine 구성품·Inventory item_id는 `sh:or ( [sh:not 유형값] [sh:class …] )`로 조건부 | 판정은 "마스터 레코드가 있을 때만 키 노드에 타입" 변환 규칙에 의존 (열린 세계 → [매핑 §5](e06_rdf_mapping.md)) |
| B01 BOM 순환 | ERR-BOMCYCLE | 2 | 속성 경로 `(^BOM_product_id/hasKey/^BOMLine_bom_id/BOMLine_component_product_id)+` | 경로 중간 간선에는 `component_type = PRODUCT` 조건을 걸 수 없음(E05는 모든 간선에 조건). 순환 경로 자체는 반환하지 않고 존재만 판정 |
| B02 활성 버전 조건 중복 | ERR-BOMVER | 2 | 자기 조인 + 판정식 FILTER | Core 불가(두 노드 비교) |
| B03 미승인 활성 | ERR-BOMVER | 2 | FILTER | Core(`sh:or`)로도 가능 — SPARQL로 작성 |
| B04 제품·버전 표기 중복 | ERR-BOMVER | 2 | 자기 조인 | — |
| B05 유효 조건 자체 오류 | ERR-BOMVER | 2 (Core 가능) | FILTER(`valid_to < valid_from`, `max_qty <= min_qty`) | Core `sh:lessThanOrEquals`·`sh:lessThan`으로 표현 가능하나 pyshacl 0.40.1은 비교 대상에 형식이 틀린 리터럴이 있으면 `TypeError`로 **검증 전체가 중단** → SPARQL로 대체(변형 실행으로 측정) |
| B06 계획 라인 BOM 선택 불가·모호 | ERR-BOMVER | 2 | 후보 없음 `FILTER NOT EXISTS`, 모호 = 서로 다른 후보 2개 | 날짜·수량을 해석할 수 없는 라인은 비교 가드로 건너뜀 (E05와 같음) |
| B07 구성품 유형·열 불일치 | ERR-BADREF | 1 | `sh:or`·`sh:and`·`sh:hasValue`·`sh:maxCount 0` | component_type이 없으면 위반으로 봄(E05는 건너뜀) |
| B08 단위 차원 불일치 | ERR-UNIT | 2 | 단위 레코드 두 번 조인 | 4개 엔터티별 shape |
| B09 라인 없는 BOM (합성 가정) | ERR-BOMVER | 1 | 순서 경로 `( cp:hasKey [ sh:inversePath cp:BOMLine_bom_id ] )` + `sh:minCount 1` | — |
| B10 같은 구성품 중복 (합성 가정) | ERR-DUPID | 2 | 자기 조인 | — |
| B11 우선 공급사 ≠ 1 | ERR-DUPID | 2 | 없음: `FILTER NOT EXISTS`, 여럿: `GROUP BY … HAVING COUNT > 1` | Core `sh:qualifiedValueShape`는 자재 키 노드를 대상으로 해야 해서 레코드 보고가 어려움 |
| B12 배분 비율 합 ≠ 1 | ERR-NUMFMT | 2 (→4) | `GROUP BY $this … HAVING (ABS(SUM)…)` | SHACL-SPARQL은 `$this` 사전 바인딩 때문에 `$this`를 고르지 않는 중첩 SELECT를 쓸 수 없음(pyshacl이 shape 거부). 집계 질의가 rdflib에서 규모에 따라 비선형으로 느려짐 → 집계 규칙은 SQL/Python이 적합 |
| B13 ALLOCATED 필수 | ERR-MISSING | 1 | `sh:or ( [sh:not hasValue] [minCount] )` 2개 | 둘 다 없으면 두 필드 모두 보고(E05는 하나) |
| B14 외주 단가 | ERR-MISSING | 1 | `sh:or`·`sh:and`·`sh:hasValue true/false` | — |
| V01 음수 재고 | ERR-INVQTY | 1 | `sh:minInclusive 0` | — |
| V02 할당 > 보유 | ERR-INVQTY | 2 (Core 가능) | FILTER | B05와 같은 이유로 SPARQL |
| V03 EA 소수 | ERR-INVQTY | 2 | `FLOOR` 비교, 3개 필드 | — |
| V04 재고 키 중복 | ERR-INVQTY | 2 | S08과 같음 | — |
| V05 입고 예정일 | ERR-DATE | 1 | `sh:or ( [maxInclusive 0] [minCount 1] )` | — |
| V06 기준일 이후 재고 | ERR-DATE | 1 | `sh:maxInclusive "2026-11-15"^^xsd:date` (생성 시 매개변수 대입) | 형식이 틀린 날짜도 위반으로 보고(부분 탐지) |
| V07 납기 < 주문일 | ERR-DATE | 2 (Core 가능) | FILTER | B05와 같은 이유로 SPARQL |
| V08 공정 없는 제품 | ERR-RESREL | 2 | `FILTER NOT EXISTS` | — |
| V09 공정에 없는 자원 | ERR-RESREL | 2 | `FILTER EXISTS` + `NOT EXISTS` | — |
| V10 외주·자원 규칙 | ERR-RESREL | 2 | `BIND(EXISTS …)` 비교 | Core로는 "열거값이 둘 중 하나일 때만" 조건을 쓰기 번거로움 |
| V11·V12 (합성 가정) | ERR-RESREL·ERR-DATE | 2 | 조인 + FILTER, `sh:Warning` | — |
| V13 생산능력 (INFO) | — | 4 | shape 없음 | 공정 시간 × 수량 합, 주별 가용시간 계산은 결정론적 연산 — SHACL로 옮기지 않음. Python/SQL로 계산한 결과를 RDF에 넣고 SHACL로 "초과 여부"만 확인하는 방식은 별도 후보로만 기록(미구현) |
| N01~N06 (NOT_MEASURED) | — | 5 | — | E05와 같이 규칙 없음 |

분류 3(외부 Python 전처리)으로 **검출**한 규칙은 없다. 다만 다음은 변환기(RDF 전처리) 결정에 판정이 걸려 있다: S02·S03(리터럴 해석), R01~R07(마스터 타입 생성), Inventory.item_id(item_type으로 대상 클래스 선택), 업무 키 노드 생성(S08·V04).

## 3. 집계

| 분류 | 규칙 수 | 규칙 |
|---|---|---|
| 1 Core | 21 | S01~S07, R01~R07, B07, B09, B13, B14, V01, V05, V06 (S06과 V01은 같은 범위 생성기) |
| 2 SPARQL | 20 | S08, B01~B06, B08, B10~B12, V02~V04, V07~V12 (그중 B05·V02·V07은 Core 표현 가능, B03은 Core 가능) |
| 4 SQL/Python 적합 | 1 (+B12 성능) | V13 |
| 5 범위 밖 | 6 | N01~N06 |

(1·2 합계 = 채점 대상 41개, shape 418개: Core 377, SPARQL 41)

## 4. 검증 결과 → E05 오류 코드 대응 표

shape의 `cp:ruleId` → `configs/e05_validation_rules.json`의 `error_code`. 같은 레코드가 여러 shape를 위반하면 규칙별로 따로 보고하고, 채점은 E05와 같이 (규칙, 레코드, 필드) 단위와 사건 단위로 나눈다. 대응 실패(`unmapped_results`)는 `accuracy.json` runinfo에 데이터셋별로 기록된다.
