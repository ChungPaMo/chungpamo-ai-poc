# E09 사전 PoC 최종 기술 선정 보고 (2026-10-22)

> 사전 기술 선정 PoC의 종합 판단이다. **운영 기술을 확정하지 않는다** — 수요기업 ERP·환경이 확인되지 않았고(D-036), 정량 합격선이 합의되지 않았다(D-010).
> 모든 수치는 합성 데이터(E01 정답셋 v2와 그 파생 평가셋) 또는 공개 외부 문서에서 얻었다. 같은 작성자가 정답과 구현을 만든 실험의 100%는 구현 일치도이며 일반화 성능이 아니다.
> 근거 등급: **M** = 실제 측정 완료 · **S** = 합성 데이터에서만 확인 · **D** = 설계·계약만 준비 · **N** = 미측정 · **E** = 실제 기업 환경 확인 필요

## 1. 실험 상태 (실행 상태와 채택 판단은 별개)

| ID | 실험 | 실행 상태 | 핵심 결과 | 보고서 |
|---|---|---|---|---|
| E00 | 개발환경·재현성 | COMPLETED | Python 3.11.9 venv, 새 클론 재현 | experiment_plan |
| E01 | 합성 데이터·정답셋 | COMPLETED | 정답셋 v2 (14 엔터티, 353 레코드) | results/E01_dataset |
| E02 | CSV/Excel 직접 파싱 | RUNNING (Baseline 완료) | 파서 범위 오류 9/9, 업무 규칙 4건 → E05에서 4/4 검출 | results/E02_tabular_parsing |
| E03 | DOCX/PDF/PPTX 직접 파서 | RUNNING | holdout PDF(공식 정답) v2: 표 6/6, 셀 625/676, 병합 23/30. DOCX·PPTX는 잠정 정답, HWP/HWPX 미측정 | e03_external_generalization_report |
| E04 | 직접 파서 vs Upstage | NOT_STARTED (기존 2회 호출로 잠정 비교) | 텍스트형 PDF 2건: 셀 정확도 동일, 병합 1건 API 우세, API 셀 좌표 없음 | e04_direct_vs_upstage_report |
| E05 | Python/Pydantic/SQLite 검증 | RUNNING (커밋 `3d9974b`) | 41 규칙, Python·SQL 99/0/0, Pydantic 단독 31/0/68, 제약 적재 50/114/49 | e05_data_validation_report |
| E06 | RDFLib/SHACL | RUNNING (측정 완료) | 99/0/0 (E05와 차이 0), L 검증 70분·0.7 GB | e06_rdf_shacl_comparison_report |
| E07 | GraphDB | NOT_STARTED · 기술 검토 보류 | 재개 조건 미충족 | experiment_plan E07 |
| E08 | CPU/API/하이브리드 | RUNNING (기존 실측 인용 비교) | CPU 로컬로 실측 기능 전부 1초 이내 | e08_deployment_architecture_report |
| E09 | 기술 선정 | RUNNING (이 문서) | — | — |
| E10 | 모의 ERP 매핑 | RUNNING | v1 잘못된 반영 1/7(M13) → v2 0건, 안전성 13/13 | e10_erp_mapping_report, e10_m13_fix_report |
| E11 | 의사결정 계약 | RUNNING (계약 검증만) | 판정 11/11, E01 계획안 3개 모두 INFEASIBLE | e11_contract_verification_report |

어떤 실험도 정량 합격선 없이 COMPLETED로 바꾸지 않았다 (E00·E01은 기존 승인으로 COMPLETED).

## 2. 기술 선정표

| 영역 | 기술 | 판정 | 근거 | 등급 | 조건·대체안 |
|---|---|---|---|---|---|
| 정형 입력 | 표준 csv + openpyxl | **조건부 채택** | E02 파서 범위 오류 9/9, 업체 A·B 형식, 묶음 0.04~0.05 s | M·S | 실제 업체 파일 형식 확인(E). pandas 비교 보류(D-016) |
| 문서 입력 | pdfplumber v2 (텍스트형 PDF) | **조건부 채택** | holdout 공식 정답 셀 625/676, 표 6/6. 약한 문서 존재(X-HO-P01 2/53) | M | 사람 검토 전제, 셀 좌표로 원본 추적 가능 |
| 문서 입력 | pypdf | **제외** (표 용도) | 표 구조 0 (텍스트는 보존) | M | 텍스트 전용 보조로만 |
| 문서 입력 | python-docx·python-pptx | **조건부 채택** | 합성 샘플 일치, 외부 문서는 잠정 정답 기준 | S (외부는 미검수) | 사람 검수(D-026) 후 확정 |
| 문서 입력 | HWP·HWPX 파서 | **보류** | 미측정 | N | 사용자 측 PDF/DOCX 변환(대체안), 검수자 지정(D-017) |
| 문서 입력 | OCR (스캔 PDF) | **보류** | 미측정 (우선순위 제외) | N | 스캔 문서 비중 확인(E) |
| 문서 입력 | Upstage Document Parse | **보류** (조건부 검토 후보) | 텍스트형 2건에서 정확도 이익 없음, 병합 1건 우세, 1건 8~10 s·쪽당 과금, 셀 좌표 없음 | M (2건) | 스캔·복잡 표 본 실험(D-021), 외부 전송 승인(E) |
| 검증 | Python + E01 Pydantic 모델 + 규칙 함수 | **조건부 채택** | 99/0/0, L 0.20 s | M·S | Pydantic strict/유한값 검사 추가(D-029) |
| 검증 | Pydantic 단독 | **제외** | 재현율 0.313, model_validator 가림 | M | — |
| 검증 | SQLite 검증 질의 | **조건부 채택** | 99/0/0, L 0.31 s, 재귀 CTE BOM | M·S | FK pragma·date 왕복 관리, 운영 DB 확정 후 재검증(E) |
| 검증 | SQLite 제약 적재 단독 | **제외** (검증 보고 수단) | 50/114/49, 연쇄 거부 | M | 적재 안전장치로는 E10에서 사용 |
| 검증·관계 | RDF + SHACL (pyshacl) | **보류** | 추가 검출 0, 변경 비용 동일, L 70분·0.7 GB, 엔진 중단 위험 | M·S | 다기업 의미 충돌·SQL로 유지 곤란한 관계가 실측될 때 재검토 |
| 관계 조회 | RDFLib SPARQL | **보류** | Q1~Q5 46/46 동일, SQL 재귀 CTE로 충분 | M·S | — |
| 저장 | GraphDB (E07) | **보류** | 재개 조건 미충족 | N | — |
| 추론 | OWL·범용 온톨로지 | **보류** | 필요성 미확인 | N | SHACL·SQL 규칙 |
| ERP 연계 | SQLite 모의 ERP + staging·승인 계층 | **조건부 채택** (검증 환경으로) | 승인 없는 반영 0, 중복 승인·롤백·재반입 13/13, v2 잘못된 반영 0 | M·S | 실제 ERP 아님 — ERP 확인 후 대상 교체(E) |
| ERP 연계 | 애플리케이션 검증 + DB 제약 이중 장치 | **채택** (설계 원칙) | 한쪽만으로 뚫린 경로가 실제로 있었음(D-2) | M | — |
| ERP 연계 | 규칙 기반 매핑 v2 (충돌 탐지) | **조건부 채택** | 필드 56/56, 충돌 M13·C01 차단, 오탐 0(C02·C03) | S | 교차 필드 규칙 확장, 실제 업체 문서 시험(E) |
| ERP 연계 | 자동 승인 | **보류** (기본값 REVIEW_REQUIRED) | v1 자동 승인에서 잘못된 반영 발생 | M·S | 허용 필드·조건 팀 합의 |
| ERP 연계 | BM25·임베딩·Tri-CHEF·LLM 후보 | **보류** (미측정) | 계약만 (`e10_candidate_provider_contract.json`) | D | 검색·에이전트 담당 결과를 같은 평가셋으로 |
| ERP 연계 | 외부 ERP 공식 API | **보류** | ERP 미확인 | N·E | 파일 반입 + staging |
| ERP 연계 | 실기업 ERP 직접 쓰기 / 전사 ERP 구현 | **제외** (사전 PoC·MVP 범위) | — | — | staging + 승인 후 반영 |
| 의사결정 | Hard Constraint 공통 판정 (FEASIBLE/INFEASIBLE/UNVERIFIED) | **조건부 채택** (계약) | 11/11, 미확인 조건 자동 FEASIBLE 0 | S·D | 필수 납기·업무 제약 정의(도메인·KPI 담당) |
| 의사결정 | 예측모델·계획 생성·OR-Tools | **보류** (미측정) | 예측·최적화 담당 범위, E01 계획안 모두 INFEASIBLE | N | 실행 가능 계획이 나오는 시나리오 합의 |
| 배치 | CPU 로컬 | **조건부 채택** (기본안) | 실측 기능 전부 GPU 없이 1초 이내 | M | 기업 서버 사양 확인(E) |
| 배치 | 하이브리드 (로컬 + 선택적 API) | **보류** (조건부 후보) | API 이점 미입증 | M (2건) | 스캔·복잡 표 실측 + 외부 전송 승인 |
| 배치 | 전체 외부 API | **제외** (현 근거) | 정확도 이익 없음, 비용·보안·장애 의존 | M (2건) | — |

## 3. 제안 아키텍처 (ERP·경량 DB 중심, 조건부)

```
업체 CSV/XLSX ─► 표준 csv/openpyxl ─┐
텍스트형 PDF ─► pdfplumber v2 ─────┼─► 공통 IR 0.2 ─► 매핑 후보(규칙 v2; 검색·LLM은 계약만) ─► 값 검증(E05 규칙, Python)
DOCX/PPTX ─► python-docx/pptx ─────┘                                                   │
(스캔·복잡 표 ─► Upstage: 승인 시에만, 결과도 staging으로)                                ▼
                                       StagingRecord ─► 담당자 승인(자동 승인 기본 OFF) ─► 모의 ERP(SQLite, 트리거·FK)
                                                                                         │ 변경 이력·원본 위치
                                                                                         ▼
                                PlanningInput ─► (예측·계획 생성: 담당 미구현) ─► Hard Constraint 판정 ─► FEASIBLE끼리 비교
```

- 이 그림의 각 상자는 실측 또는 계약 수준이 다르다 (§2 등급). 문서 파서 → IR → E10 매핑의 **자동 연결은 미구현·미측정**.
- RDF/SHACL·GraphDB는 운영 경로에 넣지 않는다. 불필요하다고 확정하지 않았으며, 다기업 의미 통합 요구가 실측되면 E06 확장·E07 재개 조건으로 재검토한다.
- 실제 ERP가 있으면 모의 ERP 자리는 그 ERP의 반입 방식(파일·공식 API)으로 바뀌고, staging·승인 계층은 앞단에 남는다 (기업 확인 필요).

## 4. E02·E03 종료 범위와 남은 위험

| 항목 | 상태 |
|---|---|
| E02 CSV/XLSX | Baseline 결과 보존, 업무 규칙 4건은 E05에서 4/4 검출(E02 파서 출력 레코드 사용). pandas 비교 보류 |
| E03 PDF (공식 정답) | v2 holdout 결과 보존. 셀 51개·병합 7개 미일치, 선 없는 표·다른 생성 도구 문서는 표본이 작음 |
| E03 DOCX·PPTX | 잠정 정답(PROVISIONAL) — 사람 검수 미수행(D-026). 검증된 정확도로 쓰지 않는다 |
| E03 합성 PDF P-01·P-02 | 폰트 재배포 조건 미확인으로 로컬 전용(D-020) |
| HWP·HWPX | 미측정 (도구·검수자 없음 D-006·D-017) — 조건부 후보 |
| OCR·스캔 PDF | 미측정 — Upstage 비교의 핵심 공백 |
| 위험 | 합성 문서는 같은 라이브러리 계열 왕복 가능성(D-022). 실제 업체 문서 형식 미확인 |

## 5. E06 종료 판단

실행 상태 RUNNING(측정 완료), 기술 판단 **보류**. 근거: Python/SQL 대비 추가 검출 0건, 규칙 변경 수정 범위 동일, L 규모 검증 4,189 s(Python 0.20 s), 메모리 727 MB, 구현 602줄 + 의존성 9개, Core 비교 제약의 엔진 중단, rdflib 리터럴 관대함. 평가 단위 결함: Q3·Q4가 주문 단위가 아니라 계획 기간 기준(CQ-06·08)으로 측정됨(review_issues I-02). E07은 새로운 정량 필요성이 없어 보류 유지.

## 6. 미해결 항목

[poc_open_issues_and_enterprise_questions.md](poc_open_issues_and_enterprise_questions.md)
