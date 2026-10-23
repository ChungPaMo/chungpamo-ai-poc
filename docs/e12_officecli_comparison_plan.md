# E12 OfficeCLI 파싱 비교 계획

> 작성 2026-10-23. 상태 **COMPLETED** — 검토 완료, 기술 판단 보류(2026-10-23). 결과 보고: [e12_officecli_comparison_report.md](e12_officecli_comparison_report.md).
> 이 문서는 도구 조사와 탐색 실행 뒤, 본 실행(`scripts/e12_run.py`) 전에 정한 범위를 적은 것이다. 본 실행 중 바뀐 점은 §8에 따로 적었다.

## 1. 목적

iOfficeAI/OfficeCLI(v1.0.157)의 문서 읽기·구조 추출이 지금 쓰는 파서보다 나은지 같은 원본·같은 정답·같은 채점기로 잰다. 교체 여부를 미리 정하지 않는다. 기존 도구와 의미 있는 차이가 없으면 교체를 권하지 않는다.

| 형식 | 기존 파서 (기준선) | OfficeCLI 비교 범위 |
|---|---|---|
| XLSX | openpyxl 3.1.5 (`data_only=False/True`) | `get` / `query column` / `batch` |
| DOCX | E03 v2 (python-docx 1.2.0 + lxml) | `get /body·/header·/footer --depth 30`, `query footnote·endnote·paragraph` |
| PPTX | E03 v2 (python-pptx 1.0.2 + lxml) | `get /slide[i] --depth 30`, `query notes` |
| PDF | pdfplumber v2 | **NOT_SUPPORTED** — OfficeCLI 읽기 대상이 .docx/.xlsx/.pptx뿐이다. `view pdf`는 내보내기 기능이라 비교하지 않는다 |

## 2. 도구 확인 항목 (설치 전)

- 출처: GitHub Release `officecli-win-x64.exe` v1.0.157. `SHA256SUMS`와 GitHub API digest가 같은지 확인한 뒤 저장소 밖 사용자 로컬 도구 폴더에 둔다. 저장소에는 넣지 않고 실행 파일 해시만 기록한다.
- 확인 항목: Windows 지원, 읽기 명령, JSON 출력, 기능 범위, 로컬 전용 동작, 네트워크 사용(소스의 업데이트 확인 코드), 라이선스·비용, 코드 서명.
- 새 Python 패키지는 설치하지 않는다(실행 파일만 사용). 유료 API·가입은 없다.

## 3. 데이터 (기존 평가셋 재사용 우선)

| 묶음 | 문서 | 정답 상태 | 용도 |
|---|---|---|---|
| X12-01 합성 XLSX (신규, 생성기 `scripts/e12_make_xlsx.py`) | 1 (시트 3, 정답 셀 84) | GENERATED — 생성기 명세 | XLSX 정확도 |
| X12-02 (X12-01과 같은 셀, 수식 캐시값만 0) | 1 | GENERATED | 수식 캐시가 없는 파일에서의 차이 |
| E02 업체 XLSX (vendor_a, vendor_b) | 2 | 정답 없음 | 두 도구의 값 일치도만 본다 |
| E03 합성 DOCX·PPTX (D-01, D-02, T-01, T-02) | 4 | GENERATED (E03 생성 정답) | 정확도 |
| E03 외부 holdout (X-HO-D01~03, X-HO-T01~04) | 7 | **PROVISIONAL** (잠정, 사람 검수 없음) | 일반화 판단의 주 근거 |
| E03 외부 blind8·dev | 10 | PROVISIONAL | v2 개발에 쓴 문서라 참고·회귀 확인용. holdout과 섞지 않는다 |

X12의 신규 시험 항목: 일반 주문 표, 여러 시트, 병합 셀(가로·세로), 날짜, 금액·수량, 문자열로 저장된 숫자 "30", 잘못된 입력값 "1O50", 빈 셀, 수식(곱, SUM, 다른 시트 참조, `#VALUE!`), 숨긴 행·열. 값은 E01 제품 코드·단위를 쓴 합성 값이다.

## 4. 지표

- XLSX: 셀 값, 수식 문자열, 문자열 숫자 보존, 날짜 인식, 빈 셀 유지, 잘못된 값 보존, 병합 범위(오탐 포함), 숨긴 행·열.
- DOCX·PPTX: E03 채점기를 그대로 쓴다(`e03_grade_parsers.grade`, `e03_grade_external.grade`).
  - 표 탐지, 행·열 구조, 셀 텍스트(엄격·느슨), 병합, 머리글 셀
  - 본문 문단·글자, 읽기 순서, 각주, 머리글·바닥글
  - 도형 텍스트·위치, 그룹, SmartArt, 차트, 노트, 표 조각 연결
- OfficeCLI 출력은 같은 IR 0.2로 바꾼 뒤 채점한다. 변환 비용(`convert_s`)은 따로 잰다.
- 표 조각 연결은 두 쪽 모두 E03 공통 후처리 규칙(`header_repeat_rule`)을 같게 적용한다. 파서 기능이 아니다.
- 성능: 문서·방식별 3회.
  - 첫 실행과 반복(2·3회) 중앙값을 따로 기록한다. 피크 RSS, 실패 수도 기록한다.
  - 두 방식 모두 자식 프로세스 단위로 재므로 프로세스 시작 비용이 들어간다. 기존 파서의 프로세스 내부 파싱 시간도 따로 기록한다.
- 네트워크: 시간 측정과 분리한 감시 실행 1회. 실행 중 프로세스의 원격 TCP 연결을 기록한다.

## 5. 안전 규칙

- OfficeCLI는 항상 **원본의 임시 복사본**에 실행한다. 실행 전후 원본 해시를 확인한다.
  - `batch`에는 조회 명령(get/query)만 허용한다(코드에서 검사).
  - 탐색 단계에서 원본에 직접 실행해 원본이 바뀐 사고가 있었다(보고서 §9).
- 실행 시작·끝에 모든 입력 문서의 해시를 매니페스트와 대조한다. 끝에서 불일치하면 결과를 무효로 한다.
- 환경변수 `OFFICECLI_SKIP_UPDATE=1`로 업데이트 확인을 끈다.
- 외부 문서 출력과 외부 문서 사례는 `data/raw/e12_officecli/`에만 둔다(Git 제외, D-025). 공개 결과(`results/E12_officecli/`)에는 합성 문서 출력과 집계 수치만 둔다.
- 기존 E00~E11 코드·정답·결과는 수정하지 않는다. 결과 디렉터리에 파일이 이미 있으면 실행을 거부한다.

## 6. 산출물

| 파일 | 내용 |
|---|---|
| `scripts/e12_make_xlsx.py` | X12 합성 XLSX와 정답 생성 (결정적) |
| `scripts/e12_officecli.py` | OfficeCLI 실행 래퍼(임시 복사본, 시간·메모리·연결 감시) + OfficeCLI JSON → IR 변환 |
| `scripts/e12_run.py` | 비교 실행 → `results/E12_officecli/results.json`, `run_meta.json`, `outputs/synthetic/` |
| `scripts/e12_examples.py` | 형식별 실제 사례 → `results/E12_officecli/examples.json` (외부 사례는 `data/raw/e12_officecli/examples_external.json`) |
| `scripts/e12_summary.py` | 분할별 집계 → `results/E12_officecli/summary.json` |
| `tests/test_e12_officecli.py` | 변환 규칙(정상 + 음성 대조), 정답 재현, 결과 일관성, 공개 파일 누출, 실제 실행 |

## 7. 판단 기준

- 정량 합격선은 정하지 않는다(팀 합의 필요).
- 판단 순서: holdout 정확도 차이 → 기존 파서가 못 하는 기능이 있는지 → 성능·운영 위험.
- 판단 선택지: 기존 파서 대체 / 일부 기능에 보조 사용 / 조건부 도입 / 보류 / 제외.

## 8. 본 실행 중 바뀐 점

- 첫 실행에서 OfficeCLI 쪽 변환기 결함 5건이 드러났다. 고친 뒤 결과를 지우고 다시 실행했다(보고서 §10).
  - batch 결과가 stdout에 바로 담기는 경우를 놓침
  - PPTX 병합 셀의 열 계산
  - 공통 연결 규칙 누락
  - 블록 sdt 안 문단
  - 여러 문단 셀 · 머리글·바닥글 필드
- 채점 결과 평탄화 버그(합성 문서 지표가 빈 값으로 기록됨)를 고쳤다.
- 성능 측정에서는 네트워크 감시를 끄도록 했다. 감시를 켜면 폴링 비용 때문에 호출당 시간이 늘어났다.
