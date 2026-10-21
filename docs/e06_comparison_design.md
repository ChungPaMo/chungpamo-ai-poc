# E06 RDF/SHACL 비교 실험 설계 (E05 결과 기반)

> 작성 2026-10-21. **설계만 작성했고 RDF/SHACL 구현은 시작하지 않았다.** 패키지(rdflib, pyshacl) 미설치·미승인 (D-003).
> Baseline: E05 `python_full`, `sql_queries` ([e05_data_validation_report.md](e05_data_validation_report.md)). SHACL 도입 필요성은 미리 정하지 않는다.

## 1. 비교 원칙

- **같은 평가셋·같은 정답**: E05 평가셋 v1(72개, sha256 `d666c160…`)과 정답을 그대로 쓴다. E06이 새 정답을 만들지 않는다. 데이터셋 해시로 입력 동일성을 확인한다.
- **같은 결과 구조**: dataset_id, rule_id, entity_id(record_uid), field_path, severity, detected, actual_value, expected_constraint, explanation, evidence. 채점은 `scripts/e05_score.py`를 그대로 쓴다.
- **같은 규칙 ID**: `configs/e05_validation_rules.json`의 rule_id. 카탈로그 `shacl_fit`(CORE / SPARQL / PARTIAL / NOT_SUITABLE)은 설계 추정이며 E06에서 실제로 확인한다.
- **E05가 이미 충분하면 그 사실을 결론으로 둔다** (E06 보류·후속 분리 근거, experiment_plan E05 11항).

## 2. E05에서 확인된 기준선

| 항목 | E05 실측 |
|---|---|
| 정확도 (ERROR, 구현 일치도) | python_full·sql_queries 모두 TP 99 / FP 0 / FN 0, 사건 63/63, 규칙 41/41 |
| 정상·경계 통과 오탐 | 0 (네 방식 모두) |
| 단독 한계 | Pydantic만: 재현율 0.313 (참조·집계·관계 규칙 불가, model_validator 가림). SQLite 제약만: 재현율 0.505, 연쇄 거부 오탐 114, 행당 첫 위반만 |
| 성능 L(17,454 레코드) | 검증 python_full 0.21 s, sql_queries 0.33 s(+적재 0.05 s), 피크 RSS 55~59 MB |
| 코드 | Python 검증기 416줄, SQL 검증기 394줄(생성 질의 308개) |

→ E06의 질문은 "정확도를 올릴 수 있는가"가 아니라(현재 평가셋으로는 올릴 여지 없음) **표현·수정·추적·관계 탐색이 나아지는가, 그 대가(변환 비용)는 얼마인가**다.

## 3. 문제별 검토

질문: ① SQL/Python으로 이미 충분히 해결됐는가 ② SHACL로 더 명확하게 표현할 수 있는가 ③ 규칙 추가·수정이 쉬워질 가능성 ④ 관계 탐색이 실제로 단순해질 가능성 ⑤ RDF 변환 비용이 이익보다 클 가능성 ⑥ 지식그래프 없이도 충분한가

| 문제 | 관련 규칙 | ① | ② | ③ | ④ | ⑤ | ⑥ | E06 측정 |
|---|---|---|---|---|---|---|---|---|
| BOM 계층(다단계·순환) | B01, P-05 | 예 (Python DFS, SQL 재귀 CTE 모두 2/2) | SHACL Core로는 불가, SHACL-SPARQL 경로식(`bom:hasComponent+`)으로 표현 가능 — 재귀 CTE보다 짧을 가능성 | 경로 깊이 변경에 강함 | **가능성 있음** (가장 유력한 비교 대상) | 중간 | 현재 규모에서는 충분 | 필수 |
| 참조 무결성 | R01~R07 | 예 (8/8, 고아·외부 코드 미매핑 포함) | Core `sh:class` + 대상 존재 — 단 RDF는 열린 세계라 "없는 대상"을 IRI 존재로 판정하려면 마스터 타입 선언 필요 | 비슷 | 아니오 | 큼 (모든 참조를 IRI로 변환) | 예 | 필수 (FN·오탐 동일성 확인) |
| 공급사–자재 관계 | R02, R03, B11 | 예 | B11(우선 공급사 정확히 1개)은 `sh:qualifiedValueShape` + `sh:qualifiedMinCount/MaxCount`로 Core 표현 가능성 | 가능성 있음 | 아니오 | 중간 | 예 | 선택 |
| 코드 매핑 | I-R02b, E02 매핑 설정 | 예 (매핑 안 된 코드는 R02로 검출) | 매핑 자체는 SHACL 범위 아님 (`owl:sameAs`·SKOS는 추론 필요 → OWL 범위, 필요성 확인 전 구현 금지) | — | 아니오 | 큼 | 예 | 제외 (설계 메모만) |
| 속성 제약 | S01~S08, B03, B05, B07, B13, B14, V01~V07, V10 | 예 | Core(`sh:datatype`, `sh:minInclusive`, `sh:in`, `sh:pattern`)로 선언적 표현 — **가장 명확해질 가능성**. 단 날짜 형식(ERR-DATE)·숫자 형식(ERR-NUMFMT)은 RDF 변환 단계에서 리터럴 생성 실패로 먼저 드러나 SHACL까지 오지 않을 수 있음 | 가능성 있음 (shape 1개 수정) | 아니오 | 중간 | 예 | 필수 (형식 오류가 어느 단계에서 잡히는지) |
| 유효기간·관계 제약 | B02, B06, V08, V09, V12 | 예 | B02(기간·수량·사이트 동시 겹침)·B06(선택 후보 개수)은 비교 연산이 많아 SHACL-SPARQL 필요, SQL 자기 조인과 길이 비슷할 것으로 예상 | 불확실 | 아니오 | 중간 | 예 | 필수 (B02·B06) |
| 생산능력 계산 | V13 | 예 (GT와 36/36 일치) | 집계·계산이라 SHACL 대상 아님 | — | — | — | 예 | 제외 |

## 4. E06 측정 항목

1. 규칙별 정확도 — E05와 같은 채점기 (TP·FP·FN, 사건·규칙 단위, 정상·경계 오탐)
2. 표현 비용 — TTL 매핑 규칙 수, shape 수·줄 수, SPARQL 제약 줄 수 (규칙 ID별). E05 비교값: `results/E05_schema_sql/complexity.json`
3. 수정 범위 — 같은 변경(예: B02에 site_id 조건 추가, 우선 공급사 개수 규칙 변경)을 E05·E06에 각각 적용했을 때 바뀌는 파일·줄
4. 변환 비용 — JSON → RDF 그래프 생성 시간·트리플 수·메모리, S/M/L 같은 배율, 3회 중앙값
5. 검증 시간·메모리 — pySHACL 실행
6. 추적성 — 보고에서 record_uid·필드를 되찾을 수 있는가 (focus node·result path → rule_id·field_path 대응)
7. 형식 오류 처리 단계 — 리터럴 변환 실패를 어디서 어떻게 보고하는가 (E05 보조 관찰의 `NaN`·`1e3` 경계 포함)

## 5. 범위 제한

- 최소 온톨로지(개념 10개 이내, experiment_plan E06), OWL 추론 미사용.
- 대상 규칙: 3절 "필수" 행 규칙 우선. 전 규칙 이식은 하지 않는다.
- GraphDB(E07)·웹 UI·운영 연동 없음.
- 착수 전 필요: rdflib·pyshacl 설치 승인, E05 검토 완료.
