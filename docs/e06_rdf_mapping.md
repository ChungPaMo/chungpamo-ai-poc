# E06 RDF 매핑 — E01 정규 엔터티 → RDF

> 작성 2026-10-21. 변환기 `scripts/e06_build_rdf.py`, 어휘 `ontology/e06_minimal.ttl`(변환기가 E01 모델 정의에서 생성). OWL 추론 미사용.
> 정상 데이터 그래프 예시: `results/E06_rdf_shacl/clean_graph.nt`(정렬된 N-Triples, 합성 데이터).

## 1. 원칙

| 요구 | 구현 |
|---|---|
| 기존 ID ↔ URI 결정론적 대응 | 레코드 IRI = `rec/{record_uid}`, 업무 키 IRI = `id/{엔터티}/{키 값…}` (값은 퍼센트 인코딩). 난수·순번 없음 |
| 객체 관계와 리터럴 구분 | 참조 필드(아래 §3)만 IRI(객체 속성), 나머지는 리터럴(데이터 속성) |
| 데이터 타입 명시 | E01 모델 타입 → `xsd:decimal`·`xsd:integer`·`xsd:boolean`·`xsd:date`, 문자열·열거값은 일반 리터럴 |
| 수량·단위·날짜 유지 | 수량은 원래 어휘형 그대로(단위 환산 안 함), 단위는 `id/Unit/{코드}` IRI, 날짜는 `xsd:date` |
| BOM 버전·유효기간 유지 | BOM 레코드에 `cp:BOM_bom_version`, `valid_from`, `valid_to`, `min_qty`, `max_qty`, `site_id`, `status`, `is_active` 그대로 |
| 데이터 계보 | 모든 레코드 → `cp:inDataset` → 데이터셋 노드(`cp:datasetId`, `cp:datasetSha256`, `cp:groundTruthSha256`, `cp:builtBy`) |
| 동일 엔터티 중복 생성 방지 | 같은 업무 키를 가진 레코드는 같은 키 노드를 가리킨다(`cp:hasKey`). 업무 키에서 개체를 하나로 합치지 않고 레코드는 레코드별로 남긴다 → 중복 ID(S08)를 그래프에서 볼 수 있음 |
| 참조 대상 누락 시 실체를 만들지 않음 | 키 노드의 `rdf:type`(예: `cp:Product`)은 **그 키의 마스터 레코드가 있을 때만** 붙인다. 참조만 있으면 타입 없는 IRI로 남고, SHACL `sh:class`가 이를 위반으로 본다 |
| 원본 의미 보존 확인 | `round_trip()`: 그래프에서 레코드를 다시 읽어 원본 dict와 필드·어휘형 비교. 정상 데이터와 평가셋 72개 모두 불일치 0 (`accuracy.json` round_trip) |

## 2. 노드 구조

```
rec/rec_xxxxxxxxxxxxxxxx  a cp:BOMLineRecord ;                 # 원본 레코드 1건
    cp:BOMLine_record_uid "rec_…" ; cp:BOMLine_line_no "2"^^xsd:integer ;
    cp:BOMLine_qty_per "1.2"^^xsd:decimal ; cp:BOMLine_component_type "MATERIAL" ;
    cp:BOMLine_bom_id <id/BOM/BOM-FG001-V1> ;                   # 참조 → 업무 키 IRI
    cp:BOMLine_component_material_id <id/Material/M001> ;
    cp:BOMLine_unit <id/Unit/kg> ;
    cp:hasKey <id/BOMLine/BOM-FG001-V1/2> ;                     # 자기 업무 키
    cp:inDataset <dataset/clean> .
rec/rec_yyyy… a cp:MaterialRecord ; cp:hasKey <id/Material/M001> ; …
<id/Material/M001> a cp:Material .                              # 마스터 레코드가 있을 때만
```

- 속성 IRI는 `cp:{엔터티}_{필드}`(예: `cp:BOM_product_id`). 같은 이름의 필드(product_id 등)가 엔터티마다 의미가 다르므로 엔터티별로 나눴다. 그 덕분에 SPARQL에서 다른 레코드의 `rdf:type` 패턴 없이 조인할 수 있다.
- 마스터(타입을 붙이는) 엔터티: Unit, Product, Material, Supplier, BOM, Resource, ProductionPlan.
- 업무 키: E05와 같다 — BOMLine(bom_id, line_no), SupplierMaterial(supplier_id, material_id), SalesHistory(product_id, period_start, period_grain), Inventory(item_type, item_id, as_of_date), Operation(operation_id)와 Operation 순번 키(product_id, sequence_no), ProductionPlanLine(plan_id, line_no). 키 값 중 하나라도 null·빈 값이면 키 노드를 만들지 않는다(E05 중복 검사와 같은 조건).

## 3. 참조 필드

| 엔터티.필드 | 대상 키 노드 |
|---|---|
| Unit.base_unit_code, Product.base_unit, Material.base_unit, BOMLine.unit, Order.unit, Inventory.unit, ProductionPlanLine.unit | `id/Unit/…` |
| BOM.product_id, BOMLine.component_product_id, Order.product_id, SalesHistory.product_id, Operation.product_id, ProductionPlanLine.product_id | `id/Product/…` |
| BOMLine.component_material_id, SupplierMaterial.material_id | `id/Material/…` |
| SupplierMaterial.supplier_id | `id/Supplier/…` |
| BOMLine.bom_id | `id/BOM/…` |
| Operation.resource_id, ProductionPlanLine.resource_id | `id/Resource/…` |
| ProductionPlanLine.plan_id | `id/ProductionPlan/…` |
| Inventory.item_id | item_type이 PRODUCT면 `id/Product/…`, MATERIAL이면 `id/Material/…` (조건부 — 변환기가 item_type 값으로 대상을 고른다) |

SalesHistory.derived_from_record_uid는 E01 정답셋 밖(공개 데이터 스테이징)의 레코드를 가리키므로 리터럴로 둔다.

## 4. 값 변환 규칙과 변환 기록

| 원본 값 | RDF |
|---|---|
| null(None) | 트리플 없음 (RDF로는 'null'과 '값이 주어지지 않음'을 구분할 수 없다) |
| 빈 문자열 "" | 리터럴 "" (선언 타입이 decimal·date면 형식이 틀린 리터럴) |
| 숫자·날짜·불리언 | 선언 타입 리터럴, 어휘형은 원본 문자열 그대로. 변환기는 맞는지 판정하지 않는다 |
| 참조 값이 비어 있거나 문자열이 아님 | IRI 대신 리터럴 (SHACL `sh:class`·`sh:minLength`가 위반으로 봄) |
| 모델에 없는 필드 | 일반 리터럴 속성 `cp:{엔터티}_{필드}`로 그대로 옮김 (SC5 시나리오) |

변환 기록(`conversion_notes`): rdflib가 형식이 틀린 리터럴로 표시한 값(`ill_typed`)과 IRI로 만들 수 없는 참조 값. **SHACL 검출로 세지 않고** 따로 집계한다.

### 4.1 rdflib 리터럴 해석의 한계 (실측)

rdflib 7.6.0은 xsd:decimal을 Python `Decimal()`로 해석해서, XSD 어휘 규칙상 틀린 `NaN`, `INF`, `1e3`, `' 12'`, `'+5'`, 전각 숫자 `１２`, `1_000`을 **정상 리터럴**로 받아들인다. `2026-11-15T00:00`도 정상 `xsd:date`로 받아들인다. 따라서 `sh:datatype`도 이 값들을 위반으로 보지 않는다 — E05에서 Pydantic lax 모드에 있던 결함과 같은 종류다(SQLite 질의는 모두 거부). `1O50`, `2026-02-30`, `2026/11/15`, `3.0`(정수), `yes`(불리언)는 형식 오류로 표시된다.

## 5. 열린 세계 가정과 SHACL 판정의 구분

| 상황 | RDF 표현 | SHACL 판정 |
|---|---|---|
| 누락된 관계 (필수 참조 없음) | 해당 속성 트리플 없음 | `sh:minCount 1` → S01 |
| 존재하지 않는 대상 참조 | 타입 없는 키 IRI를 가리킴 | `sh:class` → R01~R07 |
| 존재하지만 잘못 연결된 관계 (예: 자재 열에 제품 ID) | `id/Material/FG001`(타입 없음)을 가리킴 | `sh:class cp:Material` → R02 |
| 매핑되지 않은 외부 코드 (I-R02b) | 업체 코드로 만든 키 IRI(타입 없음) | `sh:class` → R02 |
| 타입이 잘못된 속성 | 형식이 틀린 리터럴 | `sh:datatype` → S02·S03 (§4.1의 예외 있음) |
| 명시되지 않은 사실 (선택 속성 null) | 트리플 없음 | 위반 아님. 추론으로 값을 만들지 않는다 |

RDF 자체는 열린 세계라 "없는 대상"을 알 수 없다. 이 PoC는 **변환기가 마스터 레코드에서만 타입을 만든다**는 폐쇄적 규칙과 SHACL `sh:class`의 조합으로 참조 무결성을 판정한다. 다른 출처의 그래프를 합치면(예: 다른 시스템이 `id/Material/M999 a cp:Material`을 추가) 판정이 바뀔 수 있다.
