# 사전 PoC 방향 전환 보고 — ERP 중심 (2026-10-21)

> 결정: DEC-20261021-04. 작업 범위: 문서·설계·설정 초안만. 커밋·푸시, 외부 API 호출, E10·E11 실행, GraphDB·OR-Tools 설치 없음.
> 이 문서의 E00~E11은 **기술 적합성 사전 PoC**이며 충파모 전체 프로젝트 범위가 아니다. **모의 ERP는 실제 기업 ERP가 아니다.**

## 1. 변경 배경과 목표

기존 실험을 폐기하지 않고, 기술 선정용 사전 PoC의 우선순위와 설계를 ERP 중심으로 바꾼다. 다음은 확인되지 않았으므로(D-036) 관련 실험은 합성 데이터와 모의 ERP(SQLite)로만 설계한다: 수요기업 ERP 보유 여부, ERP 실제 스키마, 외부 API·데이터 반입 권한, ERP 자체 생산계획 기능, GPU·CPU·망·보안 환경, 실제 업무 규칙·승인 절차.

## 2. 변경 전·후 기술 구조

| | 구조 |
|---|---|
| 변경 전 | 문서 파싱 → RDF/OWL → GraphDB → 예측·의사결정 |
| 변경 후 | 문서 파싱 → 검색·ERP 필드 매핑 후보 → 정합성 검증 → 담당자 승인 → 모의 ERP DB → 예측·계획 계산 → 대안 비교 |

RDF/SHACL·GraphDB는 불필요하다고 확정하지 않았다. 조건부 검토·보류로 두고 재개 조건을 명시했다 (§6).

## 3. E00~E11 상태 및 우선순위

| ID | 상태 (실제 실행 여부 기준) | 2026-10-21 우선순위 |
|---|---|---|
| E00 | COMPLETED | 완료 유지 |
| E01 | COMPLETED | 완료 유지 |
| E02 | RUNNING (Baseline 완료) | 유지 |
| E03 | RUNNING (v1/v2·외부 평가) | 유지 |
| E04 | NOT_STARTED (예비 1회 + E03 진단 1회만) | **상향** — ERP 입력 품질 관점 |
| E05 | RUNNING (1차 실행 완료, 합격선 미정) | Baseline 확정·마무리 |
| E06 | RUNNING (부분 실행, 성능 미완료) | 최소 SHACL 비교로 제한 |
| E07 | NOT_STARTED · 기술 검토 보류 | 신규 GraphDB 구축 보류 |
| E08 | NOT_STARTED | CPU/API/하이브리드 비교 우선 |
| E09 | NOT_STARTED | E10·E11 포함 |
| E10 | NOT_STARTED (설계만) | 신규 — 모의 ERP 매핑 |
| E11 | NOT_STARTED (계약만) | 신규 — ERP 기반 의사결정 |

어떤 실험도 이번 작업으로 COMPLETED가 되지 않았다. 의존성: E01 → E02·E03·E05 → E10 → E11, E03·E04 → 문서 파서 선정, E05 → E06 → E07 재개 여부, E04·E08·E10·E11 → E09 ([experiment_plan.md](experiment_plan.md) §0.2).

## 4. 실제 수정한 파일

| 구분 | 파일 |
|---|---|
| 수정 | `docs/experiment_plan.md` (개정 이력, §0.1.1, 상태 표, 의존성, E04·E06·E07·E08·E09 개정 문단, E10·E11 절), `docs/decisions.md` (§3 상태 갱신·행 추가, §3.1, D-031 이행 기록 추가, D-032~D-037, DEC-20261021-03·04), `docs/e06_scope.md` (미작성 보고서 링크를 미작성 표시로) |
| 신규 | `docs/e10_erp_mapping_plan.md`, `docs/e10_data_contract.md`, `docs/e10_evaluation_protocol.md`, `schemas/e10_mock_erp.sql`, `configs/e10_mapping_rules.json`, `docs/e11_decision_interface.md`, `docs/e11_constraint_policy.md`, `schemas/e11_scenario_contract.json`, 이 문서 |
| 변경 없음 | 정답셋·평가셋·모든 결과 폴더·파서·E05/E06 코드 (§10) |

기존 D-001~D-031과 DEC 기록 본문은 지우거나 바꾸지 않았다(D-031에 이행 결과만 덧붙임). 새 ID: D-032~D-037, DEC-20261021-03·04 (기존 마지막 ID D-031·DEC-20261021-02 확인 후 발급).

## 5. E05 공개 준비 상태

결과 파일에서 다시 확인한 값 (보고값과 일치): 규칙 42(NOT_MEASURED 6), 평가셋 72(기대 항목 80, sha256 `d666c1600267…`), python_full TP 99/FP 0/FN 0, sql_queries 99/0/0, pydantic_only 31/0/68, sql_constraints 50/114/49, E02 이관 4/4. 결함 기록(Pydantic lax 모드, SQLite FK 기본 off, 날짜 정규화, 연쇄 거부, 복합 오류 가림, 정답 정의 범위 오탐 1건)은 [e05_data_validation_report.md](e05_data_validation_report.md)에 그대로 있다. 정답·결과는 바꾸지 않았다.

**E05 커밋은 승인되지 않아 하지 않았다 (D-032).** 제안 커밋 대상:

```
configs/e05_validation_rules.json
data/canonical/e05/eval_set_v1.json  data/canonical/e05/manifest_v1.json  data/canonical/e05/verification_v1.json
docs/e05_validation_scope.md  docs/e05_rule_catalog.md  docs/e05_injection_protocol.md  docs/e05_data_validation_report.md  docs/e06_comparison_design.md
results/E05_schema_sql/ (complexity.json failures.md git_safety_report.md leak_scan_report.md metrics.csv perf.csv queries.sql reports.json run_meta.json scores.json summary.md)
scripts/e05_dataset.py  scripts/e05_build_eval_set.py  scripts/e05_validate_python.py  scripts/e05_validate_sql.py  scripts/e05_score.py  scripts/e05_run.py
tests/test_e05_validation.py
```

권장 메시지: `feat: add E05 data consistency and business rule validation baseline (Python/Pydantic, SQLite)`

주의: `docs/experiment_plan.md`·`docs/decisions.md`에는 E05·E06·ERP 전환 내용이 함께 들어 있고, `requirements.lock`에는 E06 패키지(rdflib·pyshacl)가 들어 있다. 파일 단위로만 스테이징하므로(부분 스테이징 금지 규칙) 이 세 파일은 E05 커밋에서 빼고 전환 문서 커밋에 넣는 것을 제안한다. 이 경우 E05 커밋 시점의 저장소에는 E05 상태 문단이 없다.

로컬 전용(커밋 제외 유지): `data/raw/`, 외부 문서 원본·텍스트 포함 정답·출력(D-025), `configs/sensitive_terms.local.txt`, 세션 임시 파일.

## 6. E06 현재 상태와 보류 조건

- 상태 **RUNNING** — 부분 실행. 측정 완료: E05 정답셋 정확도(pyshacl ERROR TP 99/FP 0/FN 0, E05 Python·SQL과 데이터셋별 차이 0), Q1~Q5 46/46(Python·SQLite·SPARQL), 규칙·스키마 변경 시나리오 5개. 미완료: S/M/L 성능(사용자 지시로 중단 — 중단 전 실행의 SHACL 메모리 값은 측정 버그로 무효), 종합 보고서. 코드·결과는 보존했고 재실행하지 않았다 (D-033).
- **최소 비교로 제한**: 오류 검출 차이, 관계 표현력, BOM 순환 검증, 규칙 변경 영향, RDF 변환 시간, 구현·운영 복잡도.
- **E06 확장 조건**: 여러 ERP 간 같은 개념의 의미 충돌 / SQL·공통 스키마로 유지하기 어려운 관계 / SHACL의 명확한 검증상 이점 / 규칙 변경 운영 비용 절감 — 실측으로 확인될 때만.
- **E07 재개 조건**: RDFLib가 관계 조회 규모·속도를 못 맞춤 / 전용 그래프 저장소의 관리·질의 기능 필요 / 다중 시스템 의미 통합을 지속 수행 / 관계형 DB 대비 확실한 정량 이점 — 하나라도 확인될 때 재검토. SPARQL이 가능하다는 이유만으로 구축하지 않는다.

## 7. E10 모의 ERP 설계

[e10_erp_mapping_plan.md](e10_erp_mapping_plan.md). E01 정답셋 v2의 11개 엔터티를 모의 ERP 테이블(ProductMaster·MaterialMaster·SupplierMaster·SupplierItem·UnitMaster·BOMHeader·BOMLine·SalesOrder·Inventory·ProductionCapacity·Routing)로 대응시켰다. 승인 대기 구조 5개(ImportBatch·MappingCandidate·ValidationIssue·StagingRecord·ApprovalLog). DDL 초안([schemas/e10_mock_erp.sql](../schemas/e10_mock_erp.sql))은 승인 기록 없는 본 테이블 쓰기와 검증 오류가 남은 승인을 트리거로 막는다 — 빈 메모리 DB에서 문법만 확인했고 데이터는 적재하지 않았다. 시나리오 12개(M01~M12)와 독립 정답·지표는 [e10_evaluation_protocol.md](e10_evaluation_protocol.md), 계약은 [e10_data_contract.md](e10_data_contract.md). 확인된 제약: E01의 생산능력은 **시간 단위**라서 제품 수량 기준 능력은 E01에 없다.

## 8. E11 계획 비교 인터페이스

[e11_decision_interface.md](e11_decision_interface.md), [e11_constraint_policy.md](e11_constraint_policy.md), [schemas/e11_scenario_contract.json](../schemas/e11_scenario_contract.json). 계약 7개(PlanningInput·ForecastResult·HardConstraint·ScenarioConfig·PlanCandidate·ConstraintViolation·ScenarioEvaluation). 판정 FEASIBLE / INFEASIBLE / **UNVERIFIED**(판정에 필요한 사실 미확인 — 자동 실행 가능 판정 금지). 비교 계획은 E01의 PLAN-REG·PLAN-OT·PLAN-OUT 3개로 제한. 필수 시나리오 T-01 독립 정답: 생산 900개, 자재 1,800 kg, 부족 300 kg, 능력 초과 100개 → 정규 생산만 INFEASIBLE, 외주·잔업 추가 UNVERIFIED, 순위 없음.

## 9. 재사용 코드와 데이터

| 재사용 | 대상 실험 |
|---|---|
| E01 정답셋 v2·expected(plan_evaluation, cq) | E10 기준 데이터, E11 Baseline 정답 |
| E01 모델(`scripts/e01_models.py`) | E10 DDL 필드·타입 |
| E02 업체 헤더·코드 대응표(`configs/e02_vendor_mapping.json`) | E10 규칙 기반 매핑 |
| 공통 IR 0.2 | E10 MappingInput (IR 변경 없음) |
| E05 규칙·검증기·채점 구분 | E10 값 검증, E11 HC-DATA |
| decision_logic §1~§6 | E11 제약 판정·T-01 |
| E05·E06 실측 결함(lax 숫자·날짜, FK off, 날짜 정규화) | E10 규칙 M-11·M-13, DDL 주석 |

## 10. 기존 결과 불변 검증

작업 시작 시 정답셋·결과(Git 제외 파일 포함)·온톨로지·설정·코드·테스트·문서·`requirements.lock` 440개 파일의 sha256을 세션 임시 폴더에 기록하고, 작업 종료 시 다시 비교했다 (종료 시 447개).

| 대상 | 결과 |
|---|---|
| `data/canonical/**`(정답셋 v2 `262dbe75…`, E05 평가셋 `d666c160…` 등) | 변경 0, 삭제 0 |
| `results/**`(E00~E06, E03 v1/v2·외부 결과, Upstage 응답 포함) | 변경 0, 삭제 0 |
| `ontology/*`, `scripts/*.py`, `tests/*.py`, `src/**`, `requirements.lock` | 변경 0 |
| `configs/*` | 기존 변경 0, 신규 1 (`e10_mapping_rules.json`) |
| `docs/*.md` | 의도한 수정 3 (experiment_plan·decisions·e06_scope), 신규 6 |
| `schemas/*` (새 폴더) | 신규 2 (`e10_mock_erp.sql`, `e11_scenario_contract.json`) |
| 문서 내부 링크 (`docs/*.md`) | 깨진 링크 0 |

## 11. 전체 테스트 결과

`pytest` 281 passed (E00~E05 207 + E06 74), 경고 33건(rdflib 내부 DeprecationWarning). 신규 기술 실험은 실행하지 않았다. 신규 JSON 2개 파싱·`$ref` 확인, DDL 문법 확인(빈 메모리 DB), 문서 내부 링크 확인.

## 12. Git 안전 검사

`scripts/git_safety_check.py`·`scripts/e03_external_leak_scan.py`를 실행하고 보고서는 세션 임시 폴더에 저장했다(기존 결과 파일을 덮어쓰지 않기 위해). 결과는 최종 보고(대화)에 적는다. 스테이징 0, 커밋·푸시 없음.

## 13. 추가 승인 필요 항목

| ID | 내용 |
|---|---|
| D-032 | E05 커밋·공개 (§5 목록) |
| D-033 | E06 잔여 측정·보고서 |
| D-034 | E10 착수(적재·평가), 임베딩·LLM 외부 API 사용 여부 |
| D-035 | E11 계약 확정, OR-Tools 설치 |
| D-036 | 수요기업 ERP·환경 확인 |
| D-037 | 공개 문서의 담당자 역할명 표기 확인 |
| D-028·D-029·D-030 | E05 완료 조건, Pydantic strict 모드, 합성 가정 규칙 확인 (기존) |
| D-010 | 정량 목표값 (Wrong-value Commit Rate 허용 상한 포함) |

## 14. 다음 단계 실행 순서 (제안)

1. E05 커밋 승인 여부 결정(D-032) → 공개
2. E06 처리 결정(D-033): 성능 재측정 범위 축소(S·M만) 또는 현 상태로 보고서 작성
3. E10 1단계: 모의 ERP DDL 적재 + 규칙 기반 매핑 Baseline + 시나리오 M01~M12 정답 파일 (D-034)
4. E04 본 실험 범위를 ERP 필수 필드 기준으로 확정(D-021)
5. E11 계약 담당 간 합의(D-035) → T-01·E01 Baseline 판정 모듈
6. E08 실행 환경 비교표 작성 → E09 종합
