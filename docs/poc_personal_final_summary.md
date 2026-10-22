# 사전 기술검증 PoC 개인 최종 요약 — 파서·데이터 통합 담당 (2026-10-22)

> 기존 보고서의 요약이다. 수치는 `scripts/poc_consistency_check.py`로 원본 결과 파일과 대조했다(57개 항목, 불일치 0, `results/poc_final/consistency_check.json`).
> **모든 결과는 합성 데이터(E01 정답셋 v2 파생) 또는 공개 외부 문서에서 얻었다. 실제 기업 적용 성능이 아니다.** 정답과 구현을 같은 작성자가 만든 실험의 100%는 구현 일치도다.
> 실행 상태와 기술 판단은 별개다. 정량 합격선이 합의되지 않아(D-010) E00·E01 외에는 COMPLETED가 아니다. 종합 판단: [e09_final_technology_selection.md](e09_final_technology_selection.md), 미해결·기업 질문: [poc_open_issues_and_enterprise_questions.md](poc_open_issues_and_enterprise_questions.md).

## 한눈에 보기

| ID | 실험 | 실행 상태 | 기술 판단 | 핵심 수치 |
|---|---|---|---|---|
| E00 | 개발환경 | COMPLETED | — | Python 3.11.9 venv, 새 클론 재현 |
| E01 | 합성 데이터·정답셋 | COMPLETED | — | 14 엔터티·353 레코드, 독립 검증 143/143 |
| E02 | CSV/Excel 파싱 | RUNNING | csv·openpyxl 조건부 채택 | 파서 범위 오류 9/9, 업무 오류 4건 → E05에서 4/4 |
| E03 | 문서 직접 파서 | RUNNING | pdfplumber v2·python-docx/pptx 조건부 채택, pypdf(표) 제외 | holdout 공식 정답 셀 625/676 |
| E04 | 직접 파서 vs Upstage | NOT_STARTED (기존 2회로 잠정 비교) | Upstage 보류 | 텍스트형 2건 셀 동일, 병합 4/6 vs 2/6 |
| E05 | Python/SQLite 검증 | RUNNING (공개 `3d9974b`) | Python·SQLite 검증 조건부 채택, Pydantic 단독·제약 적재 단독 제외 | 99/0/0 |
| E06 | RDF/SHACL | RUNNING | 보류 | 99/0/0(추가 검출 0), L 검증 4,189 s·727 MB |
| E07 | GraphDB | NOT_STARTED · 검토 보류 | 보류 | — |
| E08 | CPU/API/하이브리드 | RUNNING | CPU 로컬 기본안(조건부) | 실측 기능 전부 GPU 없이 1초 이내 |
| E09 | 기술 선정 | RUNNING | 보고서 작성 | — |
| E10 | 모의 ERP 매핑 | RUNNING | 모의 ERP + 승인 계층·규칙 매핑 v2 조건부 채택, 자동 승인 보류 | 잘못된 반영 v1 1/7 → v2 0 |
| E11 | 의사결정 계약 | RUNNING | 판정 규칙 조건부 채택, 예측·최적화 미구현 | 계약 검증 11/11 |

## E02 CSV/Excel 직접 파싱

| 질문 | 답 |
|---|---|
| 왜 | MVP의 기본 입력 경로(업체 CSV·XLSX)가 표준 라이브러리로 충분한지 |
| 무엇·데이터 | E01에서 만든 업체 A(CSV)·B(XLSX, CP949·천 단위·한글 단위) 정상/오류 주입본 |
| 도구·비교군 | 표준 csv + openpyxl (Baseline). pandas 비교는 보류(D-016) |
| 정량 결과 | 주입 오류 13건 중 파서 범위 9/9 검출, 업무 규칙 4건은 E05로 이관 → E05에서 4/4 검출. 업체 묶음 처리 0.037~0.051 s, 피크 RSS 약 28 MB |
| 오류·한계 | 업체 코드 대응표를 E01 생성 규칙을 아는 상태에서 작성 — 낯선 코드 자동 매칭은 측정하지 않음 |
| 판단 | 조건부 채택 (실제 업체 파일 형식 확인 필요) |
| 미확인 | 실제 업체 파일, 대용량, `.xls` |

## E03 문서 직접 파서

| 질문 | 답 |
|---|---|
| 왜 | DOCX·PDF·PPTX 문서에서 ERP 입력값을 로컬 파서로 뽑을 수 있는지 |
| 무엇·데이터 | 합성 샘플 6개 + 공개 외부 문서(PubTables-1M 등, blind8·dev·holdout 분할) |
| 도구·비교군 | python-docx, python-pptx, pypdf, pdfplumber (직접 파서 v1, v2) |
| 정량 결과 | holdout PDF(공식 정답) v2: 표 6/6, 셀 625/676, 병합 23/30 (v1은 0). 합성 P-02: pdfplumber 셀 248/248, pypdf 표 0/3 |
| 오류·한계 | 선 없는 표 문서 X-HO-P01 셀 2/53. DOCX·PPTX 외부 정답은 잠정(사람 검수 미수행). 합성 문서는 같은 라이브러리 계열 왕복 가능성 |
| 판단 | pdfplumber v2·python-docx·python-pptx 조건부 채택(사람 검토 전제), pypdf는 표 용도 제외 |
| 미확인 | HWP·HWPX, 스캔 PDF·OCR, 다른 생성 도구로 만든 문서, DOCX·PPTX 검증된 정확도 |

## E04 직접 파서 vs Upstage (잠정)

| 질문 | 답 |
|---|---|
| 왜 | 외부 Document Parse API가 정확도 이익을 주는지, 비용·보안 부담을 정당화하는지 |
| 무엇·데이터 | 기존 호출 2회만: 합성 P-02(3쪽), 외부 X-DV-P04(2쪽, 공식 정답). **이번 정리에서 추가 호출 0** |
| 도구·비교군 | Upstage Document Parse standard vs pdfplumber v1·v2, pypdf |
| 정량 결과 | P-02: pdfplumber = Upstage (셀 248/248, 코드·수량·날짜 100%). X-DV-P04: 셀 47/47 동일, 병합 Upstage 4/6 vs v2 2/6. Upstage 8~10 s/건·쪽당 과금(추정 $0.02~0.03), 직접 0.04~1.6 s·비용 0 |
| 오류·한계 | Upstage는 셀 좌표 미제공(셀 단위 원본 추적 불가). 표본 2건 |
| 판단 | Upstage 보류(스캔·복잡 표 한정 조건부 검토 후보) |
| 미확인 | E04 본 실험(holdout·스캔 PDF), 실제 청구 비용, API 보안 정책 |

## E05 Python/Pydantic/SQLite 검증

| 질문 | 답 |
|---|---|
| 왜 | 공통 스키마와 SQL만으로 데이터 정합성·업무 규칙 검증이 어디까지 되는지 (모든 비교의 Baseline) |
| 무엇·데이터 | 규칙 42개(채점 41), 독립 평가셋 72개(기대 항목 80) |
| 도구·비교군 | Python(E01 Pydantic + 규칙 함수), Pydantic 단독, SQLite 검증 질의, SQLite 제약 적재 |
| 정량 결과 | Python·SQL 99/0/0, Pydantic 단독 31/0/68, 제약 적재 50/114/49. L(17,454 레코드) 검증 Python 0.20 s, SQLite 0.31 s |
| 오류·한계 | Pydantic lax 모드가 NaN·지수·전각 숫자 수용, SQLite FK 기본 off·date('2026-02-30') 정규화, 제약 적재 연쇄 거부, model_validator 가림 |
| 판단 | Python·SQLite 검증 조건부 채택, 단독 방식 제외 |
| 미확인 | 실제 업무 규칙(합성 가정 5개), 운영 DB 방언, Pydantic strict 적용(D-029) |

## E06 RDF/SHACL 비교

| 질문 | 답 |
|---|---|
| 왜 | 온톨로지·SHACL이 Python/SQL보다 검증·관계 조회·규칙 변경에서 이익이 있는지 |
| 무엇·데이터 | E05와 같은 평가셋·정답·채점기, Q1~Q5, 변경 시나리오 5개, S/M/L(×1·×10·×50) 3회 |
| 도구·비교군 | rdflib 7.6.0 + pyshacl 0.40.1 (shape 418개) vs E05 Python·SQLite, RDFLib SPARQL |
| 정량 결과 | 99/0/0, E05와 데이터셋별 차이 0. Q1~Q5 46/46 (세 방식 동일). L 검증 pyshacl 4,189 s·727 MB, hybrid 1,540 s, Python 0.20 s |
| 오류·한계 | rdflib 숫자·날짜 해석 관대, Core 비교 제약이 형식 오류에서 검증 전체 중단, SPARQL 경로식이 중간 BOM 상태를 못 거름, Q3·Q4가 계획 기간 기준 |
| 판단 | RDF/SHACL 보류, E07 GraphDB 보류 유지 |
| 미확인 | 다기업 의미 통합 데이터, 다른 SHACL 엔진 성능 |

## E08 운영 방식

| 질문 | 답 |
|---|---|
| 왜 | GPU 없는 CPU 서버·사내망에서 어떤 배치(로컬/API/하이브리드)가 맞는지 |
| 무엇·데이터 | E02~E06·E10의 기존 실측 인용 (새 인프라·API 호출 없음) |
| 도구·비교군 | CPU 로컬 / 외부 API / 하이브리드 |
| 정량 결과 | 정형·텍스트형 문서·검증·매핑 모두 GPU 없이 1초 이내, 수백 MB 이하. API 문서 1건 8~10 s |
| 오류·한계 | 측정 PC는 운영 서버가 아님. LLM·OCR·예측 미측정 |
| 판단 | CPU 로컬 기본안(조건부), 하이브리드 조건부 후보, 전체 API 제외(현 근거) |
| 미확인 | 기업 서버 사양·망·외부 전송 정책·처리량 |

## E10 모의 ERP 매핑·승인

| 질문 | 답 |
|---|---|
| 왜 | 파싱 값이 ERP로 들어갈 때 잘못된 값이 승인 없이 또는 잘못 승인되어 반영되지 않는지 |
| 무엇·데이터 | SQLite 모의 ERP(E01 엔터티 11개, DDL v0.2), 평가셋 18개 시나리오 + 독립 충돌 세트 5건, 업체 A 형식 입력 |
| 도구·비교군 | 규칙 기반 매핑(E02 설정) + E05 검증 재사용, 승인자 시뮬레이션 2종(ideal·rubber_stamp), 매퍼 v1·v2 |
| 정량 결과 | v1: 잘못된 반영 1/7(M13). v2: 네 조합 모두 잘못된 반영 0, 오류 후보 자동 승인 0, 승인 없는 본 테이블 행 0. 안전성 13/13. 필드 매핑 56/56. 21행 0.10 s |
| 오류·한계 | M13(코드·품명 충돌 덮어쓰기)→수정, DB 트리거 승인 재사용 허점→수정, 대기 중 재반입 중복 미탐지→수정. v2 기본 정책에서 X02 이력 검사 1건 실패(각본 가정 차이, 기록) |
| 판단 | 모의 ERP + staging·승인 계층 조건부 채택, 이중 안전장치 채택(원칙), 자동 승인 보류(기본 REVIEW_REQUIRED) |
| 미확인 | 실제 ERP·업체 문서, 파서 IR 자동 연결, 검색·LLM 후보(계약만) |

## E11 의사결정 계약

| 질문 | 답 |
|---|---|
| 왜 | 계획안 비교 전에 Hard Constraint가 가중치와 무관하게 지켜지는 계약을 고정 |
| 무엇·데이터 | T-01(수요 1,000·재고 200·안전재고 100·자재 2 kg·보유 1,500 kg·능력 800), T-02 대조, E01 계획안 3개 |
| 도구·비교군 | JSON Schema 계약 + 판정 함수 (예측·최적화 미구현) |
| 정량 결과 | 11/11 통과: 900·1,800 kg·300 kg·100개, 정규안 INFEASIBLE, 추가안 UNVERIFIED, E01 계획안 3개 모두 INFEASIBLE |
| 오류·한계 | E01 데이터에는 실행 가능 계획이 없어 계획 간 비교 시험 불가. 시간·수량 능력 환산 미정 |
| 판단 | 판정 규칙·계약 조건부 채택 |
| 미확인 | 예측·계획 생성·최적화, 필수 납기·업무 제약 정의 |

## 다른 담당자와 연계할 데이터 계약

| 계약 | 파일 | 연계 대상 |
|---|---|---|
| 파서 출력 (공통 IR 0.2) | [intermediate_representation.md](intermediate_representation.md) | 모든 문서 입력 |
| ERP 매핑 입력·후보·승인 | [e10_data_contract.md](e10_data_contract.md), `schemas/e10_mock_erp.sql` | 검색·에이전트 담당 |
| 매핑 후보 제공자 (BM25·임베딩·Tri-CHEF·LLM) | `schemas/e10_candidate_provider_contract.json` | 검색·에이전트 담당 |
| 계획 입력·예측·계획안·판정 | [e11_decision_interface.md](e11_decision_interface.md), [e11_constraint_policy.md](e11_constraint_policy.md), `schemas/e11_scenario_contract.json` | 예측·최적화 담당, 도메인·KPI 담당 |
