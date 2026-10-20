# 실험 계획 — 충파모 과제 7 사전 기술 PoC

- 작성일: 2026-10-20 (1단계 초안)
- 개정: 2026-10-20 2단계 보완 — E00 완료 조건·실행 결과 반영, venv + pip 확정(D-002), HWP 정답 원천 예외 및 독립 검수 규칙(E01)
- 담당: 파서·온톨로지 담당 (구현 지원: Claude Code / 설계·검토: ChatGPT)
- 대상 MVP: AI 기반 기업 운영계획 시뮬레이션 및 의사결정 지원
- 관련 문서: [evaluation_protocol.md](evaluation_protocol.md), [decisions.md](decisions.md), [environment_inventory.md](environment_inventory.md)
- 참고 자료: 팀 내부 업무분장 문서(비공개, 저장소에 포함하지 않음)

> 이 문서는 계획이다. 아래의 가설과 예상 실패 유형은 검증 전 가정이며, 어떤 실험도 아직 실행되지 않았다.

---

## 0. 범위와 우선순위

### 0.1 범위 우선순위

8주 MVP 일정에서 온톨로지·GraphDB·HWP 파서·예측·최적화를 동시에 적용하면 범위가 과다해질 위험이 있다. 사전 PoC는 각 기술을 MVP에 넣을지, 후속 범위로 분리할지를 **실측 근거로 판단하기 위한** 실험이므로 해당 기술을 모두 검토하되, CSV·Excel 매핑 경로를 핵심으로 두고 우선순위를 다음과 같이 **제안**한다(팀 확인 필요).

| 우선순위 | 실험 | 이유 |
|---|---|---|
| 핵심 | E00, E01, E02, E05 | MVP의 CSV·Excel 매핑 경로. 다른 실험의 Baseline |
| 판단용 경량 검증 | E03, E04, E06, E07 | MVP 포함/후속 분리 여부를 결정하기 위한 최소 실험. 구현 범위를 넓히지 않음 |
| 종합 | E08, E09 | 측정 결과 기반 배치·채택 판단 |

### 0.2 실험 목록과 상태

| ID | 실험 | 상태 | 선행 실험 |
|---|---|---|---|
| E00 | 개발환경 및 재현성 확인 | COMPLETED (2026-10-20, 결과 검토 대기) | — |
| E01 | 제조업 공통 합성 데이터·정답셋 구성 | COMPLETED (2026-10-20 승인 — 독립 검증 143/143, pytest 48/48, 재현성 31/31, Git 보안 점검 통과. 정답셋 v2 기준, v1 보존. `results/E01_dataset/summary.md`) | E00 |
| E02 | CSV/Excel 직접 파싱 | RUNNING — 1차 Baseline(csv + openpyxl) **완료** (2026-10-20 승인, DEC-20261020-09), pandas 비교 보류(D-016). `results/E02_tabular_parsing/summary.md` | E01 |
| E03 | DOCX/PDF/HWP/HWPX/PPTX 직접 추출 파서 비교 | NOT_STARTED (문서 샘플 미확보 — 확보 계획만 수립) | E01, E02 검토 |
| E04 | 복잡한 PDF·스캔 문서: 직접 추출 vs Upstage Document Parse API | NOT_STARTED | E01, E03(PDF 직접 추출 결과) |

**전체 파싱 검증 범위 (2026-10-20 확정)**: CSV, XLSX (E02) / DOCX, PDF, HWP, HWPX, PPTX (E03) / 복잡한 PDF·스캔 문서 (E04). 세 실험 모두 공통 중간 JSON([intermediate_representation.md](intermediate_representation.md))과 형식별 지표([evaluation_protocol.md](evaluation_protocol.md) §10)를 쓴다.
| E05 | 공통 JSON/Pydantic/SQL 데이터 검증 | NOT_STARTED | E01, E02 |
| E06 | RDFLib/RDF/SHACL 검증 | NOT_STARTED | E01, E05 |
| E07 | GraphDB/SPARQL 관계 조회 | NOT_STARTED | E06 |
| E08 | CPU/API/하이브리드 운영 검토 | NOT_STARTED | E02~E07 측정 결과 |
| E09 | 기술 채택 판단 및 보고서 작성 | NOT_STARTED | E00~E08 |

```
E00 → E01 ─┬→ E02 → E05 → E06 → E07 ─┐
           ├→ E03 → E04 ──────────────┼→ E08 → E09
           └──────────────────────────┘
```

### 0.3 공통 원칙

- 동일 입력·동일 정답셋·동일 지표로 비교한다 (평가 프로토콜 준수).
- 외부 API에는 합성·공개 데이터만 보낸다. 실기업 데이터는 반출 승인 전 사용 금지.
- 측정하지 않은 값은 `미측정`, 목표값은 `팀 합의 필요`로 기록한다.
- 패키지 설치·외부 API 호출·도구 설치는 단계별로 사용자 승인 후 수행한다.
- 실행 환경은 Python 3.11.9 + 표준 `venv` + `pip` + `requirements.lock`으로 확정했다(D-002). 모든 스크립트는 `.\.venv\Scripts\python.exe`로 직접 실행한다.

---

## E00. 개발환경 및 재현성 확인

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | 다른 팀원·다른 PC에서도 동일 결과를 재현할 수 있는 실행 환경을 확정한다. |
| 2. 기술적 가설 | 프로젝트 전용 `venv` + 버전 고정 `requirements.lock` + Git 커밋 해시 기록으로, 동일 Windows 환경에서 같은 스크립트를 재실행했을 때 환경 안정 필드가 동일하게 재현된다. |
| 3. 필요한 입력 데이터 | 없음 (environment_inventory.md 결과 사용) |
| 4. 비교 대상과 Baseline | 도구 비교는 하지 않음 — D-002로 표준 `venv + pip` 확정(uv 사용 안 함). 재현성 비교 = 같은 환경의 1차 실행 vs 2차 실행 |
| 5. 정답 데이터 확보 방법 | 해당없음. 정확도 지표 대신 환경 안정 필드 비교(evaluation_protocol.md §9) |
| 6. 평가 지표 | 안정 필드 일치 여부(불일치·누락·미측정 건수), pytest 통과/실패/오류/스킵 수, `pip check` 결과, lock 파일과 설치 버전 일치, 출력의 민감 경로 포함 여부, 한글 경로 처리 |
| 7. 실행 방법 | ① `git init`(원격 연결 없음) ② `py -3.11 -m venv .venv` ③ `pip install pytest psutil` → `pip check` → `requirements.lock` 작성 ④ `.\.venv\Scripts\python.exe scripts\run_e00.py` 실행: 환경 점검 3회(기본·run1·run2, 각각 별도 프로세스) → 안정 필드 비교 → `pytest -v` → `run_meta.json`·`summary.md` 자동 작성 및 상태 판정 |
| 8. 예상 실패 유형(가설) | 콘솔 cp949 인코딩으로 한글/특수문자 출력 오류(1단계 조사 중 실제 1건 관찰됨), `python3` Store 별칭 오호출, 전역 패키지와 가상환경 혼용, 일부 패키지의 Windows 휠 부재 |
| 9. 결과 파일명 | `results/E00_environment/` 아래 `env_check.json`, `env_check_run1.json`, `env_check_run2.json`, `run_meta.json`, `summary.md`, `pytest_output.txt`, `pytest_report.xml` / `requirements.lock` / `docs/environment_inventory.md`(갱신) |
| 10. 선행조건 및 미확정 사항 | 확정: 로컬 Git(D-001), Python 3.11.9 + venv/pip(D-002), pytest·psutil 설치(D-003). 미확정: 최초 커밋 시점, GitHub 원격 사용 여부 |
| 11. 후속 의사결정 조건 | 아래 완료 조건 충족 + 사용자·ChatGPT 검토 후 E01 진입. 재현 실패 시 원인 해결 전까지 다른 실험 결과는 `INVALID` 가능성 표시 |

**E00 완료 조건** (모두 충족 시 `COMPLETED`, `scripts/run_e00.py`가 자동 판정)

1. `.\.venv\Scripts\python.exe --version`이 3.11.9이고, 가상환경이 전역 site-packages를 포함하지 않음
2. `pip check` 이상 없음, `requirements.lock`의 모든 고정 버전이 가상환경 설치 버전과 일치
3. 환경 점검 스크립트 3회 실행 모두 종료코드 0, 필수 필드에 미측정 없음 (미측정 시 `errors`에 사유 기록)
4. run1·run2의 안정 필드가 모두 일치 (누락·미측정은 불일치로 간주)
5. pytest 전체 통과 (실패·오류 0)
6. 결과 파일에 사용자 홈 경로·사용자 이름·PC 이름이 없음
7. `run_meta.json`, `summary.md`가 측정값으로 작성됨

**E00 실행 결과 (2026-10-20)**: `COMPLETED` — pytest 16개 통과(실패·오류·스킵 0), 안정 필드 25개 일치, 수집 오류 0건. 상세는 `results/E00_environment/summary.md`.

---

## E01. 제조업 공통 합성 데이터·정답셋 구성

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | 모든 실험이 공유할 단일 정답 원천(canonical JSON)과 오류 주입 데이터셋, 형식별 파생 문서를 만든다. |
| 2. 기술적 가설 | 제품 5종·자재 10종·BOM 약 20행 규모로도 각 실험의 주요 실패 유형(단위 불일치, 고아 참조, 표 구조 손실 등)을 재현할 수 있다. |
| 3. 필요한 입력 데이터 | 제조 시나리오 정의(제품·자재·BOM·주문·재고·생산능력·리드타임), 업체별 컬럼 표기 사례, 오류 주입 목록(프로토콜 §2.4) |
| 4. 비교 대상과 Baseline | 해당없음(데이터 구축). 단, 정상 데이터셋 vs 오류 주입 데이터셋을 쌍으로 구성 |
| 5. 정답 데이터 확보 방법 | 정답 원천을 먼저 작성 → 동결·해시 기록 → 이 원천으로부터 CSV/XLSX/DOCX/PDF(텍스트형·스캔형)/HWPX를 생성. **HWP는 예외**(아래 "HWP 정답 원천 예외" 참고). 오류 주입 위치는 `data/canonical/injected_errors_v1.json`에 기록(정답셋 공식 경로는 `data/canonical/`, 오류 주입본은 `data/invalid/`). 생성 코드와 채점 코드 분리, 일부 표본 육안 대조 |
| 6. 평가 지표 | 정량: 엔터티별 레코드 수, 오류 유형별 주입 건수, 형식별 생성 성공 파일 수, 육안 대조 표본의 불일치 건수. 정성: 시나리오의 현실성(도메인 멘토·산업데이터·KPI 조사 담당의 조사와 대조) |
| 7. 실행 방법 | ① 스키마·필드 목록 확정 ② 정답 원천 작성 ③ Vendor A/B 이형 표현 정의 ④ 오류 주입 ⑤ 형식별 문서 생성 ⑥ 육안 대조 ⑦ 정답셋 v1 동결 |
| 8. 예상 실패 유형(가설) | 한글 미설치로 HWP 샘플 생성 불가, 스캔형 PDF 생성 도구 부재, 생성 코드가 파서와 동일 라이브러리를 써서 평가가 순환적이 됨, 합성 데이터가 실제 현장 형식을 대표하지 못함 |
| 9. 결과 파일명 | `data/canonical/ground_truth_v1.json`, `data/canonical/injected_errors_v1.json`, `data/vendor_a/*`, `data/vendor_b/*`, `data/documents/*`, `results/E01_dataset/dataset_manifest.csv`(파일명·형식·해시·생성방법) |
| 10. 선행조건 및 미확정 사항 | 주문·생산능력 규모, 다단계 BOM 포함 여부, 필수 필드 목록, 오류 유형별 주입 건수, HWP/HWPX 샘플 확보 방법(한글 프로그램 보유자 협조 또는 공개 샘플), 공개 데이터 사용 시 라이선스 확인(산업데이터·KPI 조사 담당과 연계) |
| 11. 후속 의사결정 조건 | 정답셋 v1 동결 후에만 E02~E07 착수. 형식별 샘플 확보가 불가하면 해당 형식 실험은 `BLOCKED` |

**E01 명세 산출물 (2026-10-20, 데이터 미생성)**: [data_source_research.md](data_source_research.md), [manufacturing_data_schema.md](manufacturing_data_schema.md), [decision_logic.md](decision_logic.md), [data_provenance_policy.md](data_provenance_policy.md), [data_provenance_design.md](data_provenance_design.md), [ontology_competency_questions.md](ontology_competency_questions.md), [ontology_design_patterns.md](ontology_design_patterns.md), [ontology_standards_review.md](ontology_standards_review.md). E06·E07은 이 문서들의 CQ·패턴·추적 설계와 평가 프로토콜 §5.4를 따른다.

**초기 실험 범위 (초기 제안값, 2026-10-20)**: 제품 5종(완제품 3 + 반제품 2), 자재 10종, BOM 약 20행, 다단계 BOM 최대 2단계, 주문 20건, 자원 3종, 주간 생산계획(4주), 화폐 KRW, 단위 EA/kg/g/h, 반복 측정 3회. 세부 가정은 [manufacturing_data_schema.md](manufacturing_data_schema.md) §1.1 (ASM-01~15).

**데이터 생성 필요 패키지 (미설치, 승인 대기 — D-011)**

| 용도 | 후보 패키지 | 설치 상태(가상환경) | 비고 |
|---|---|---|---|
| canonical JSON, CSV, 해시, 매니페스트 | 표준 라이브러리 (`json`, `csv`, `hashlib`, `random`, `decimal`) | 설치 불필요 | 시드 고정 |
| 정답 원천 스키마 검증 | `pydantic` | 미설치 | E05와 같은 모델을 공유할 수 있음 |
| XLSX (Vendor A/B, 병합 헤더) | `openpyxl` | 미설치 (전역에만 3.1.5 존재 — 사용하지 않음) | |
| DOCX | `python-docx` | 미설치 (전역에만 1.2.0 존재) | |
| 텍스트형 PDF | `reportlab` 또는 `fpdf2` 중 1개 | 미설치 | 한글 폰트 필요. Windows 시스템 폰트는 로컬 생성용으로만 쓰고 폰트 파일은 저장소에 넣지 않음(폰트 라이선스 확인 필요) |
| 스캔형 PDF (이미지 렌더링) | `Pillow` (+ 위 PDF 패키지) | 미설치 (전역에만 12.3.0 존재) | 래스터화 방식은 E01 생성 시 결정 |
| HWPX | 표준 `zipfile` + `lxml` | `lxml` 미설치 (전역에만 존재) | 직접 작성한 HWPX가 한글 프로그램에서 열리는지 확인 불가(한글 미설치) → 정답 원천 예외 규칙 적용 가능성 |
| HWP | 해당 패키지 없음 | — | 정답 원천 예외(아래)로 별도 확보 |

- 표 형식 데이터(canonical JSON, CSV, XLSX)만 먼저 만든다면 `pydantic`, `openpyxl` 2개로 시작할 수 있다. 문서 형식은 E03 직전에 생성해도 된다(단계 분리 여부는 사용자 결정).
- 버전은 설치 시점의 최신 안정판으로 정하고 `requirements.lock`에 고정한다.

**HWP 정답 원천 예외**

- HWP(바이너리)는 한글 프로그램 미설치로 canonical JSON에서 직접 생성할 수 없다. 따라서 HWP에 한해 "정답 원천 → 문서 생성" 원칙의 예외를 허용한다.
- 허용 경로: ① 공개 HWP 샘플 ② 한글 프로그램 보유자가 canonical JSON을 보고 별도로 제작한 HWP ③ HWPX/DOCX를 한글 프로그램으로 변환한 HWP.
- 위 경로로 확보한 HWP는 다음을 모두 기록·수행한다.
  - **출처 기록**: 파일 출처(URL 또는 제작자 역할), 확보일, 라이선스·재배포 조건, 제작·변환 도구와 버전, 파일 SHA-256 → `dataset_manifest.csv`
  - **독립적인 정답 검수**: HWP용 정답은 평가 대상 파서의 출력에서 만들지 않는다. 한글 프로그램(또는 그 PDF 출력)에서 사람이 직접 읽어 정답 JSON을 작성하고, 작성자와 다른 1인이 대조 검수한다. 검수자·검수일·불일치 건수와 해결 내용을 기록한다.
  - 별도 제작본(②, ③)은 canonical JSON과의 차이(제작 중 생긴 오탈자·누락 등)를 검수에서 확인하고, 차이가 있으면 HWP 정답은 **검수된 정답 JSON**을 기준으로 한다.
  - 공개 샘플(①)은 제조 시나리오와 내용이 다르므로 형식 호환성(열림 여부, 텍스트·표 추출 여부) 평가에 주로 쓰고, 다른 형식과의 정확도 직접 비교에는 쓰지 않는다.

---

## E02. CSV/Excel 직접 파싱

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | 업체별로 다른 CSV/Excel을 공통 스키마로 정확히 읽어올 수 있는지 확인한다(MVP 핵심 경로). |
| 2. 기술적 가설 | pandas/openpyxl 직접 파싱 + 명시적 컬럼 매핑 사전만으로 Vendor A/B 정상 데이터의 필수 필드를 정확히 추출할 수 있으며, 병합 헤더·숫자 형식 차이는 전처리 규칙으로 처리 가능하다. |
| 3. 필요한 입력 데이터 | E01의 Vendor A/B CSV·XLSX(정상/오류 주입), 컬럼 매핑 사전 |
| 4. 비교 대상과 Baseline | Baseline = Python 표준 `csv` + openpyxl 직접 읽기. 비교 = pandas(`read_csv`, `read_excel`). 인코딩(UTF-8/UTF-8-BOM/CP949) 변형 포함 |
| 5. 정답 데이터 확보 방법 | E01 정답 원천 및 `injected_errors_v1.json` |
| 6. 평가 지표 | 필수 필드 정확 일치율·누락률, 숫자·단위 보존율, 주입 오류 탐지율(ERR-MISSING/DUPID/UNIT/NUMFMT), 처리시간, 피크 메모리, 실패율. 정성: 매핑 규칙 추가 공수 |
| 7. 실행 방법 | 파일별 각 도구로 읽기 → 매핑·정규화 → 공통 JSON 출력 → 정답 비교 → `metrics.csv` |
| 8. 예상 실패 유형(가설) | CP949 CSV 인코딩 오인식, `1,500` 문자열 처리, 선행 0이 있는 ID의 숫자 변환(예: `001`→`1`), 병합 헤더 오해석, 빈 행·숨김 시트, 날짜 자동 변환 |
| 9. 결과 파일명 | `results/E02_tabular_parsing/metrics.csv`, `failures.md`, `summary.md`, `run_meta.json` |
| 10. 선행조건 및 미확정 사항 | pandas 설치 승인, 컬럼 매핑 방식(규칙 사전 고정 — 자동 매핑은 매핑·에이전트·보안 담당의 Tri-CHEF 실험과 분리), `.xls` 구형식 포함 여부 |
| 11. 후속 의사결정 조건 | 결과가 E05 입력이 된다. 필수 필드 정확도 목표값은 `팀 합의 필요` |

**E02 1차 실행 (2026-10-20, RUNNING)**: Baseline(표준 csv + openpyxl)만 실행했다. pandas 비교는 하지 않았다(설치 미승인). 파서 `src/parsers/`, `src/normalization/`, 매핑 설정 `configs/e02_vendor_mapping.json`, 채점기 `scripts/e02_grade.py`(파서와 분리), 실행기 `scripts/e02_run.py`. 결과는 `results/E02_tabular_parsing/`. 업무 규칙 오류 4건(납기<주문일, BOM 순환, BOM 버전 중복, 할당>보유)은 파서 범위 밖으로 분류해 E05로 넘긴다.

---

## E03. DOCX/PDF/HWP/HWPX/PPTX 직접 추출 파서 비교

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | 비정형 문서 형식(DOCX, PDF, HWP, HWPX, PPTX)별로 로컬 직접 추출 파서가 텍스트·표·ID·버전·원본 위치를 보존하는지, 그리고 HWP/HWPX를 무GPU 로컬 환경에서 처리할 수 있는지 확인한다. |
| 2. 기술적 가설 | DOCX·HWPX·PPTX(ZIP+XML 구조)·텍스트형 PDF는 로컬 파서로 표 구조를 상당 부분 보존할 수 있고, HWP(바이너리)는 오픈소스 도구로 처리 가능한 범위가 제한적이다. PPTX는 도형 배치 순서와 읽기 순서가 달라 텍스트 순서 보존이 위험 요소다. 스캔형 PDF는 OCR 없이 처리할 수 없다. (모두 검증 전 가설) |
| 3. 필요한 입력 데이터 | E01 정답 원천에서 만든 동일 내용 DOCX / 텍스트 PDF / 스캔 PDF / HWPX / HWP / PPTX (ERR-TABLE, ERR-IDVER 케이스 포함). **현재 원본 파일 없음** → 아래 "문서 샘플 확보 계획" |
| 4. 비교 대상과 Baseline | 직접 추출 방식만 비교한다. DOCX: python-docx(Baseline). PDF: pypdf(Baseline) vs PyMuPDF vs pdfplumber. HWPX: zipfile+lxml 직접 파싱(Baseline) vs 공개 라이브러리 후보. HWP: olefile/pyhwp 계열 후보(호환성 미확인). **PPTX: python-pptx(후보, Baseline)**, 비교 = zipfile+lxml 직접 파싱. 각 후보의 최종 목록은 설치 가능성·라이선스 확인 후 확정 (모두 미설치, 설치 승인 필요) |
| 5. 정답 데이터 확보 방법 | E01 정답 원천(같은 내용을 여러 형식으로 렌더링했으므로 형식 간 동일 정답 사용) |
| 6. 평가 지표 | 필수 필드 정확 일치율·누락률, 표 검출 재현율·정밀도, 표 셀 정확 일치율(+내용 일치율), 표 구조 보존율, 페이지 넘김 표 연결, 숫자·단위 보존율, 제품 ID·문서 버전 보존 여부, 텍스트 블록 순서 보존, 머리말·각주·발표자 노트 보존, 원본 위치 보존 성공률(형식별 판정 — protocol §10.3), 처리시간, 피크 메모리, 추출 실패율, 오류 복구 여부. 정성: 설치 난이도, 라이선스, 유지보수 상태 |
| 7. 실행 방법 | 형식×파서 조합 실행 → 공통 중간 JSON([intermediate_representation.md](intermediate_representation.md)) 변환 → 파서와 분리된 채점기로 정답 비교. 각 조합 3회 반복 측정 |
| 8. 예상 실패 유형(가설) | PDF 표가 줄 단위 텍스트로 풀림, 병합 셀 위치 이동, 머리말·표 제목의 버전 정보 누락, HWP 배포용/암호 문서 열기 실패, HWP 5.0 이외 버전 미지원, 한글 조합형 문자 깨짐, PPTX 그룹 도형·이미지 속 표 누락, 슬라이드 도형 순서 뒤섞임, 스캔 PDF에서 빈 출력(`output_generated=False`) |
| 9. 결과 파일명 | `results/E03_document_parsers/metrics.csv`, `compatibility_matrix.md`(형식×도구), `failures.md`, `summary.md`, `run_meta.json` |
| 10. 선행조건 및 미확정 사항 | 문서 샘플 확보(아래 계획), HWP/HWPX 샘플(한글 미설치), 파서·생성 도구 설치 승인(python-docx, PyMuPDF, pdfplumber, python-pptx, PDF 생성 도구 등 — 모두 미설치), PyMuPDF 라이선스(AGPL/상용) 확인, OCR 후보 추가 여부(Tesseract 등 미설치), 파서별 라이선스 검토, PDF bbox IoU 임계값(팀 합의) |
| 11. 후속 의사결정 조건 | 형식별 권장 파서·라우팅 규칙 도출. HWP 처리 불가 시 "사용자 측 PDF/HWPX 변환 후 업로드" 같은 대체안 검토 → MVP 포함/후속 분리 판단 근거 |

**문서 샘플 확보 계획 (2026-10-20, 계획만 — 샘플 미생성, 측정 미실행)**

| 형식 | 현재 원본 | 확보 방법 (안) | 정답 위치 기록 방법 | 필요 승인·선행조건 |
|---|---|---|---|---|
| DOCX | 없음 | E01 canonical에서 생성 (제품 사양서·BOM 표·머리말 버전, 병합 셀 표 포함) | 생성 시 문단·표 순번 기록 | 생성 패키지(python-docx) 설치 승인 |
| PDF (텍스트형) | 없음 | E01 canonical에서 생성 (페이지 넘김 표, 머리말 ID·버전 포함) | 생성 도구가 아는 좌표(bbox)를 생성 시 기록 | PDF 생성 패키지 설치 승인, 한글 폰트 사용 조건 확인 |
| PDF (스캔형) | 없음 | 텍스트형 PDF를 이미지로 렌더링해 재조립 (해상도 기준 팀 합의) | 원 텍스트형 PDF 좌표를 해상도 비율로 환산 | 렌더링 도구 설치 승인 |
| HWPX | 없음 | canonical에서 XML 직접 작성 시도. 한글 프로그램에서 열리는지 확인 불가 → HWP 예외 규칙 준용 가능성 | 섹션·문단 ID 생성 시 기록 | lxml 설치 승인, 한글 프로그램 보유자 확인 |
| HWP | 없음 | 공개 샘플 또는 한글 보유자가 별도 제작 (E01 "HWP 정답 원천 예외") | 사람이 뷰어에서 확인해 독립 검수 | 제작·검수 담당 지정 |
| PPTX | 없음 | E01 canonical에서 생성 (슬라이드별 표 도형, 그룹 도형, 텍스트 상자, 발표자 노트에 버전 정보) | 생성 시 슬라이드 번호·도형 ID 기록 | python-pptx 설치 승인 |

- 원본 파일이 없는 형식은 측정 완료로 처리하지 않는다. 샘플을 확보하기 전 E03의 모든 지표는 `미측정`이다.
- 샘플은 합성(SYNTHETIC) 또는 라이선스가 확인된 공개 자료만 쓴다.

---

## E04. 복잡한 PDF·스캔 문서: 직접 추출 vs Upstage Document Parse API

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | 복잡한 표·스캔 PDF에서 외부 Document Parse API가 로컬 직접 추출보다 정확도 이익이 있는지, 그 이익이 시간·비용·보안 부담을 상회하는지 확인한다. |
| 2. 기술적 가설 | 텍스트형 단순 표 PDF에서는 직접 추출과 API의 정확도 차이가 작고, 스캔 PDF·병합 셀 표에서는 API가 표 구조 보존에서 우세할 수 있다. (검증 전 가설) |
| 3. 필요한 입력 데이터 | E01 합성 PDF 5~10개(텍스트형/스캔형/복잡 표 포함). 실기업 문서 사용 금지. **HWP/HWPX/PPTX의 API 지원 여부는 공식 문서로 확인하기 전까지 가정하지 않는다** — 지원이 확인되면 해당 형식 추가를 별도 검토하고, 확인 전에는 E04 비교 대상에 넣지 않는다 |
| 4. 비교 대상과 Baseline | Baseline = E03에서 선정된 최선의 로컬 PDF 파서. 비교 = Upstage Document Parse API. 필요 시 로컬 OCR 대체 후보 1종 |
| 5. 정답 데이터 확보 방법 | E01 정답 원천 |
| 6. 평가 지표 | E03과 동일 지표 + API 호출 수(재시도 포함), 실제 청구 비용(콘솔 확인 전 `미확인`), 네트워크 포함 처리시간, 외부 전송 데이터 범위, API 오류율·재시도 성공 여부 |
| 7. 실행 방법 | 승인 후 API 키를 환경변수로 주입(코드·로그·결과 파일에 키 기록 금지) → 동일 PDF를 로컬/API로 처리 → 응답을 공통 중간형식으로 변환 → 정답 비교 |
| 8. 예상 실패 유형(가설) | API 응답 형식(HTML/Markdown) 변환 과정에서 셀 위치 손실, 한글 단위 표기 오인식, 요청 한도·타임아웃, 페이지 수 기준 과금으로 예상보다 비용 증가, 네트워크 차단 환경에서 실행 불가 |
| 9. 결과 파일명 | `results/E04_pdf_vs_upstage/metrics.csv`, `cost_log.csv`, `failures.md`, `summary.md`, `run_meta.json` |
| 10. 선행조건 및 미확정 사항 | 외부 API 사용 승인(회사·운영기관), API 키 발급 주체, 요금·무료 한도·데이터 보존·재학습 정책(공급사 공식 문서로 확인, 매핑·에이전트·보안 담당의 보안 검토와 연계), 테스트 예산 상한, **API의 지원 입력 형식(HWP/HWPX/PPTX 포함 여부) — 미확인, 공식 문서 확인 필요** |
| 11. 후속 의사결정 조건 | 정확도 이익과 비용·보안 조건을 함께 비교해 "API 사용 / 특정 문서 유형만 API / 미사용" 중 판단. API 승인 불가 시 `BLOCKED`로 두고 로컬 대체안만 판단 |

---

## E05. 공통 JSON/Pydantic/SQL 데이터 검증

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | 공통 스키마(JSON/Pydantic)와 관계형 SQL만으로 데이터 품질 검증과 관계 조회가 어디까지 가능한지 확인한다. 온톨로지 비교의 Baseline(방식 A). |
| 2. 기술적 가설 | Pydantic 필드 검증 + SQL 기본키·외래키·CHECK 제약으로 주입 오류 대부분(누락, 중복 ID, 잘못된 참조, 숫자 형식)을 탐지할 수 있고, 단위 불일치는 별도 규칙이 필요하다. |
| 3. 필요한 입력 데이터 | E01 정답 원천과 오류 주입 데이터셋(또는 E02 파싱 결과 — 파싱 오류와 검증 성능을 분리하기 위해 두 경우 각각 실행) |
| 4. 비교 대상과 Baseline | 본 실험 자체가 Baseline. 내부 비교: Pydantic만 / SQL 제약만 / 둘 다 |
| 5. 정답 데이터 확보 방법 | `injected_errors_v1.json`, 질의셋 기대 결과(프로토콜 §5.2) |
| 6. 평가 지표 | 오류 탐지율(유형별), 오탐 수, 잘못된 참조 처리 방식, 관계 조회 정답률(Q1~Q5), 적재·조회시간, 스키마 변경 시나리오별 수정 범위, 오류 메시지 활용성 |
| 7. 실행 방법 | Pydantic 모델 정의 → 검증 → SQLite(제안) 테이블·제약 생성 → 적재 → 질의셋 실행 → 스키마 변경 시나리오 적용 및 diff 측정 |
| 8. 예상 실패 유형(가설) | SQLite 외래키 기본 비활성 상태로 잘못된 참조 미탐지, 첫 오류에서 적재 중단되어 나머지 오류 미보고, 단위 환산 규칙 부재, 다단계 BOM 조회에 재귀 CTE 필요 |
| 9. 결과 파일명 | `results/E05_schema_sql/metrics.csv`, `queries.sql`, `schema_change_diff.md`, `failures.md`, `summary.md`, `run_meta.json` |
| 10. 선행조건 및 미확정 사항 | pydantic 설치 승인, DB 엔진 선택(SQLite 제안, 운영 DB와 차이 존재), 질의셋·스키마 변경 시나리오 확정 |
| 11. 후속 의사결정 조건 | E06·E07은 이 결과 대비 "추가로 무엇을 얻는가"로 평가한다. A만으로 요구가 충족되면 B/C는 보류·후속 분리 근거가 된다 |

---

## E06. RDFLib/RDF/SHACL 검증

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | 동일 데이터를 RDF로 표현하고 SHACL로 검증했을 때, 방식 A 대비 추가로 얻는 이익(용어 표준화, 이형 데이터 통합, 추가 검출 오류, 스키마 변경 용이성)과 비용을 확인한다(방식 B). |
| 2. 기술적 가설 | Vendor A/B의 이형 표현을 공통 어휘로 매핑하면 동일 질의로 통합 조회할 수 있고, SHACL은 필수값·카디널리티·참조 대상 클래스 검증을 선언적으로 표현할 수 있다. 단, 중복 ID·단위 환산은 별도 설계(SHACL-SPARQL 제약 또는 사전 정규화)가 필요하다. A 대비 우수성은 가정하지 않는다. |
| 3. 필요한 입력 데이터 | E05와 동일한 입력, 최소 온톨로지(TTL: 개념 10개 이내 — Product, Material, BOMLine, Order, Inventory, Resource, Supplier 등), SHACL shape |
| 4. 비교 대상과 Baseline | Baseline = E05(방식 A). 비교 = RDFLib + pySHACL + RDFLib 내 SPARQL |
| 5. 정답 데이터 확보 방법 | E05와 동일한 `injected_errors_v1.json`, 질의셋 기대 결과 |
| 6. 평가 지표 | E05와 동일 지표 + A 대비 추가 탐지 오류 유형, TTL·shape 작성 라인 수, 매핑 규칙 수 |
| 7. 실행 방법 | 온톨로지 초안 작성(OWL 추론 미사용) → CSV/JSON→RDF 매핑 → SHACL 검증 → 검증 보고서 파싱 → 질의셋 SPARQL 실행 → 스키마 변경 시나리오 적용 |
| 8. 예상 실패 유형(가설) | URI 설계 오류로 Vendor A/B의 동일 개체가 분리됨, 중복 ID가 RDF에서 하나의 노드로 병합되어 오류가 사라짐, 리터럴 타입(xsd:decimal) 변환 실패, SHACL 보고서가 원본 행 위치를 잃음, 열린 세계 가정으로 누락 판단 어려움 |
| 9. 결과 파일명 | `ontology/ontology_v1.ttl`, `ontology/shapes_v1.ttl`, `results/E06_rdf_shacl/metrics.csv`, `queries.rq`, `shacl_report.ttl`, `failures.md`, `summary.md`, `run_meta.json` |
| 10. 선행조건 및 미확정 사항 | rdflib·pyshacl 설치 승인, Protégé 사용 여부(업무분장 기재, 설치 필요), 네임스페이스·URI 정책, 원본 위치 추적(provenance) 표현 방식 |
| 11. 후속 의사결정 조건 | A 대비 추가 이익이 확인되지 않으면 RDF는 보류/후속 분리. 이익이 있으나 GraphDB 없이 충분하면 E07은 축소 실행 |

---

## E07. GraphDB/SPARQL 관계 조회

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | E06의 RDF를 GraphDB에 적재했을 때 RDFLib 메모리 그래프 대비 관계 조회·운영에서 실익이 있는지, 설치·운영 부담은 어느 수준인지 확인한다(방식 C). |
| 2. 기술적 가설 | 사전 PoC 규모(수백 트리플 수준)에서는 RDFLib와 GraphDB의 조회 정답률은 같고, GraphDB의 이점은 성능보다 운영 기능(영속 저장, 엔드포인트, 웹 UI)에 있다. 설치·운영 부담은 A·B보다 크다. |
| 3. 필요한 입력 데이터 | E06 RDF·온톨로지, 동일 질의셋 |
| 4. 비교 대상과 Baseline | Baseline = E05(SQL), E06(RDFLib SPARQL). 비교 = GraphDB SPARQL 엔드포인트 |
| 5. 정답 데이터 확보 방법 | 질의셋 기대 결과(E05·E06과 동일) |
| 6. 평가 지표 | 관계 조회 정답률, 잘못된 참조 처리, 적재·조회시간, JVM 피크 메모리(힙 설정 기록), 설치 단계 수·소요시간, 필요 런타임·포트, 라이선스 조건(확인 출처), 스키마 변경 시 재적재 범위 |
| 7. 실행 방법 | GraphDB 설치(승인 후, 로컬 Java 21 또는 WSL) → 저장소 생성 → 적재 → 질의셋 실행(HTTP SPARQL) → E06 결과와 비교 |
| 8. 예상 실패 유형(가설) | Free 에디션 기능·라이선스 제약, Java 버전 호환성, 메모리 부족(조사 시 가용 RAM 2.19GB), Windows 방화벽·포트 충돌, 다운로드에 회원가입 필요 |
| 9. 결과 파일명 | `results/E07_graphdb_sparql/metrics.csv`, `install_log.md`, `queries.rq`, `failures.md`, `summary.md`, `run_meta.json` |
| 10. 선행조건 및 미확정 사항 | **GraphDB 사용 여부, 라이선스 조건, 설치 방법(Windows 네이티브/WSL/Docker — Docker 미설치)은 별도 확인 필요**. 대안 트리플스토어 비교 여부 |
| 11. 후속 의사결정 조건 | 정답률이 B와 같고 운영 이점이 MVP 요구에 없으면 보류/후속 분리. 수요기업 환경 확정 후 재평가 |

---

## E08. CPU/API/하이브리드 운영 검토

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | GPU 없는 CPU 서버 환경을 기준으로, 기능별 로컬 CPU 실행 가능 여부와 외부 API 필요 여부를 구분하고 배치안 3종(로컬/API/하이브리드)을 비교한다. |
| 2. 기술적 가설 | 정형 파싱·검증·그래프 조회는 로컬 CPU로 충분하고, 외부 API가 필요한 영역은 스캔·복잡 표 문서와 LLM 기능에 한정된다. API 불가 환경에서는 수동 매핑·규칙 계산·사전 변환으로 기능 축소가 가능하다. |
| 3. 필요한 입력 데이터 | E02~E07 측정 결과, 다른 담당자(매핑·에이전트·보안 담당: LLM·보안, 예측·최적화 담당: 예측)의 실측 결과(있는 경우 인용) |
| 4. 비교 대상과 Baseline | Baseline = 전체 로컬 CPU. 비교 = 전체 외부 API / 하이브리드(문서 유형별 라우팅) |
| 5. 정답 데이터 확보 방법 | 해당없음. 각 실험의 측정값을 근거로 사용 |
| 6. 평가 지표 | 기능별 처리시간·피크 메모리(측정값 인용), 외부 전송 필드 목록, API 비용(실측만), 장애 시 대체 가능 여부, 필요 서버 사양(측정 근거 있는 항목만), 운영 복잡성 |
| 7. 실행 방법 | 기능×배치방식 비교표 작성 → 측정 없는 칸은 `미측정` → API 불가 시 기능 축소안 정의 → 수요기업 확인 질문 정리 |
| 8. 예상 실패 유형(가설) | 측정 PC(데스크톱)와 수요기업 서버 사양 차이로 일반화 곤란, 다른 담당자 결과 미확보로 비교표 공백, 호출 빈도 가정의 근거 부족 |
| 9. 결과 파일명 | `results/E08_deployment/deployment_comparison.md`, `function_matrix.csv`, `fallback_plan.md` |
| 10. 선행조건 및 미확정 사항 | 수요기업 GPU·망·보안 요구(미확정), 외부 API 사용 승인 절차, 호출 빈도 가정(팀 합의 필요) |
| 11. 후속 의사결정 조건 | 수요기업 조건 확정 전에는 "조건부" 배치안으로 제시. 확정 후 재평가 |

---

## E09. 기술 채택 판단 및 보고서 작성

| 항목 | 내용 |
|---|---|
| 1. 검증 목적 | 실측 근거로 기술별 채택/조건부 채택/보류/제외를 판단하고, 판단 이유·대안·남은 불확실성을 정리한다. |
| 2. 기술적 가설 | 해당없음(판단 단계). 단, "실험 완료 = 채택"이 아님을 전제로 한다. |
| 3. 필요한 입력 데이터 | E00~E08의 `summary.md`, `metrics.csv`, 팀 합의 목표값 |
| 4. 비교 대상과 Baseline | 기술별로 "더 단순한 대체안"(예: RDF vs SQL, API vs 로컬 파서)과 비교 |
| 5. 정답 데이터 확보 방법 | 해당없음 |
| 6. 평가 지표 | 기술별: Baseline 대비 개선 여부(측정값), GPU·망·보안 조건 충족 여부, 8주 내 구현·운영 가능성, 대체안. 결과 없는 항목은 `예정`/`미측정` 명시 |
| 7. 실행 방법 | decisions.md의 판단 규칙 적용 → 판단표 작성 → 팀·ChatGPT 검토 → 확정 |
| 8. 예상 실패 유형(가설) | 목표값 미합의로 판단 불가, 일부 실험 `BLOCKED`로 근거 부족, 합성 데이터 결과를 현장 성능으로 과장 |
| 9. 결과 파일명 | `docs/decisions.md`(갱신), `results/E09_report/tech_decision_report.md`, `results/E09_report/one_page_summary.md` |
| 10. 선행조건 및 미확정 사항 | 정량 목표값 팀 합의, 다른 담당자 결과 취합 형식(업무분장 08절 형식) |
| 11. 후속 의사결정 조건 | 판단 결과를 MVP 범위 확정 및 면담 Q&A 근거로 사용. `보류` 항목은 재검토 조건을 명시 |

---

## 부록. 해결되지 않은 기술적 질문

1. HWP 바이너리 샘플을 한글 프로그램 없이 어떻게 확보하고, 정답 원천과의 일치를 어떻게 보증할 것인가?
2. 스캔형 PDF를 어떤 도구로 생성할 것인가(이미지 렌더링 품질·해상도 기준)?
3. PDF 파서 후보(PyMuPDF)의 AGPL 라이선스가 MVP 배포 형태에 문제가 되는가?
4. RDF에서 중복 ID가 노드 병합으로 사라지는 문제를 어떤 방식(적재 전 검증 / 행 단위 provenance)으로 다룰 것인가?
5. SHACL 검증 결과를 원본 파일·행 위치로 되돌려 보여줄 수 있는가?
6. GraphDB의 현행 무료 사용 조건과 Windows 설치 방식은 무엇인가?
7. Upstage Document Parse API의 요금·데이터 보존·재학습 정책은 무엇이며, 테스트 승인 주체는 누구인가?
8. 다단계 BOM을 포함할 것인가? (E07 실익 평가와 직결)
9. ~~메모리 측정 도구(psutil) 설치 전에는 피크 메모리를 어떤 수준까지 측정할 수 있는가?~~ → 2단계에서 psutil 7.2.2 설치로 해소. 단, 샘플링 기반 피크 측정의 간격·자식 프로세스 포함 방식은 E02 착수 시 확정 필요.
10. HWP 독립 정답 검수를 수행할 한글 프로그램 보유자·검수자를 누가 맡을 것인가?
