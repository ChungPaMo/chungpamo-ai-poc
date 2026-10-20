# 의사결정 기록 — 충파모 과제 7 사전 기술 PoC

- 작성일: 2026-10-20 (1단계 초안)
- 개정: 2026-10-20 2단계 — 사용자 확정 결정 D-001~D-003 기록, E00 상태 반영
- 현재 상태: **모든 기술 채택 판단은 미결정**. 개발환경 관련 결정(D-001~D-003)만 확정되었다. E00 외에는 실험이 실행되지 않았으므로 이 문서에 기록된 성능·비용 값은 없다.

---

## 1. 판단 규칙

### 1.1 실험 상태와 채택 판단의 분리

- 실험 상태(`NOT_STARTED / RUNNING / COMPLETED / BLOCKED / INVALID`)는 실행 사실만 나타낸다. 정의는 [evaluation_protocol.md](evaluation_protocol.md) §7.
- 실험이 `COMPLETED`라는 이유만으로 기술을 채택하지 않는다.
- 판단 근거가 되는 실험이 `INVALID`이면 해당 판단은 무효로 하고 재실행 후 다시 판단한다.
- 판단 근거가 되는 실험이 `BLOCKED`이면 해당 기술은 원칙적으로 `보류`로 두고, 차단 사유를 기록한다.

### 1.2 채택 판단 구분

| 판단 | 정의 | 기록 필수 항목 |
|---|---|---|
| 채택 | MVP에 포함한다. 실측 근거가 팀 합의 목표를 충족하고, GPU·망·보안 조건 및 8주 구현 가능성에 문제가 없다. | 근거 지표, Baseline 대비 결과, 남은 위험 |
| 조건부 채택 | 특정 조건(문서 유형, 승인, 수요기업 환경 등)이 충족될 때만 포함한다. | 조건, 조건 미충족 시 대체안 |
| 보류 | 근거 부족·선행조건 미충족·환경 미확정으로 지금 판단하지 않는다. | 재검토 조건, 필요한 추가 실험 |
| 제외 | MVP 및 사전 PoC 이후 계획에서 제외한다. 더 단순한 대체안으로 충분하거나 부담이 이익보다 크다. | 제외 이유, 대체안 |

### 1.3 판단 시 반드시 답할 질문 (업무분장 12절 기준)

1. 기존 기준(Baseline) 대비 무엇이 얼마나 나아졌는가? — 실측값으로만 답한다.
2. 기업의 GPU·망·보안 조건을 만족하는가? — 미확정이면 `미확인`.
3. 8주 내 구현·운영 가능한가?
4. 더 단순한 대체안은 무엇인가?

결과가 없으면 `예정` 또는 `미측정`으로 기록하고 성능을 단정하지 않는다. 합성 데이터 결과는 현장 성능으로 표현하지 않는다.

---

## 2. 정량 목표값 (모두 팀 합의 필요)

| 항목 | 관련 실험 | 목표값 | 상태 |
|---|---|---|---|
| CSV/Excel 필수 필드 정확 일치율 | E02 | 팀 합의 필요 | 미정 |
| 문서 파서 필수 필드 정확 일치율 | E03, E04 | 팀 합의 필요 | 미정 |
| 표 셀 정확 일치율 / 표 구조 보존율 | E03, E04 | 팀 합의 필요 | 미정 |
| 숫자·단위 보존율 | E02~E04 | 팀 합의 필요 | 미정 |
| 파일당 처리시간 허용 상한 | E02~E04 | 팀 합의 필요 | 미정 |
| 파서 타임아웃 기준 | E02~E04 | 팀 합의 필요 | 미정 |
| API 테스트 예산 상한 / 파일당 허용 비용 | E04 | 팀 합의 필요 | 미정 |
| 오류 탐지율 / 허용 오탐 수 | E05, E06 | 팀 합의 필요 | 미정 |
| 관계 조회 정답률 | E05~E07 | 팀 합의 필요 | 미정 |
| "추가 이익"으로 인정할 기준(RDF/GraphDB가 A 대비) | E06, E07 | 팀 합의 필요 | 미정 |
| 반복 측정 횟수 | 전체 | 3회 (초기 제안값 반영, 2026-10-20) | 제안 반영, 팀 확인 대기 |
| 육안 대조 표본 비율 | E01 | 10% 이상 제안, 팀 합의 필요 | 미정 |

---

## 3. 기술별 판단표

| 기술 | 근거 실험 | 실험 상태 | 판단 | 근거 요약 | 대체안 |
|---|---|---|---|---|---|
| pandas/openpyxl CSV·Excel 파싱 | E02 | NOT_STARTED | 미결정 | — | 표준 csv + openpyxl |
| python-docx (DOCX) | E03 | NOT_STARTED | 미결정 | — | 사용자 측 PDF 변환 |
| 로컬 PDF 파서 (pypdf / PyMuPDF / pdfplumber) | E03 | NOT_STARTED | 미결정 | — | — |
| HWPX 파서 | E03 | NOT_STARTED | 미결정 | — | 사용자 측 PDF/DOCX 변환 |
| HWP 파서 | E03 | NOT_STARTED | 미결정 | — | 사용자 측 HWPX/PDF 변환 |
| Upstage Document Parse API | E04 | NOT_STARTED | 미결정 | — | 로컬 PDF 파서 + 로컬 OCR |
| 공통 JSON/Pydantic + SQL | E05 | NOT_STARTED | 미결정 | — | — (Baseline) |
| RDFLib + RDF + SHACL | E06 | NOT_STARTED | 미결정 | — | 방식 A |
| GraphDB + SPARQL | E07 | NOT_STARTED | 미결정 | — | RDFLib SPARQL, 방식 A |
| OWL 추론 | — | 계획 없음 | 미결정 (필요성 확인 전 미구현) | — | SHACL·SQL 규칙 |
| 배치 방식 (로컬/API/하이브리드) | E08 | NOT_STARTED | 미결정 | — | — |

---

## 4. 결정 대기 항목 (사용자·팀 확인 필요)

| ID | 결정 사항 | 관련 | 결정 주체 | 상태 |
|---|---|---|---|---|
| D-001 | 프로젝트 폴더 Git 저장소 초기화 및 GitHub 원격 사용 여부 | E00 | 사용자 | **확정** (DEC-20261020-01) — 로컬 Git 승인, GitHub 연결 보류 → **후속 승인**(DEC-20261020-04): Public 저장소 연결·최초 푸시 |
| D-002 | 가상환경 도구 선택 (uv / venv+pip) 및 Python 3.11.9 고정 여부 | E00 | 사용자 | **확정** (DEC-20261020-02) — Python 3.11.9 + venv/pip |
| D-003 | 실험용 패키지 설치 승인 범위 (pandas, PyMuPDF, pdfplumber, pydantic, rdflib, pyshacl, psutil, pytest 등) | E00 이후 | 사용자 | **부분 확정** (DEC-20261020-03) — pytest·psutil 및 필수 의존성만 승인. 나머지 패키지는 해당 실험 착수 시 별도 승인 |
| D-004 | 범위 축소 제안: E03(HWP)·E06·E07을 "판단용 경량 검증"으로 축소하는 우선순위 제안 수용 여부 | 전체 | 팀 | 대기 (팀 합의 필요) |
| D-005 | 다단계 BOM 포함 여부, 주문·생산능력 데이터 규모 | E01, E07 | 팀 | **초기 제안값 반영** (2026-10-20, 사용자 제시): 제품 5·자재 10·BOM 약 20행·최대 2단계·주문 20·자원 3·주간 계획·KRW·EA/kg/g/h. 세부 가정 ASM-01~15는 [schema §1.1](manufacturing_data_schema.md). 팀 확인 대기 |
| D-006 | HWP/HWPX 샘플 확보 방법 (한글 미설치) | E01, E03 | 팀 | 대기 |
| D-007 | 외부 API(Upstage) 사용 승인, API 키 발급 주체, 테스트 예산 | E04 | 회사·운영기관 | **예비 호출 1회 승인·실행** (사용자, DEC-20261020-11). E04 본 실험·예산은 미결정 |
| D-008 | GraphDB 사용 여부, 라이선스 조건, 설치 방식 (Windows/WSL; Docker 미설치) | E07 | 팀 | 대기 (별도 확인 필요) |
| D-009 | 파서 라이선스 허용 범위 (예: AGPL 도구 사용 가능 여부) | E03 | 팀 | 대기 |
| D-010 | §2 정량 목표값 전체 | 전체 | 팀 | 대기 (반복 측정 3회만 초기 제안값으로 반영) |
| D-011 | E01 데이터 생성용 패키지 설치 승인 (목록: experiment_plan.md E01 "데이터 생성 필요 패키지") | E01 | 사용자 | **부분 확정** (DEC-20261020-05) — pydantic, openpyxl만. 문서 생성 패키지는 미승인 |
| D-012 | 공개 데이터 다운로드 승인 — UCI(DL-1), M5(DL-2) ([data_source_research.md](data_source_research.md) §8) | E01 | 사용자 | **부분 확정** (DEC-20261020-05) — UCI만 다운로드, M5 보류 |
| D-013 | 공개 데이터를 SalesHistory에 쓸지 여부와 방식(UCI 배분 / M5 대응 / 미사용) | E01 | 팀 | **사용자 지시로 UCI 배분 적용** (DEC-20261020-05). 팀 확인 대기 |
| D-014 | E03 문서 샘플 생성·파서 패키지 설치 승인 (python-docx, PDF 생성·추출 도구, python-pptx, lxml 등) | E03 | 사용자 | **부분 확정** (DEC-20261020-10) — python-docx, reportlab, python-pptx, lxml 설치(+필수 의존성 Pillow·XlsxWriter·charset-normalizer). PDF 파서·HWP 도구·OCR은 미승인 |
| D-017 | HWP/HWPX 열림 확인·HWP 변환·독립 검수 담당(한글 프로그램 보유자) 지정 | E03 | 팀 | 대기 (지정 전 HWP·HWPX는 검증 완료 처리 불가) |
| D-018 | PyMuPDF(AGPL-3.0/상용 이중 라이선스) 사용 여부 | E03 | 팀 | 대기 |
| D-019 | 공통 중간 JSON 0.2 변경안(content_set·logical_id·planned/actual 위치 등) 채택 여부 | E03 | 팀 | **명세 반영** (DEC-20261020-10, intermediate_representation.md §8). E02 출력은 0.1 그대로 |
| D-020 | 폰트 서브셋을 임베드한 PDF(P-01·P-02)의 공개 저장소 업로드 | E03 | 사용자 | **보류** (2026-10-20) — 맑은 고딕 서브셋의 재배포 조건(Microsoft EULA) 미확인. 로컬 전용(.gitignore 명시). 해제 방안: ① 재배포 가능 폰트(예: OFL 한글 폰트)로 재생성 — 재생성 시 E03 결과 재측정 필요 ② 라이선스 확인 |
| D-021 | E04 본 실험 착수와 호출·비용 상한 ([e04_upstage_plan.md](e04_upstage_plan.md) §4) | E04 | 사용자 | 본 실험 대기. E03 실패 사례 진단용 제한 비교만 승인·수행 (2026-10-21, Standard 1회·2쪽, DEC-20261021-01) |
| D-023 | 외부 문서 원본(Apache-2.0·MIT·CC BY)의 공개 저장소 업로드 여부 — 라이선스상 재배포는 허용(고지 의무)되나 현재 로컬 전용 | E03 | 사용자 | 대기 ([e03_external_testset_plan.md](e03_external_testset_plan.md) §8). X-P05는 문서 자체 저작권 미확인 |
| D-025 | 외부 문서 텍스트가 담긴 정답·파서 출력·API 응답의 공개 여부 | E03 | 사용자 | **결정 (2026-10-21, DEC-20261021-01)** — 원본·텍스트 포함 정답·원문 복원 가능 출력·첨부·미확인 SmartArt/차트 원문·API 응답은 비공개, 코드·채점기·테스트·출처·해시·분할·집계·비식별 오류 통계·보고서는 검사 통과 시 공개 |
| D-026 | 외부 DOCX·PPTX 잠정 정답(PROVISIONAL)의 사람 뷰어 검수 담당·범위 (VERIFIED_MANUAL 승격 조건) | E03 | 사용자·팀 | **방식 승인**, 담당 미배정 — 체크리스트·목록 준비([e03_external_manual_review_checklist.md](e03_external_manual_review_checklist.md)), 검수 미수행 |
| D-027 | 직접 파서 v2 채택 여부 (v1 대체 또는 병행) | E03 | 사용자·ChatGPT | **조건부 병행 채택** (2026-10-21) — v1 유지, v2 별도 버전. 잠정 정답 의존 기능은 검수 후 확정 |
| D-024 | 외부 문서 정답 작성 방식 승인: 공식 주석·저장소 기대값 우선, 나머지 수동 검수(검수 담당 지정), PubTables 주석 규칙(빈 셀·행 머리·헤더 정규화) 채점 반영 방식, 블라인드 프로토콜(§5) | E03 | 사용자·팀 | 대기 |
| D-022 | E03 완료 판정 조건: 생성 도구와 다른 경로로 만든 문서(Word·PowerPoint·한글에서 저장한 파일, 선 없는 표 PDF 등) 추가 측정 필요 여부, HWP/HWPX 미측정 상태로의 완료 가능 여부 | E03 | 사용자·팀 | 대기 (직접 파서 Baseline은 같은 라이브러리 계열 왕복 결과 — `parser_baseline/summary.md` §5) |
| D-015 | Upstage Document Parse의 지원 입력 형식(HWP/HWPX/PPTX 포함 여부) 공식 문서 확인 | E04 | 팀 | 대기 (확인 전 지원 가정 금지) |
| D-016 | E02 pandas 비교 실행 여부 (pandas 설치 승인 포함) | E02 | 사용자·팀 | **보류** (2026-10-20, DEC-20261020-09) — 1차 Baseline 결과상 급하지 않음. 대용량·`.xls`·자동 형식 추론 위험 확인이 필요할 때 재검토 |

---

## 5. 결정 기록 (Decision Log)

결정이 내려지면 아래 형식으로 추가한다. 기술 채택 판단 기록은 아직 없다(개발환경 결정만 기록).

```
### DEC-YYYYMMDD-NN: <제목>
- 날짜:
- 결정 주체:
- 대상 기술 / 관련 결정 대기 ID:
- 판단: 채택 / 조건부 채택 / 보류 / 제외
- 근거 실험 및 상태:
- 근거 지표 (분자/분모 포함):
- Baseline 대비:
- GPU·망·보안 조건:
- 8주 구현 가능성:
- 조건 / 재검토 조건:
- 대체안:
- 남은 불확실성:
```

### DEC-20261020-01: 로컬 Git 초기화 승인, GitHub 연결 보류
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 관련 결정 대기 ID: D-001
- 결정 내용: 프로젝트 루트에 로컬 Git 저장소를 초기화한다. GitHub 원격 저장소 연결·업로드는 하지 않는다.
- 이행: `git init` 완료(브랜치 `master`), 원격 없음. 최초 커밋은 사용자 승인 대기. Git 사용자 이름·이메일은 설정하지 않음.
- 조건: `.gitignore`로 `.venv/`, 비밀 설정(`.env` 등), `data/raw/`, `docs/` 아래 비공개 원본 PDF/DOCX를 추적에서 제외. `git add -A` 사용 금지.
- 재검토 조건: GitHub 사용 여부는 사용자가 별도로 결정한다.
- 후속: 2026-10-20 사용자가 GitHub 연결을 승인함 → DEC-20261020-04 (이 기록은 당시 결정으로 보존).

### DEC-20261020-02: Python 3.11.9 + 표준 venv/pip 확정
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 관련 결정 대기 ID: D-002
- 결정 내용: Python 3.11.9, 표준 `venv` + `pip`, `requirements.lock`(pip freeze 형식)으로 의존성을 고정한다. uv는 사용하지 않는다.
- 이행: `.venv` 생성(전역 site-packages 미포함). 실행은 `.\.venv\Scripts\python.exe` 명시적 경로 사용(PowerShell 실행 정책 변경 없음).
- 근거 실험: E00 — `COMPLETED` (results/E00_environment/run_meta.json)

### DEC-20261020-03: pytest·psutil 및 필수 의존성 설치 승인
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 관련 결정 대기 ID: D-003 (부분)
- 결정 내용: pytest, psutil과 그 하위 의존성 설치를 승인한다.
- 이행: pytest 9.1.1, psutil 7.2.2 및 하위 의존성(colorama 0.4.6, iniconfig 2.3.1, packaging 26.3, pluggy 1.7.0, Pygments 2.21.0) 설치, `pip check` 이상 없음.
- 미승인: pandas, PyMuPDF, pdfplumber, pydantic, rdflib, pyshacl 등 — 해당 실험 착수 시 별도 승인.
- 후속: 2026-10-20 E01용으로 pydantic, openpyxl 설치 승인 → DEC-20261020-05.

### DEC-20261020-04: GitHub Public 저장소 연결 및 최초 커밋·푸시 승인
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 관련 결정 대기 ID: D-001 (DEC-20261020-01의 "GitHub 연결 보류"를 후속 승인으로 해소)
- 결정 내용: `origin` = https://github.com/ChungPaMo/chungpamo-ai-poc (Public 유지), 브랜치 `main`. 공개 전 팀원 실명을 역할명으로 바꾸고, 외부 공개가 제한된 평가 내용과 비공개 원본 파일명을 문서에서 삭제. 작성자 이메일은 이 저장소에만 GitHub noreply 주소 사용.
- 이행: 최초 커밋 `3920191305f9f2c37fd8beab7e97899fbf2f376b` 일반 푸시(강제 푸시 없음).
- 조건: 이후 커밋·푸시는 매번 사용자 승인 필요. 공개 데이터 원본·비공개 문서·인증정보 업로드 금지.

### DEC-20261020-05: E01 데이터 구축 착수 및 패키지·다운로드 승인
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 관련 결정 대기 ID: D-011(패키지), D-012(다운로드 — UCI만), D-013(공개 데이터 사용 — UCI 배분 허용, M5 미사용)
- 결정 내용: 가상환경에 pydantic, openpyxl만 추가 설치. UCI Daily Demand 원본을 공식 출처에서 받아 `data/raw/public/uci_daily_demand/`에 보관(Git 미추적). Kaggle M5는 이번 단계에서 받지 않음. 문서(PDF/DOCX/HWP/HWPX) 생성은 하지 않음.
- 조건: E01 상태는 `RUNNING` 유지, 완료 판정은 사용자·ChatGPT 검토 후.

### DEC-20261020-06: E01 정답셋 v2 (계획안 비교 로직 수정) 및 E00 XML 보정
- 날짜: 2026-10-20
- 결정 주체: 사용자 지시 (E01 최종 검증 보완)
- 결정 내용: ① 계획안 의미를 정규(정규시간 자체 생산) / 잔업(정규 + 잔업 가용시간, 실제 잔업·추가비용 별도 계산) / 외주(명시 수량만 외주, 자체 능력 사용량과 외주비 별도)로 재정의 ② 정답셋을 `ground_truth_v2.json`으로 버전 올림, v1은 보존 ③ UCI 요일 코드는 의미 미확인으로 숫자 보존, 날짜는 합성 표시 ④ E00 `pytest_report.xml` 원본은 보존하고 보정본을 별도 파일로 생성
- 근거: v1 잔업안의 능력 초과가 정규안보다 커진 원인은 라인 단위 잔업 버킷 모델의 결함 ([decision_logic.md](decision_logic.md) §6.1)
- 합성 가정: 가상 외주처 능력 150 EA/주, 리드타임 7일, 자재 외주처 부담

### DEC-20261020-07: E01 완료 승인
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 결정 내용: E01 상태를 `COMPLETED`로 기록. 계획안 비교 규칙은 v2(`ground_truth_v2.json`)를 PoC 기준으로 사용하고 v1(`ground_truth_v1.json`)은 보존.
- 근거 (승인 시점 실측): 독립 검증 143/143 통과, pytest 48/48 통과(스킵 0), 재현성 31/31 파일 바이트 일치, Git 보안 점검 통과 (`results/E01_dataset/run_meta.json`, `git_safety_report.md`)
- 한계 (합성 시나리오):
  - 반제품 생산능력 부족은 완제품 공급(납기) 계산에 반영하지 않음
  - 가상 외주처 조건(FG003만, 150 EA/주, 리드타임 7일, 자재 외주처 부담)은 합성 가정
  - 모든 마스터·주문·재고·비용 값은 합성값이며 현장 성능을 나타내지 않음
- 이 판단은 E01 데이터셋 구축 완료에 대한 것이며, 어떤 기술의 채택 판단도 아니다.
- E00 원본 결과는 변경하지 않음 (XML 보정본은 별도 파일).

### DEC-20261020-08: 문서 파싱 검증 범위 확정 (7개 형식)
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 결정 내용: 파싱 검증 범위를 CSV, XLSX, DOCX, PDF, HWP, HWPX, PPTX로 확정. E03에 PPTX 추가(후보 파서 python-pptx). E02~E04는 공통 중간 JSON([intermediate_representation.md](intermediate_representation.md))과 형식별 지표(evaluation_protocol.md §10)를 쓴다.
- 조건(DEC-08 계속): E04에서 HWP/HWPX/PPTX의 API 지원 여부는 공식 문서 확인 전까지 가정하지 않음(D-015). 원본 파일이 없는 형식은 샘플 확보 계획만 세우고 측정 완료로 처리하지 않음. E02 구현 범위는 넓히지 않음. 패키지 설치·E03·E04 구현·외부 API 호출은 별도 승인 전 하지 않음.

### DEC-20261020-09: E02 1차 Baseline 완료 (E02 전체는 RUNNING)
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 결정 내용: 표준 csv + openpyxl Baseline 결과를 1차 완료로 기록. E02 전체 상태는 `RUNNING` 유지. pandas 비교는 D-016 보류.
- 근거 (실측, `results/E02_tabular_parsing/`): 정상 입력 18개 파일·시트 필수 필드·ID·위치 역추적 모두 일치, 오류 입력 파서 범위 9/9 탐지, 오탐 0, pytest 전체 통과
- 범위 명시: 주입 오류 13건 중 9건만 파서 범위, 4건(납기<주문일, BOM 순환, BOM 버전 중복, 할당>보유)은 E05 업무 규칙 검증 대상. 경고 12건(ERR-UNRESOLVED, 헤더 손상의 파생 영향)은 정탐·오탐과 별도.
- 한계: 코드 매핑 41항목은 수작업 설정이며 자동 매핑 정확도는 측정하지 않음. 단위 오류 진단 위치는 주입 목록을 본 뒤 수정했으므로 새 오류에 대한 일반화는 미확인.
- 이 판단은 기술 채택 판단이 아니다.

### DEC-20261020-10: E03 문서 샘플 생성 착수, OCR 우선순위 제외
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 결정 내용: ① DOCX·텍스트형 PDF·PPTX 6개 샘플 생성·독립 검증 ② 패키지 python-docx·reportlab·python-pptx·lxml 설치 승인(Pillow는 필수 의존성으로 설치됨) ③ **OCR은 현재 우선순위에서 제외** — 스캔형 PDF(S-01·S-02) 생성 보류, OCR 엔진 설치·인식 실험·인식률 측정·Upstage 호출 금지. 스캔 문서는 향후 E04(Upstage)에서 검증 예정, 지원 형식·조건은 공식 문서·계약 확인 후 확정 ④ 공통 중간 JSON 0.2 필드 정의 ⑤ PDF 표 영역 bbox IoU 임시 기준 0.5
- 유지: HWP/HWPX는 최종 검증 대상이나 이번 단계에서 생성·변환·파싱하지 않음(미측정), 한글 프로그램 보유자 지정(D-017) 미결정. E03 상태 RUNNING.

### DEC-20261020-11: Upstage Document Parse 예비 호출 1회 (E04 본 실험 아님)
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 결정 내용: 로컬 `.env`의 `UPSTAGE_API_KEY`로 E03 합성 문서 P-02(텍스트형 PDF 3쪽)만 1회 전송. model `document-parse`, mode `standard`, 재시도·동시 요청·Enhanced·OCR 전용 모델 없음. 패키지 python-dotenv, requests 설치.
- 실행 결과: 성공(HTTP 200), 응답 모델 `document-parse-260930`, 과금 3쪽(standard), 추정 $0.03(VAT 별도, 공개 단가 기준 — 실제 청구는 콘솔 확인 전 미확인). 응답 원문은 `data/raw/upstage_test/`(Git 제외), 요약은 `results/E04_upstage_preflight/`.
- 조건: 실패 시 승인 없이 재호출 금지(호출 기록 파일로 차단). 결과는 1개 문서 예비 확인이며 정확도로 일반화하지 않음. E04 본 실험은 별도 승인.

### DEC-20261020-12: E03 직접 문서 파서 Baseline 착수, pypdf·pdfplumber 설치
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 결정 내용: DOCX = python-docx, PPTX = python-pptx, PDF = pypdf·pdfplumber로 직접 파서 Baseline 측정. PyMuPDF(D-018)·HWP/HWPX 파서·OCR 엔진은 설치하지 않음. Upstage는 기존 예비 결과만 참고(추가 호출 금지).
- 이행: pypdf 6.21.1(BSD-3-Clause), pdfplumber 0.11.10(MIT) 설치 — 의존성 pdfminer.six 20260107(MIT), pypdfium2 5.14.0(BSD-3-Clause·Apache-2.0, PDFium 바이너리 포함), cryptography 50.0.2(Apache-2.0 OR BSD-3-Clause), cffi 2.1.1(MIT-0), pycparser 3.11(BSD-3-Clause). 모두 Python 3.11 지원, `pip check` 이상 없음.
- 환경 수정: 새 클론 검증에서 `requirements.lock`의 한국어 주석 때문에 pip이 파일을 cp949로 읽어 설치가 실패함을 발견(최초 커밋부터 존재한 결함). 첫 줄에 `# -*- coding: utf-8 -*-` 선언을 추가해 해결하고, 새 가상환경에서 설치·pip check·pytest로 확인.
- 결과: `results/E03_document_parsers/parser_baseline/` (상태 RUNNING). 이 판단은 기술 채택 판단이 아니다.

### DEC-20261020-13: E03 외부 제작 문서 테스트셋 확보 착수 (확보·분석·평가 설계까지)
- 날짜: 2026-10-20
- 결정 주체: 사용자
- 결정 내용: 공개 저장소·데이터셋에서 외부 제작 문서 후보를 확보하고 독립 정답셋과 블라인드 평가를 설계한다. 파서 수정·실행·채점, Upstage 호출, OCR은 하지 않는다. 외부 원본은 `data/raw/external_documents/`(Git 제외).
- 이행: 최종 후보 8건(DOCX 2·PPTX 2·PDF 4) + 예비 5건 확보 ([e03_external_testset_plan.md](e03_external_testset_plan.md)). PubTables-1M은 주석 아카이브 앞부분만 스트리밍(JSON 40개), 원본 PDF는 PMC 공개 버킷에서 CC BY 논문만. 검사는 평가 대상 파서를 쓰지 않음(zipfile+lxml, pypdfium2).
- 한계: Word·한글 저장 DOCX, 공식 정답이 있는 선 있는 격자 표 PDF는 확보하지 못함.

### DEC-20261020-14: E03 외부 문서 일반화 검증·직접 파서 v2 (장기 작업, 로컬 전용)
- 날짜: 2026-10-20
- 결정 주체: 사용자 (승인 범위 안에서 중간 승인 없이 진행, 커밋·푸시·API 호출 금지)
- 이행: 평가 묶음 고정(blind8·dev·holdout) → 독립 정답 v1(공식 + 잠정, 사람 검수 0) → v1 최초 블라인드 평가(덮어쓰기 금지) → 실패 분석 → v2(`src/parsers/v2/`, dev로만 조정) → v2 동결 → holdout v1·v2 1회 평가 → blind8 v2 회귀 측정.
- 결과: [e03_external_generalization_report.md](e03_external_generalization_report.md). holdout PDF(공식 정답) 표 재현율 0/6 → 6/6, 셀 텍스트 0/676 → 625/676. DOCX·PPTX 개선은 대부분 잠정 정답 기준.
- 이 판단은 기술 채택 판단이 아니며 E03은 RUNNING.

### DEC-20261021-01: E03 v2 결과 확정 절차, 공개 정책(D-025), v2 조건부 병행(D-027), Upstage 제한 비교(D-021 일부)
- 날짜: 2026-10-21
- 결정 주체: 사용자
- 결정 내용: ① 외부 문서 원본·텍스트 포함 정답/출력·첨부·API 응답 비공개, 공개는 코드·채점기·테스트·출처·해시·분할·집계·보고서(문자열 검사 통과 시) ② v2는 v1을 대체하지 않는 별도 버전으로 조건부 병행 ③ E03 실패 사례 진단용 Upstage Standard 비교: 전체 과금 4쪽 이하, Enhanced·OCR 모델·재시도 금지, 문서 자르기 금지 ④ 사람 검수는 방식만 승인(담당 미배정)
- 이행: 재검증(`external_verification.json`) — holdout 무결성 확인, 공식·잠정 혼합 수치 1건 분리 보고. 정답 작성기의 외부 문자열 제거(정답 불변 확인). Upstage는 조건을 만족하는 문서가 X-DV-P04(2쪽) 1건뿐이라 1회·2쪽 호출(추정 $0.02). 검수 목록 523항목 준비.
- E03 상태 RUNNING, E04 본 실험 미착수.
