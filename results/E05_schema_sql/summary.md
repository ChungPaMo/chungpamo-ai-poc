# E05 결과 요약 (자동 생성)

- 상태: RUNNING (검토 전). 실행: 2026-10-21T09:49:38+09:00, Python 3.11.9, pydantic 2.14.1, SQLite 3.45.1
- 입력: ground_truth_v2 262dbe75dbfa…, eval_set_v1 d666c1600267…, 데이터셋 {'clean': 1, 'single': 59, 'pass': 9, 'compound': 3}, 기대 항목 80
- 외부 API 호출 0. 합성 데이터만 사용.
- **해석 주의**: 평가셋(정답)과 검증기를 같은 규칙 카탈로그로 같은 작성자가 만들었다. 정답은 검증기 출력과 독립으로 정했지만, 100% 수치는 '카탈로그에 적은 규칙을 구현이 그대로 잡는가'(구현 일치도)이며 처음 보는 오류 유형·실제 데이터에 대한 일반화 성능이 아니다.

## 정확도 (규칙 단위, 심각도별)

| 방식 | 심각도 | TP | FP | FN | Precision | Recall | F1 | 사건 검출 | 규칙 검출/기대 |
|---|---|---|---|---|---|---|---|---|---|
| python_full | ERROR | 99 | 0 | 0 | 1.0 | 1.0 | 1.0 | 63/63 | 41/41 |
| python_full | WARNING | 5 | 1 | 0 | 0.8333 | 1.0 | 0.9091 | 5/5 | 41/41 |
| python_pydantic_only | ERROR | 31 | 0 | 68 | 1.0 | 0.3131 | 0.4769 | 28/63 | 17/41 |
| python_pydantic_only | WARNING | 1 | 0 | 4 | 1.0 | 0.2 | 0.3333 | 1/5 | 17/41 |
| sql_queries | ERROR | 99 | 0 | 0 | 1.0 | 1.0 | 1.0 | 63/63 | 41/41 |
| sql_queries | WARNING | 5 | 1 | 0 | 0.8333 | 1.0 | 0.9091 | 5/5 | 41/41 |
| sql_constraints | ERROR | 50 | 114 | 49 | 0.3049 | 0.5051 | 0.3802 | 46/63 | 27/41 |
| sql_constraints | WARNING | 0 | 0 | 5 | None | 0.0 | None | 0/5 | 27/41 |

TN은 (규칙, 레코드) 쌍 근사이므로 참고값이다. 정상·경계 통과 데이터 오탐: python_full 0, python_pydantic_only 0, sql_queries 0, sql_constraints 0

## 오류 유형별 사건 검출 (단일 주입)

| 오류 코드 | python_full | python_pydantic_only | sql_queries | sql_constraints |
|---|---|---|---|---|
| ERR-BADREF | 8/8 | 1/8 | 8/8 | 8/8 |
| ERR-BOMCYCLE | 2/2 | 0/2 | 2/2 | 0/2 |
| ERR-BOMVER | 9/9 | 3/9 | 9/9 | 3/9 |
| ERR-DATE | 6/6 | 4/6 | 6/6 | 5/6 |
| ERR-DUPID | 6/6 | 0/6 | 6/6 | 3/6 |
| ERR-ENUM | 2/2 | 2/2 | 2/2 | 2/2 |
| ERR-IDFMT | 1/1 | 1/1 | 1/1 | 1/1 |
| ERR-INVQTY | 4/4 | 2/4 | 4/4 | 4/4 |
| ERR-MISSING | 5/5 | 5/5 | 5/5 | 3/5 |
| ERR-NUMFMT | 7/7 | 6/7 | 7/7 | 6/7 |
| ERR-RESREL | 6/6 | 1/6 | 6/6 | 3/6 |
| ERR-UNIT | 3/3 | 0/3 | 3/3 | 1/3 |

## 생산능력(V13) 계산 대조 — GT plan_evaluation

- python_full: {'rows_compared': 36, 'rows_equal': 36, 'expected_rows_missing_in_output_with_zero_hours': 3, 'excess_rows_expected': 6, 'excess_rows_output': 6}
- sql_queries: {'rows_compared': 36, 'rows_equal': 36, 'expected_rows_missing_in_output_with_zero_hours': 3, 'excess_rows_expected': 6, 'excess_rows_output': 6}

## E02 이관 오류 4건 (E02 파서 출력 레코드 사용)

| 오류 | 기대 규칙 | E02 레코드 | python_full | sql_queries |
|---|---|---|---|---|
| E01-ERR-009 | V07 | True | True | True |
| E01-ERR-010 | B01 | True | True | True |
| E01-ERR-011 | B02 | True | True | True |
| E01-ERR-012 | V02 | True | True | True |

## 보조 관찰: 형식 경계 문자열 (평가셋 밖, 채점 안 함)

| 엔터티.필드 | 값 | python_full | sql_queries | 일치 |
|---|---|---|---|---|
| Material.unit_cost | `'1e3'` | - | S02 | False |
| Material.unit_cost | `' 12'` | - | S02 | False |
| Material.unit_cost | `'12 '` | - | S02 | False |
| Material.unit_cost | `'+5'` | - | S02 | False |
| Material.unit_cost | `'.5'` | - | - | True |
| Material.unit_cost | `'5.'` | - | - | True |
| Material.unit_cost | `'1,000'` | S02 | S02 | True |
| Material.unit_cost | `'１２'` | - | S02 | False |
| Material.unit_cost | `'1_000'` | - | S02 | False |
| Material.unit_cost | `'0x10'` | S02 | S02 | True |
| Material.unit_cost | `'NaN'` | - | S02 | False |
| Material.unit_cost | `'Infinity'` | - | S02 | False |
| Material.unit_cost | `'-0'` | - | - | True |
| Material.unit_cost | `'00012'` | - | - | True |
| Material.unit_cost | `'12.50'` | - | - | True |
| Order.order_date | `'2026-11-1'` | S03 | S03 | True |
| Order.order_date | `'2026-1-15'` | S03 | S03 | True |
| Order.order_date | `' 2026-11-15'` | S03 | S03 | True |
| Order.order_date | `'2026-11-15T00:00'` | - | S03 | False |
| Order.order_date | `'20261115'` | S03 | S03 | True |
| Order.order_date | `'2026-13-01'` | S03 | S03 | True |

## 성능 (자식 프로세스 3회 중앙값)

| 방식 | 배율 | 계층 | 레코드 | 적재 s | 검증 s | 전체 s | 피크 RSS MB | heap MB |
|---|---|---|---|---|---|---|---|---|
| python_full | 1 | all | 353 | 0.0 | 0.00358 | 0.30446 | 34.8 | 0.069 |
| sql_queries | 1 | all | 353 | 0.00181 | 0.00955 | 0.31033 | 36.7 | 0.137 |
| python_pydantic_only | 1 | all | 353 | 0.0 | 0.00208 | 0.30934 | 35.9 | 0.009 |
| sql_constraints | 1 | all | 353 | 0.00225 | 0.00751 | 0.30766 | 36.8 | 0.055 |
| python_full | 10 | all | 3494 | 0.0 | 0.03809 | 0.37056 | 39.9 | 0.589 |
| sql_queries | 10 | all | 3494 | 0.00927 | 0.04927 | 0.37453 | 41.6 | 0.393 |
| python_pydantic_only | 10 | all | 3494 | 0.0 | 0.0163 | 0.31934 | 39.6 | 0.009 |
| sql_constraints | 10 | all | 3494 | 0.00933 | 0.03602 | 0.3491 | 41.1 | 0.34 |
| python_full | 50 | all | 17454 | 0.0 | 0.21135 | 0.65194 | 55.0 | 2.249 |
| sql_queries | 50 | all | 17454 | 0.05132 | 0.33662 | 0.81085 | 58.9 | 1.79 |
| python_pydantic_only | 50 | all | 17454 | 0.0 | 0.08378 | 0.49773 | 53.9 | 0.009 |
| sql_constraints | 50 | all | 17454 | 0.05128 | 0.18172 | 0.64011 | 58.2 | 1.661 |
| python_full | 10 | schema | 3494 | 0.0 | 0.02251 | 0.32742 | 39.8 | 미측정 |
| sql_queries | 10 | schema | 3494 | 0.00948 | 0.02578 | 0.34771 | 41.0 | 미측정 |
| python_full | 10 | schema+referential | 3494 | 0.0 | 0.02016 | 0.32239 | 39.7 | 미측정 |
| sql_queries | 10 | schema+referential | 3494 | 0.00947 | 0.02897 | 0.35988 | 41.0 | 미측정 |
| python_full | 10 | schema+referential+relational | 3494 | 0.0 | 0.03152 | 0.35115 | 39.7 | 미측정 |
| sql_queries | 10 | schema+referential+relational | 3494 | 0.00918 | 0.03785 | 0.36629 | 41.7 | 미측정 |
| python_full | 10 | schema+referential+relational+business | 3494 | 0.0 | 0.0309 | 0.34561 | 40.0 | 미측정 |
| sql_queries | 10 | schema+referential+relational+business | 3494 | 0.00905 | 0.04901 | 0.37107 | 41.3 | 미측정 |

heap(tracemalloc)은 Python 할당만 잡는다. pydantic-core(Rust)·SQLite(C) 내부 할당은 포함되지 않으므로 방식 간 비교 지표로 쓰지 않는다.
