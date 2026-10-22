# E06 결과 요약 (자동 생성, scripts/e06_run.py)

- 상태: RUNNING (검토 전). 실행 2026-10-21T20:04:30+09:00, Python 3.11.9, rdflib 7.6.0, pyshacl 0.40.1
- 입력: ground_truth_v2 262dbe75dbfa…, eval_set_v1 d666c1600267… (E05와 같은 평가셋·정답·채점기)
- 정상 데이터 그래프: 4668 트리플, sha256 f7e2baac85d3…
- **해석 주의**: 평가셋·정답·규칙 카탈로그·shape를 같은 작성자가 만들었다. 수치는 카탈로그 규칙의 SHACL 표현 일치도이며 일반화 성능이 아니다.

## 정확도 (규칙 단위)

| 방식 | 심각도 | TP | FP | FN | Precision | Recall | F1 | 사건 | 규칙 검출/기대 |
|---|---|---|---|---|---|---|---|---|---|
| shacl_pyshacl | ERROR | 99 | 0 | 0 | 1.0 | 1.0 | 1.0 | 63/63 | 41/41 |
| shacl_pyshacl | WARNING | 5 | 1 | 0 | 0.8333 | 1.0 | 0.9091 | 5/5 | 41/41 |
| shacl_hybrid | ERROR | 99 | 0 | 0 | 1.0 | 1.0 | 1.0 | 63/63 | 41/41 |
| shacl_hybrid | WARNING | 5 | 1 | 0 | 0.8333 | 1.0 | 0.9091 | 5/5 | 41/41 |
| shacl_core_compare | ERROR | 90 | 0 | 9 | 1.0 | 0.9091 | 0.9524 | 61/63 | 41/41 |
| shacl_core_compare | WARNING | 5 | 1 | 0 | 0.8333 | 1.0 | 0.9091 | 5/5 | 41/41 |
| E05 python_full | ERROR | 99 | 0 | 0 | 1.0 | 1.0 | 1.0 | | |
| E05 sql_queries | ERROR | 99 | 0 | 0 | 1.0 | 1.0 | 1.0 | | |

- 정상·경계 통과 오탐: shacl_pyshacl 0, shacl_hybrid 0, shacl_core_compare 0
- 검출 출처(shacl_pyshacl 전체 보고): {'shacl_core': 52, 'shacl_sparql': 136}, 정답 레코드에 대한 보고: {'shacl_core': 46, 'shacl_sparql': 58}
- 변환 단계 기록이 있는 데이터셋: 6개, 그중 기대 항목과 겹친 기록 6건 (SHACL 채점에 넣지 않음)
- pyshacl 결과 = hybrid 결과: 72/72, pyshacl 반복 실행 일치: 18/18
- RDF 재생성 해시 일치: 72/72, 왕복 불일치 합계: 0
- Core 비교 제약 변형에서 pyshacl 중단: 2개 데이터셋 — C-3: TypeError: '<=' not supported between instances of 'Literal', I-S03a: TypeError: '<=' not supported between instances of 'Literal'

- E05 python_full와 검출 규칙·오탐이 다른 데이터셋: 0개 
- E05 sql_queries와 검출 규칙·오탐이 다른 데이터셋: 0개 

## Q1~Q5 관계 조회 (기대 정답 = GT expected.cq)

| 방식 | Q1 | Q2 | Q3 | Q4 | Q5 | Q1~Q5 1회 s | 준비 s | 피크 RSS MB |
|---|---|---|---|---|---|---|---|---|
| python | 19/19 | 4/4 | 10/10 | 6/6 | 2/2 | 0.0003 | 0.0 | 42.7 |
| sqlite | 19/19 | 4/4 | 10/10 | 6/6 | 2/2 | 0.0009 | 0.004 | 45.1 |
| sparql | 19/19 | 4/4 | 10/10 | 6/6 | 2/2 | 0.7439 | 0.07 | 62.0 |
| sparql_naive | 19/19 | 4/4 | 10/10 | 6/6 | 2/2 | 0.7847 | 0.074 | 62.1 |

- 판별 사례(중간 BOM 비활성): {'python': [], 'sqlite': [], 'sparql': [], 'sparql_naive': ['P0']} (기대 [])

BOM 단계 증가(Q2, 합성 사슬) — 중앙값 s / 정답 여부

| 깊이 | python | sqlite | sparql | sparql_naive |
|---|---|---|---|---|
| 2 | 1e-05 / True | 4e-05 / True | 0.01091 / True | 0.00628 / True |
| 4 | 1e-05 / True | 4e-05 / True | 0.01145 / True | 0.00685 / True |
| 8 | 1e-05 / True | 8e-05 / True | 0.01295 / True | 0.00709 / True |
| 16 | 4e-05 / True | 0.0001 / True | 0.01568 / True | 0.00707 / True |
| 32 | 0.00014 / True | 0.00019 / True | 0.01807 / True | 0.00715 / True |
| 64 | 0.00059 / True | 0.00018 / True | 0.02407 / True | 0.00784 / True |

## 규칙·스키마 변경

| 시나리오 | 방식 | 바뀐 파일 | 바뀐 줄 | 회귀: 결과가 바뀐 데이터셋 | 변경 후 정상 데이터 보고 |
|---|---|---|---|---|---|
| SC1 | python | 1 | 2 | 72 | 7 |
| SC1 | sqlite | 1 | 2 | 72 | 7 |
| SC1 | shacl | 1 | 2 (생성된 TTL 10줄) | 72 | 7 |
| SC2 | python | 1 | 4 | 72 | 3 |
| SC2 | sqlite | 1 | 4 | 72 | 3 |
| SC2 | shacl | 1 | 4 (생성된 TTL 8줄) | 72 | 3 |
| SC3 | python | 1 | 2 | 1 | 0 |
| SC3 | sqlite | 1 | 2 | 1 | 0 |
| SC3 | shacl | 1 | 2 (생성된 TTL 6줄) | 1 | 0 |
- SC4 자재 코드 체계 변경 — M001 → MAT-0001 (데이터 이전, 규칙 변경 없음): {"records_changed": 50, "field_values_changed": 50, "rdf_triples_removed": 92, "rdf_triples_added": 92, "rdf_note": "업무 ID에서 IRI를 만들므로 자재 키 노드 IRI가 바뀌고, 그 IRI를 가리키는 참조 트리플도 함께 바뀜", "after_change_errors": {"python": 0, "sqlite": 0, "shacl": 0}}
- SC5 BOM 속성 추가 — 선택 속성 revision_note (모델·테이블 미반영 상태로 데이터에 먼저 등장): {"pydantic_raw_errors": ["extra_forbidden"], "pydantic_raw_error_count": 7, "python_full_reports": 0, "python_note": "E05 검증기는 pydantic 오류 유형 extra_forbidden을 규칙에 대응시키지 않아 보고 없이 넘어감", "sqlite_column_exists": false, "sqlite_note": "적재 테이블 열이 모델 필드에서 정해져 새 속성 값은 적재되지 않고 사라짐", "rdf_triples_with_new_property": 7, "shacl_reports": 0, "rdf_note": "변환기가 레코드의 모든 키를 속성으로 옮기므로 값은 그래프에 남고, shape가 없어 검증 대상은 아님 (열린 세계)"}

## 성능 (자식 프로세스 3회 중앙값, 오류 섞인 C-1 데이터)

| 방식 | 배율 | 레코드 | 트리플 | Turtle KB | 변환 s | 직렬화 s | 로딩 s | 검증 s | 파이프라인 s | 피크 RSS MB(부모 합산) | 피크 MB(자체 기록) | SPARQL Q2·Q5 s | 비고 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| python_full | 1 | 353 | - | - | 0.0 | - | - | 0.0035 | 0.0035 | 35.2 | - | - | E05 검증기 재측정(같은 세션). convert_s = SQLite 적재(Python은 0) |
| sql_queries | 1 | 353 | - | - | 0.0018 | - | - | 0.0095 | 0.0114 | 36.8 | - | - | E05 검증기 재측정(같은 세션). convert_s = SQLite 적재(Python은 0) |
| shacl_hybrid | 1 | 353 | 4666 | 278 | 0.0586 | 0.151 | 0.1406 | 1.8784 | 2.2356 | 80.1 | 76.8 | 0.0235 |  |
| shacl_pyshacl | 1 | 353 | 4666 | 278 | 0.058 | 0.1477 | 0.1377 | 16.0143 | 16.3593 | 78.8 | 75.4 | 0.0237 |  |
| python_full | 10 | 3494 | - | - | 0.0 | - | - | 0.0311 | 0.0311 | 40.0 | - | - | E05 검증기 재측정(같은 세션). convert_s = SQLite 적재(Python은 0) |
| sql_queries | 10 | 3494 | - | - | 0.0092 | - | - | 0.045 | 0.055 | 41.5 | - | - | E05 검증기 재측정(같은 세션). convert_s = SQLite 적재(Python은 0) |
| shacl_hybrid | 10 | 3494 | 46273 | 2787 | 0.6343 | 1.7654 | 1.5043 | 67.2822 | 71.1888 | 186.3 | 183.3 | 0.0727 |  |
| shacl_pyshacl | 10 | 3494 | 46273 | 2787 | 0.6315 | 1.8451 | 1.4914 | 287.2629 | 291.3109 | 201.7 | 198.4 | 0.0691 |  |
| python_full | 50 | 17454 | - | - | 0.0 | - | - | 0.2013 | 0.2013 | 55.7 | - | - | E05 검증기 재측정(같은 세션). convert_s = SQLite 적재(Python은 0) |
| sql_queries | 50 | 17454 | - | - | 0.0486 | - | - | 0.3148 | 0.3639 | 58.9 | - | - | E05 검증기 재측정(같은 세션). convert_s = SQLite 적재(Python은 0) |
| shacl_hybrid | 50 | 17454 | 231193 | 13970 | 3.6319 | 13.4584 | 7.6364 | 1540.2522 | 1564.8809 | 708.3 | 705.3 | 0.2764 |  |
| shacl_pyshacl | 50 | 17454 | 231193 | 13970 | 3.5026 | 13.3387 | 7.557 | 4188.9484 | 4213.5185 | 730.4 | 727.1 | 0.2704 |  |

## 구현 규모

```
{"e06_build_rdf.py": 206, "e06_shapes.py": 256, "e06_validate_shacl.py": 140, "e06_queries.py": 415, "e05_validate_python.py": 416, "e05_validate_sql.py": 394, "e06_shapes.ttl": {"lines": 1778, "bytes": 141097}, "e06_minimal.ttl": {"lines": 175}, "dependencies": {"rdflib": "7.6.0", "pyshacl": "0.40.1", "owlrl": "7.6.2", "pyparsing": "3.3.3", "prettytable": "3.18.0", "html5rdf": "1.2.1"}}
```
