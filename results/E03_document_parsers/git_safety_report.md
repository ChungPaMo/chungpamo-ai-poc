# Git 업로드 전 안전 점검 — E03_document_parsers

> scripts/git_safety_check.py 실행 결과. 사용자 이름·PC 이름·홈 경로·로컬 검사어·비공개 원본 파일명은 기록하지 않는다.

- 종합: **통과**
- 커밋 후보 150개 (추적 중 127 + 미추적·비제외 23), 스테이징 0개, 작업트리 삭제 0개

## 1. 제외되어야 하는 항목 (`git check-ignore -v`)

| 항목 | 검사 경로 | 적용 규칙 |
|---|---|---|
| data/raw/ (UCI 원본 zip) | `data/raw/public/uci_daily_demand/daily+demand+forecasting+orders.zip` | `.gitignore:42:data/raw/*` |
| data/raw/ (UCI 원본 CSV) | `data/raw/public/uci_daily_demand/extracted/Daily_Demand_Forecasting_Orders.csv` | `.gitignore:42:data/raw/*` |
| data/raw/ (UCI 스테이징) | `data/raw/public/uci_daily_demand/staging_uci_daily_orders_v1.json` | `.gitignore:42:data/raw/*` |
| data/raw/ (다운로드 기록) | `data/raw/public/uci_daily_demand/download_record.json` | `.gitignore:42:data/raw/*` |
| data/raw/ (실제 기업 데이터 예시 경로) | `data/raw/company/sample.xlsx` | `.gitignore:42:data/raw/*` |
| 로컬 검사어 파일 | `configs/sensitive_terms.local.txt` | `.gitignore:35:configs/*.local.*` |
| .env | `.env` | `.gitignore:24:.env` |
| .venv/ | `.venv/pyvenv.cfg` | `.gitignore:2:.venv/` |
| __pycache__/ | `scripts/__pycache__/x.cpython-311.pyc` | `.gitignore:4:__pycache__/` |
| .pytest_cache/ | `.pytest_cache/README.md` | `.gitignore:6:.pytest_cache/` |
| 로그 | `results/run.log` | `.gitignore:65:*.log` |
| 임시파일 | `data/tmp.tmp` | `.gitignore:14:*.tmp` |
| Kaggle 인증 | `kaggle.json` | `.gitignore:33:kaggle.json` |
| 인증서·키 | `secrets/id.pem` | `.gitignore:31:secrets/` |
| 폰트 파일 | `data/documents/font.ttf` | `.gitignore:57:*.ttf` |
| 비공개 원본 문서 (docs/ PDF·DOCX) | 3개 (파일명 미기재) | 모두 제외 |

- `git status --ignored`의 제외 항목 11건 (최상위 단위)

## 2. 이미 추적 중인데 제외 규칙에 걸리는 파일 (`git ls-files -ci --exclude-standard`)

- 0건

## 3. 스테이징 상태 (`git diff --cached --name-only`)

- 0건 (커밋 승인 전이므로 스테이징하지 않음)

## 4. 추적되어야 하는 공개 가능 항목

| 분류 | 파일 수 |
|---|---|
| 정답셋·대응표 (data/canonical) | 9 |
| 합성 업체 파일 (data/vendor_a, vendor_b) | 15 |
| 오류 주입본 (data/invalid) | 16 |
| 실험 코드 (scripts) | 20 |
| 테스트 (tests) | 5 |
| 비식별 결과 (results) | 44 |
| 문서 (docs, CLAUDE.md 등) | 21 |
| 빈 폴더 유지 (.gitkeep) | 17 |

- 커밋 후보 중 제외 규칙에 걸린 파일: 0건

## 5. 내용 검사 (텍스트·JSON·CSV는 UTF-8/CP949 해독, XLSX는 내부 XML 전체)

- 검사 패턴: 사용자 홈 경로, 사용자 폴더 경로, PC 이름, 개인 이메일, API 키·토큰 형태, 개인키 블록, 비공개 자료 용어, 로컬 검사어(팀원 실명 등)
- 차단 대상 검출: **0건**
- 허용 검출 2건: 검사 규칙을 정의하는 스크립트의 정규식 문자열 (실제 비공개 내용 아님)
  - `scripts/git_safety_check.py`: 비공개 자료 용어
  - `scripts/run_e01.py`: 비공개 자료 용어

## 6. 공개 데이터 원본 복제 여부·라이선스

- UCI 원본 데이터 행(60행)이 그대로 들어 있는 커밋 후보: 0건
- 원본 헤더 문자열을 포함한 커밋 후보: 3건 (docs/data_source_research.md, results/E01_dataset/archive_v1/uci_source_verification.json, results/E01_dataset/uci_source_verification.json) — 구조 검증 기록용 헤더·요약 통계
- 원본 zip·CSV·스테이징(원본 값 전체)은 `data/raw/`에만 있고 Git 제외
- SalesHistory는 원본 총주문을 가상 제품에 나눈 합성값(SYNTHETIC/ALLOCATED)이며 원본 행이 아니다
- 라이선스: UCI Daily Demand Forecasting Orders = CC BY 4.0 (재배포·가공 허용, 출처 표기 필요). 정답셋 `dataset.public_sources`와 `uci_source_verification.json`에 출처·인용·DOI 기재
- Kaggle M5: 다운로드하지 않음 (라이선스 미확인)

## 6-0. 문서 메타데이터·폰트 (DOCX·PPTX·XLSX core/app XML, PDF Info)

- 폰트 파일 커밋 후보: 0건
- 회사명·외부 링크·외부 파일 참조가 있는 문서: 0건

| 파일 | 작성자 | 최종 수정자 | 회사 | 외부 링크 |
|---|---|---|---|---|
| `data/documents/D-01_bom_spec.docx` | chungpamo-poc (synthetic sample generator) | chungpamo-poc (synthetic sample generator) |  | 0 |
| `data/documents/D-02_order_inventory.docx` | chungpamo-poc (synthetic sample generator) | chungpamo-poc (synthetic sample generator) |  | 0 |
| `data/documents/P-01_bom_spec.pdf` | chungpamo-poc \(synthetic sample generator\) | None |  | 0 |
| `data/documents/P-02_order_inventory.pdf` | chungpamo-poc \(synthetic sample generator\) | None |  | 0 |
| `data/documents/T-01_plan_comparison.pptx` | chungpamo-poc (synthetic sample generator) | chungpamo-poc (synthetic sample generator) |  | 0 |
| `data/documents/T-02_bom_spec.pptx` | chungpamo-poc (synthetic sample generator) | chungpamo-poc (synthetic sample generator) |  | 0 |
| `data/invalid/vendor_a/vendor_a_master.xlsx` | e01_generate | None |  | 0 |
| `data/invalid/vendor_b/vendor_b_master.xlsx` | e01_generate | None |  | 0 |
| `data/vendor_a/vendor_a_master.xlsx` | e01_generate | None |  | 0 |
| `data/vendor_b/vendor_b_master.xlsx` | e01_generate | None |  | 0 |

## 6-1. 파일 크기

- 커밋 후보 전체 2,710,457 bytes, 최대 파일 `results/E02_tabular_parsing/output/invalid_vendor_a.json` 231,135 bytes
- 1 MB 이상: 0건 / 10 MB 이상(차단): 0건

## 7. 커밋 대상과 제외 대상

- 커밋 대상(승인 시): 위 4절의 공개 가능 파일 전부 (정답셋 v1·v2, 합성 업체 파일, 오류 주입본, 코드, 테스트, 비식별 결과, 문서)
- 제외 대상: data/raw/ 전체(UCI 원본·스테이징), 로컬 검사어 파일, 비공개 원본 문서, .env, .venv/, 캐시, 로그·임시파일
- 커밋·푸시: 하지 않음 (사용자 승인 대기)
