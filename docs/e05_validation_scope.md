# E05 검증 범위 — 데이터 정합성 및 업무 규칙 검증 PoC

> 작성 2026-10-21. 기준 커밋 `5e9d9e0`. 상태 **RUNNING** (실험 완료 ≠ 기술 채택).
> 관련: [experiment_plan.md](experiment_plan.md) E05, [e05_rule_catalog.md](e05_rule_catalog.md), [e05_injection_protocol.md](e05_injection_protocol.md), [e05_data_validation_report.md](e05_data_validation_report.md)

## 1. 목적

본개발 기술 선정을 위한 사전 PoC다. 데이터 검증 시스템을 만드는 것이 아니라 다음을 실측으로 확인한다.

1. 제조 운영 데이터의 구조적·업무적 오류를 어떤 방식으로 검출할 수 있는가
2. Python/Pydantic/SQL(SQLite)만으로 어느 수준까지 검증할 수 있는가
3. 규칙의 구현 복잡도와 실행 비용
4. RDF/SHACL·GraphDB가 추가 가치를 줄 가능성이 있는 문제 (E06·E07 비교 기준)
5. 실제 기업 환경 적용 전에 추가로 확인해야 할 조건

## 2. 확인한 기존 산출물 (Phase 1)

| 대상 | 확인 결과 | E05에서의 사용 |
|---|---|---|
| `CLAUDE.md`, `docs/experiment_plan.md` E05 절 | 가설: Pydantic + SQL 제약으로 주입 오류 대부분 탐지, SQLite FK 기본 비활성·첫 오류에서 중단·재귀 CTE 필요를 예상 실패로 기록 | 가설을 그대로 검증 대상으로 둠 |
| `docs/decisions.md` | E05 관련 미결 결정 없음. D-010(정량 목표값) 대기 | 목표값은 `팀 합의 필요`로 둠 |
| `docs/manufacturing_data_schema.md` §3·§5 | 14개 엔터티 필드 정의, 품질 규칙 QR-01~QR-08, QR-06① 판정식(종료일 포함·수량 상한 미포함·site null) | 규칙 카탈로그의 ERROR 근거 |
| `docs/evaluation_protocol.md` §2.4·§4.1 | 오류 코드 체계, 정확·부분·미탐·오탐·파생 판정 | 채점 기준 (§4) |
| `docs/decision_logic.md` §4·§6.1 | 생산능력 계산(자원·주별 필요시간, 가용 = 정규×5, 잔업안 +잔업×5) | V13 계산 |
| `docs/intermediate_representation.md` | 문서 파싱용 공통 IR 0.1/0.2 | E05 입력 아님 (E05는 정규화된 엔터티 레코드 대상). 결과 필드명은 IR의 위치·근거(evidence) 관례를 따름 |
| `data/canonical/ground_truth_v2.json` (sha256 `262dbe75…`) | 14개 엔터티 353 레코드, `parameters.reference_date` 2026-11-15, `site_id` null, `expected.plan_evaluation` | 정상 데이터·오류 주입 기준 (변경 없음) |
| `scripts/e01_models.py` | Pydantic 모델 (필드 제약 + model_validator) | 수정 없이 재사용 |
| `data/canonical/injected_errors_v1.json` | 주입 오류 13건 | E02 이관 4건 정의·출처 확인 |
| `results/E02_tabular_parsing/` | 13건 중 9건 파서 범위 탐지(9/9), 4건(E01-ERR-009~012) 업무 규칙 오류로 E05 이관 | §5 책임 경계, 이관 4건 연계 실행 |
| E03 문서 파싱 결과 | 문서 → IR 결과(외부 문서 텍스트 포함분은 비공개, D-025) | E05 입력으로 쓰지 않음 (§4 제외 범위) |
| 기존 테스트 | E00~E03 테스트 존재 | 불변 확인 대상 (Phase 9) |

기존 ID·필드명·타입·단위·BOM 버전·주문·재고 정의는 바꾸지 않았다.

## 3. 입력 데이터

1. **정상 데이터**: E01 정답셋 v2 엔터티 그대로 (합성 데이터 + UCI 공개 데이터 배분분. 실제 기업 데이터 없음).
2. **오류 평가셋 v1**: 정상 데이터에 변경 연산(set·add·remove)을 적용한 72개 데이터셋 — 정상 1, 단일 오류 59, 경계 통과 9, 복합 3 ([e05_injection_protocol.md](e05_injection_protocol.md)).
3. **E02 연계**: E02 파서 출력(`results/E02_tabular_parsing/output/invalid_vendor_{a,b}.json`)에서 이관 4건의 레코드를 찾아 정상 데이터에 넣고 검출 여부를 확인. 파싱 오류와 검증 성능을 분리하기 위해 업체 출력 전체를 변환하지 않았다 (CSV·XLSX 두 경로 레코드가 겹쳐 중복이 생기므로).
4. **규모 확장(성능용)**: 정상 데이터를 ×10, ×50 복제(업무 ID에 접미사, record_uid 재생성, Unit 공유). 관계·제약은 복제본 안에서 유지되며 ×50 정상 데이터에서도 ERROR·WARNING 0건을 확인했다.

## 4. 검증 범위와 제외 범위

| 범위 | 포함 | 제외 (사유) |
|---|---|---|
| 구조 | 필수값·타입·날짜·enum·record_uid 형식·숫자 범위·업무 키 중복·빈 문자열 | 업무 ID 형식(문서 정의 없음 → NOT_MEASURED) |
| 참조 | 제품·자재·공급사·BOM·자원·계획·단위 참조, 외부 코드 미매핑, 마스터 삭제로 생긴 고아 | — |
| BOM·관계 | 순환, 버전 유효조건 중복, 미승인 활성, 버전 표기 중복, 유효조건 오류, 계획 라인 BOM 선택 불가·모호, 구성품 유형 불일치, 단위 차원 불일치, 우선 공급사 개수, 배분 비율 합 | 라인 없는 BOM·같은 구성품 중복은 문서 근거 없음 → 합성 가정 WARNING |
| 업무 | 재고 수량 규칙, 납기<주문일, 공정·자원 관계, 외주·자체 생산 자원 규칙, 생산능력 계산 | 주문 수량 허용 범위·납기 실현성·자재 부족·공급 계약 (정의 없음 또는 계산 결과 → NOT_MEASURED) |
| 방식 | Python(Pydantic 재사용 + 독립 함수), SQLite 검증 질의, SQLite 제약 적재 | RDF/SHACL 구현(E06), GraphDB(E07), 웹 UI·플랫폼·운영 DB |
| 데이터 | 합성·공개 데이터 | 실제 기업 데이터, 문서 파싱 결과(E03), HWP/HWPX |

실험 계획의 다른 지표 중 **관계 조회 정답률(Q1~Q5)** 과 **스키마 변경 시나리오(schema_change_diff.md)** 는 이번 작업 단계에 없어서 실행하지 않았다 → `미측정`.

## 5. 기존 E02와 책임 경계

| 단계 | 책임 | 오류 |
|---|---|---|
| E02 (파서) | 파일 구조를 읽어 정규 필드로 옮기기, 값 정규화(날짜·숫자), 형식 오류 보고 | E01-ERR-001~008, 013 (9건) — 헤더 어긋남(ERR-TABLE)·ID·버전 표기(ERR-IDVER)처럼 파일 구조에 묶인 오류 포함 |
| E05 (검증) | 정규화된 레코드 사이의 정합성·업무 규칙 | 이관 4건: ERR-009 납기<주문일(V07), ERR-010 BOM 순환(B01), ERR-011 BOM 버전 중복(B02), ERR-012 할당>보유(V02) |

경계 원칙: 한 레코드 안에서 파일 형식만 보고 판단할 수 있으면 E02, 다른 레코드·엔터티·기준값이 필요하면 E05. E05는 파서 범위 오류(누락·형식·참조 등)도 정규화 후 단계에서 다시 잡을 수 있지만, 이는 이중 방어이며 E02 결과를 대체하지 않는다.

## 6. 평가 기준

- 채점: 독립 정답(평가셋 생성기가 정함) 대비 규칙 단위 TP·FP·FN·TN(근사), Precision·Recall·F1, 사건 단위 검출률, 규칙 커버리지, 오류 코드별 사건 검출률. 판정은 evaluation_protocol §4.1을 따른다 (정확·파생·허용·부분·오탐·미탐).
- ERROR(근거 있는 규칙)와 WARNING(합성 가정)은 따로 집계, INFO(V13 생산능력)는 GT `expected.plan_evaluation`과 값 대조.
- 성능: 같은 PC·같은 venv에서 S(×1)/M(×10)/L(×50), 계층별 규칙 수 증가, 자식 프로세스 3회 중앙값.
- 정량 합격선은 정하지 않았다 (`팀 합의 필요`, D-010). 따라서 E05는 수치가 높아도 COMPLETED로 표기하지 않는다.

## 7. E06·E07과 비교할 항목

같은 평가셋 v1과 정답, 같은 결과 필드(dataset_id, rule_id, entity_id, field_path, severity, detected, actual_value, expected_constraint, explanation, evidence)로 비교한다. 세부는 [e06_comparison_design.md](e06_comparison_design.md).

- 규칙별 검출 정확도 (특히 SPARQL 적합 규칙: 순환, 버전 중복, BOM 선택, 우선 공급사, 배분 합)
- 규칙 표현의 명확성·수정 범위 (규칙 1개 추가·변경 시 고치는 파일·줄)
- 다단계 관계 조회 (재귀 CTE vs 그래프 경로)
- 변환 비용 (JSON → RDF 적재 시간·메모리)
- 오류 보고의 추적성 (레코드·필드 특정 여부)
