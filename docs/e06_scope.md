# E06 범위 — RDFLib·SHACL 기술 선정 사전 PoC

> 작성 2026-10-21. 상태 **RUNNING** (실험 완료 ≠ 기술 채택). 기준 커밋 `5e9d9e0` + E05 미커밋 작업 트리(보존, 읽기 전용 사용).
> 관련: [e06_comparison_design.md](e06_comparison_design.md)(E05에서 작성한 설계), [e06_rdf_mapping.md](e06_rdf_mapping.md), [e06_shacl_rule_mapping.md](e06_shacl_rule_mapping.md), [e06_rdf_shacl_comparison_report.md](e06_rdf_shacl_comparison_report.md)

## 1. 질문

> 제조 BOM·제품·자재·공급업체 관계와 데이터 정합성 검증에 RDF/SHACL을 도입하면 Python/SQL보다 어떤 이점이 있고, 추가 복잡도와 비용을 정당화할 수 있는가?

결론을 RDF 도입에 유리하게 미리 정하지 않는다. 본개발 시스템·UI·서비스 기능은 만들지 않는다.

## 2. 확인한 기존 상태 (Phase 1)

| 대상 | 확인 결과 |
|---|---|
| Git | HEAD `5e9d9e09aaf7…` (예상과 같음). E05 산출물은 미커밋(수정 2, 미추적 15) — 삭제·덮어쓰기 없이 보존 |
| E01 정답셋 | `ground_truth_v2.json` sha256 `262dbe75…` 일치 |
| E05 평가셋 | `eval_set_v1.json` sha256 `d666c1600267…` 일치(보고값과 같음), 72개, 기대 항목 80, manifest의 데이터셋별 해시로 매번 확인 |
| E05 규칙 | 카탈로그 42개(채점 41 = ERROR 36 + WARNING 5, INFO 1), NOT_MEASURED 6 — 파일에서 다시 셈 |
| E05 결과 | `results/E05_schema_sql/scores.json`: python_full·sql_queries ERROR TP 99/FP 0/FN 0, pydantic_only 31/0/68, sql_constraints 50/114/49 — 읽기 전용으로 비교에 사용 |
| E02 이관 4건 | E05 I-V07·I-B01a·I-B02a·I-V02와 E02 연계 실행으로 확인됨 → E06은 같은 단일 데이터셋으로 비교 |
| Q1~Q5 | `evaluation_protocol.md` §5.2에 정의(초안) → `ontology_competency_questions.md` §2에서 CQ-04·05·06·08·10으로 흡수. 기대 정답은 GT `expected.cq`(E01 `e01_expected.py`가 독립 계산), 매개변수는 `parameters.cq` |
| `intermediate_representation.md` | 문서 파싱 IR — E06 입력 아님 (E05와 같음) |
| 의존성 | rdflib·pyshacl 미설치였음 → 승인 범위대로 rdflib 7.6.0, pyshacl 0.40.1 설치(의존성 7개, 기존 패키지 업그레이드 없음), `requirements.lock` 반영 |

## 3. 비교 대상

| 방식 | 내용 |
|---|---|
| E05 Python (`python_full`) | Pydantic(E01 모델) + 독립 함수 — 기존 결과 재사용, 성능은 같은 세션에서 재측정 |
| E05 SQLite (`sql_queries`) | SQLite 검증 질의 — 위와 같음 |
| **E06 `shacl_pyshacl`** | 엔터티 → RDF(rdflib) → pyshacl로 모든 shape 검증 (SHACL 방식의 본 결과) |
| E06 `shacl_hybrid` | Core shape는 pyshacl, SPARQL 규칙은 같은 질의를 rdflib로 규칙당 1회 직접 실행 — SHACL 엔진 비용과 SPARQL 비용 분리용 |
| E06 `shacl_core_compare` | 두 속성 비교 규칙을 Core `sh:lessThan` 계열로 쓴 변형 — pyshacl 동작 확인용 |
| Q1~Q5 | Python 자료구조 / SQLite / RDFLib SPARQL (+ 속성 경로만 쓴 naive 변형) |

## 4. 동일 조건

- 같은 입력: E05 평가셋 v1을 같은 연산으로 만들고 데이터셋 해시를 확인한 뒤 RDF로 변환.
- 같은 오류 정의·판정 단위·정상/경계 사례: E05 정답(`truth`)과 채점기(`scripts/e05_score.py`)를 그대로 사용. 규칙 ID는 E05 카탈로그.
- 같은 실행 환경: 같은 PC·같은 venv(Python 3.11.9). 성능은 E05 방식도 같은 세션에서 재측정.
- SHACL로 표현하지 않은 규칙은 제외하지 않고 [e06_shacl_rule_mapping.md](e06_shacl_rule_mapping.md)에 분류해 기록한다 (V13 생산능력 = 계산 규칙, shape 없음).
- 검출 출처 구분: RDF 변환 기록 / SHACL Core / SHACL SPARQL / 외부 Python(사용 안 함). 변환 기록은 채점에 넣지 않는다.

## 5. 기존 데이터 재사용

| 재사용 | 방법 | 변경 |
|---|---|---|
| E01 정답셋 v2 | RDF 변환 원본, Q1~Q5 기대 정답(expected.cq) | 없음 |
| E01 모델 | 데이터 타입·필수·열거값·범위 → 어휘와 구조 shape 생성 | 없음 |
| E05 카탈로그·평가셋·정답·채점기 | 그대로 import·읽기 | 없음 |
| E05 검증기 | 성능 재측정, 스키마 변경 실험(임시 복사본에만 패치) | 없음 |

## 6. 범위 밖·미측정

- GraphDB·SPARQL 엔드포인트(E07), OWL 추론, 웹 UI, 운영 연동, HWP/HWPX·OCR, 유료 API.
- 실제 기업 데이터·운영 규모 성능: 미측정.
- 코드 매핑(CQ-20 `mappedTo`)·계보 질의(CQ-19 PROV-O): 매핑 표 데이터가 정답셋에 없어 미측정 (레코드 → 데이터셋 계보만 기록).
- 사람의 규칙 수정 작업시간: 측정하지 않음 (자동 실행시간과 구분).
- 정량 합격선: 팀 합의 필요(D-010) → E06은 RUNNING 유지.
