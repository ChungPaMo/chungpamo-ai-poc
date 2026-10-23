# E12 OfficeCLI 파싱 비교 보고 — 기술 선정 사전 PoC

> 작성 2026-10-23. 상태 **COMPLETED** — 검토 완료(2026-10-23). **기술 판단: 보류** (사용자 결정). 정량 합격선 미정. 실험 완료가 채택을 뜻하지 않는다.
> 계획: [e12_officecli_comparison_plan.md](e12_officecli_comparison_plan.md).
> 수치 원본: `results/E12_officecli/` — `results.json`(문서별), `summary.json`(분할별 집계), `examples.json`(실제 사례), `run_meta.json`, `outputs/synthetic/`(합성 문서 IR).
> 외부 문서 출력·사례는 공개 문서 본문이 들어 있어 `data/raw/e12_officecli/`에만 둔다(Git 제외, D-025).

## 1. 요약

**의견: 기존 파서를 유지하고 OfficeCLI는 보류한다(교체 권고 없음).**
- 합성 정답과 holdout에서 OfficeCLI가 기존 파서보다 정확했던 지표는 없다.
- 기존 파서가 못 하는 일을 OfficeCLI가 해낸 경우는 하나다. 수식 캐시값이 없는 XLSX에서 자체 계산 엔진으로 값을 낸다.
- 반면 다음이 확인됐다:
  - DOCX 콘텐츠 컨트롤·필드와 PPTX SmartArt에서 텍스트를 놓친다.
  - 문서당 처리 시간이 4.4~9.5배 길다.
  - 서명되지 않은 실행 파일이다.
  - `batch`가 읽기 명령만 보내도 파일을 다시 쓴다.

| 형식 | 셀 텍스트 | 병합 셀 | 처리시간 (3회 중앙값, 프로세스 포함) | 피크 메모리 | ERP 연계 |
|---|---|---|---|---|---|
| XLSX | X12-01: openpyxl 83/83 = OfficeCLI 83/83<br>캐시 없는 X12-02: openpyxl **76/83**, OfficeCLI **83/83** (computedValue)<br>E02 업체 파일 두 도구 일치 445/445, 532/532 | 4/4 = 4/4, 오탐 0<br>E02 9 = 9 | openpyxl 0.55~0.56 s (파싱만 0.17~0.18 s)<br>OfficeCLI 2.43~2.47 s (호출 2회) → 약 4.4배 | 47.8~48.5 MB<br>51.8~54.0 MB | openpyxl은 Python 값(int·datetime)을 바로 준다. OfficeCLI는 모든 값이 JSON 문자열이라 형 변환 단계가 하나 더 필요하다. 셀 경로(`/Orders/C3`)는 출처 위치로 바로 쓸 수 있다 |
| DOCX | 합성: v2 305/305 = 305/305<br>holdout 엄격 격자: 54/54 = 54/54<br>holdout 본문 문단: v2 69/69, OfficeCLI **67/69**<br>dev 셀: v2 17/17, OfficeCLI **15/17** | 합성 18/18 = 18/18<br>holdout 2/2 = 2/2 | v2 0.36~0.37 s (파싱만 0.006~0.019 s)<br>OfficeCLI 2.77~3.54 s → 7.7~9.5배 | 39.2~45.9 MB<br>57.9~79.2 MB | 위치 정보는 둘 다 있다 (v2 body_index·row·col, OfficeCLI `/body/tbl[1]/tr[3]/tc[4]`). 값 해석(수량·단위)은 둘 다 하지 않는다 → E05·E10 단계는 그대로 필요하다 |
| PPTX | 합성: 126/126 = 126/126<br>holdout: 58/58 = 58/58<br>holdout SmartArt: v2 19/19, OfficeCLI **0/19** | 합성 15/15 = 15/15 | v2 0.37~0.39 s<br>OfficeCLI 2.71~3.11 s → 7.3~8.3배 | 40.9~43.7 MB<br>58.6~67.5 MB | 같음. 표 조각 연결은 두 도구 모두 기능이 없고 공통 후처리 규칙으로 처리한다 |
| PDF | **NOT_SUPPORTED** — 비교하지 않음 | — | — | — | 기존 pdfplumber v2 유지 |

## 2. 도구 조사

| 항목 | 확인 결과 | 근거 |
|---|---|---|
| 배포·설치 | .NET self-contained 단일 exe (`officecli-win-x64.exe`). Windows 10에서 설치 없이 실행된다 | GitHub Release v1.0.157 |
| 출처 확인 | sha256 `bd64eba5…0557e343`. Release의 `SHA256SUMS`·GitHub API digest와 일치한다. **Authenticode 서명 없음** | 다운로드 후 확인. 실행 때마다 `e12_run.py`가 해시를 다시 확인한다 |
| 읽기 명령 | `get <경로> --depth N`, `query <선택자>`, `view`, `batch`(여러 명령), `raw`(원시 XML), `dump` | `--help`, 탐색 실행 |
| JSON 출력 | `--json`. 노드마다 `path`·`type`·`text`·`format`·`children`이 있다. batch 결과는 크면 사용자 임시 폴더 파일(`outputFile`)에, 작으면 stdout(`data.results`)에 담긴다 | 실행 확인 |
| 기능 범위 | XLSX: 값·형식·수식·cachedValue·**computedValue**·숫자 형식·병합·숨김<br>DOCX: 표(colspan·vmerge 원시값)·sdt·각주·머리글·바닥글<br>PPTX: 도형·그룹·표(colspan·rowspan·hmerge·vmerge)·차트(제목·계열·범주·데이터 레이블)·노트 | 실행 확인 |
| 미지원 | PDF 읽기 (`view pdf`는 내보내기). SmartArt 노드 텍스트 (get·view에 없음, raw XML로만 접근) | §6 |
| 로컬 동작 | 문서 처리는 로컬에서 끝난다. 실행 중 원격 TCP 연결: 감시 대상 13개 문서에서 **0** | `results.json` network |
| 네트워크 | 소스(UpdateChecker.cs)에 업데이트 확인 코드가 있다. 24시간마다 배포 서버·GitHub에 접속한다. `OFFICECLI_SKIP_UPDATE=1`이면 건너뛴다 (이 실험은 항상 설정) | 소스 확인 |
| 라이선스·비용 | Apache-2.0, 무료. 유료 API·가입 없음 | 저장소 LICENSE |

- 감시 한계: 3 ms 간격 폴링이므로 그보다 짧은 연결은 놓칠 수 있다.
- 환경변수를 설정하지 않은 상태의 통신은 측정하지 않았다(미측정).

## 3. 데이터·정답·채점

- 같은 원본, 같은 정답, 같은 채점기를 썼다. OfficeCLI 출력은 `scripts/e12_officecli.py`가 IR 0.2로 바꾼 뒤 E03 채점기(`e03_grade_parsers`, `e03_grade_external`)에 넣었다.
  - 변환 비용은 문서당 0.0002~0.0007 s이고, 처리시간과 따로 기록했다.
- 정답 상태:
  - X12와 E03 합성 문서는 생성 정답이다(GENERATED).
  - 외부 문서는 **잠정 정답**이다(PROVISIONAL, 사람 검수 없음). 공식 정답으로 쓰지 않았다.
- 분할: holdout 7개가 일반화 판단의 주 근거다. blind8·dev 10개는 v2 개발에 썼으므로 참고용이다. 표에서 따로 적는다.
- XLSX 날짜 인식 판정:
  - openpyxl은 `is_date`를 쓴다.
  - OfficeCLI는 numberformat에 날짜 형식 문자가 있고 값이 맞으면 인정했다. 이 판정 기준은 이 실험에서 정한 것이다.

## 4. XLSX 결과 (`summary.json` xlsx)

| 지표 | X12-01 openpyxl | X12-01 OfficeCLI | X12-02 openpyxl | X12-02 OfficeCLI (computed) | X12-02 OfficeCLI (cachedValue만) |
|---|---|---|---|---|---|
| 셀 값 | 83/83 | 83/83 | **76/83** | **83/83** | 76/83 |
| 수식 문자열 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| 문자열 숫자 "30" 보존 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| 날짜 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| 빈 셀 유지 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| 잘못된 값 "1O50" 보존 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| 병합 (오탐) | 4/4 (0) | 4/4 (0) | 4/4 (0) | 4/4 (0) | 4/4 (0) |
| 숨긴 행·열 | 1/1, 1/1 | 1/1, 1/1 | 1/1, 1/1 | 1/1, 1/1 | 1/1, 1/1 |

- X12-02에서 openpyxl이 틀린 7셀은 모두 수식 셀이다: Orders F2·F3·F4·F5·F8, Products C5·C6. 파일에 남은 캐시값 0을 그대로 읽었기 때문이다.
- OfficeCLI의 computedValue는 7셀 모두 정답과 같았다. 여기에는 텍스트 숫자 곱 `"30"*95000`, `#VALUE!`, 다른 시트 참조가 포함된다.
- 이 결과는 수식 8개에 대한 것이다. OfficeCLI 계산 엔진이 Excel과 같게 계산하는지는 일반적으로 검증하지 않았다.
- E02 업체 파일(정답 없음)에서는 두 도구의 값과 병합이 모두 같았다: vendor_a 445/445 셀, vendor_b 532/532 셀, 병합 9 = 9.

## 5. DOCX·PPTX 결과 (`summary.json` synthetic·external)

| 묶음 (정답 상태) | 지표 | E03 v2 | OfficeCLI |
|---|---|---|---|
| 합성 4개 (GENERATED) | 셀 텍스트 / 머리글 셀 / 병합 / 위치 | 431/431 / 67/67 / 33/33 / 431/431 | 431/431 / 67/67 / 33/33 / 431/431 |
| | 블록·캡션 / 표 탐지 / 읽기 순서 / 표 조각 연결 | 14/14·8/8 / 9/9 / 40/40 / 1/1 | 같음 |
| **holdout 7개** (PROVISIONAL) | 표 탐지·구조 / 셀 (엄격 격자) / 병합 | 17/17·17/17 / 112/112 / 2/2 | 17/17·17/17 / 112/112 / 2/2 |
| | 본문 문단 정확 / 본문 글자 재현율 | 69/69 / 6314/6314 | **67/69 / 6250/6314** |
| | 각주 / 머리글·바닥글 | 1/1 / 2/2 | 1/1 / 2/2 |
| | 도형 텍스트 / 도형 위치 / 차트 텍스트 | 11/11 / 11/11 / 12/12 | 11/11 / 11/11 / 12/12 |
| | SmartArt 노드 텍스트 | 19/19 | **0/19** |
| blind8 4개 (참고) | 본문 문단 / SmartArt / 셀·병합 | 86/86 / 11/11 / 80/80·11/11 | 85/86 / **0/11** / 80/80·11/11 |
| dev 6개 (참고) | 본문 문단 / 표 탐지 / 셀 / SmartArt | 35/35 / 8/8 / 23/23 / 2/2 | 32/35 / **7/8** / **21/23** / **0/2** |

- holdout에서 차이가 난 문서는 X-HO-D01·X-HO-D03(인라인 sdt)과 X-HO-T03(SmartArt)이다.
- 나머지 4개 문서는 모든 지표가 같았다.

## 6. OfficeCLI 미지원·제약 (원인 확인 완료)

| 제약 | 증상 | 확인 방법 | 영향 문서 |
|---|---|---|---|
| PDF 읽기 없음 | 대상이 .docx/.xlsx/.pptx뿐 | help | PDF 전체 → NOT_SUPPORTED |
| SmartArt 텍스트 없음 | get·view에 smartart 노드만 있고 텍스트가 없다 | 원시 노드 확인 | X-HO-T03, X-T01, X-DV-T01 |
| 문단 안 콘텐츠 컨트롤(인라인 sdt) | 문단 `text`에서 sdt 텍스트가 빠진다. children에서는 sdt가 run들 **뒤에** 따로 나열되어 문단 안 원래 위치를 알 수 없다 → 순서를 복원할 수 없다 | `get /body/p[N]` 원시 노드 | X-HO-D01, X-HO-D03, X-D01, X-D03 |
| 블록 sdt 안 내용 | `get --depth 30`이 sdt 안으로 내려가지 않는다 (children 빈 목록, childCount만 있음) | 원시 노드 | `query paragraph`로 문단은 보완. 중첩 sdt는 sdt text로 대체. **sdt 안 표는 query table에도 없다** → X-D03 표 1개 누락 |
| 본문 문단 안 필드 결과 | fldSimple 결과(NUMPAGES 등)가 문단 text에서 빠진다. 머리글·바닥글은 part text에 있어 보완 가능 | 원시 노드 | X-D04 |
| soft hyphen | U+00AD를 그대로 준다 (v2는 제거) | 출력 비교 | X-D04 문단 1개. 후처리로 고칠 수 있는 차이 |
| 셀 text | 여러 문단 셀을 구분 없이 이어붙인다. 셀 children에 문단이 있어 보완 가능 | 원시 노드 | 변환기에서 보완함 |
| `batch` 파일 재기록 | 조회 명령만 보낸 batch도 임시 복사본을 다시 쓴다: 21/21 문서. 단일 get·query 호출은 다시 쓰지 않았다 | 실행 전후 복사본 해시 | 원본에 직접 쓰면 원본이 바뀐다 (§9) |

## 7. 실제 사례 (① 원본 → ② 기존 파서 → ③ OfficeCLI → ④ 비교 → ⑤ 결론)

모든 값은 `scripts/e12_examples.py`를 실행해 얻은 실제 출력이다(`results/E12_officecli/examples.json`). ⑤만 해설이다.

| ID | ① 원본 (파일 안 XML / 정답) | ② 기존 파서 | ③ OfficeCLI | ④ 비교 | ⑤ 결론 |
|---|---|---|---|---|---|
| XLSX-1 | X12-01 Orders!C3 `<c r="C3" t="s"><v>14</v></c>` / 정답 문자열 "30" | openpyxl `'30'`, data_type `s` | `text "30"`, type `SharedString` | 같음 | 둘 다 문자열로 보존 |
| XLSX-2 | X12-02 Orders!F2 `<f>C2*E2</f><v>0</v>` / 정답 6000000 | `data_only=True` → `0` | cachedValue `"0"`, **computedValue `"6000000"`** | openpyxl 오답, OfficeCLI 계산값 정답 | 캐시가 없는 파일에서만 의미 있는 차이. 계산 엔진은 검증 대상 |
| XLSX-3 | `<mergeCell ref="A8:E8"/>`, BOM `A1:B1`·`C1:D1`·`E3:E4` | `merged_cells.ranges` 4개 | A8 `merge "A8:E8", mergeAnchor true`. B8 `text "(empty)", merge "A8:E8"` | 같음 | 표현 방식만 다름 |
| XLSX-4 | `<row r="5" … hidden="1">`, `<col min="9" max="9" … hidden="1"/>` | row 5 hidden True, col I hidden True | `/Orders/row[5]` hidden true. `query column` → `/Orders/col[I]` hidden true | 같음 | OfficeCLI는 열 정보에 query 1회가 더 필요 (batch에 포함) |
| XLSX-5 | F4 `<c r="F4" t="e"><f>C4*E4</f><v>#VALUE!</v></c>`, C4 "1O50" | C4 `'1O50'` (s), F4 `'#VALUE!'` | C4 SharedString "1O50". F4 type Error, cached·computed `#VALUE!` | 같음 | 잘못된 입력 판정은 어느 도구도 하지 않는다 → E05 몫 |
| DOCX-1 | D-01 표1 `<w:vMerge w:val="restart"/>` 순번, `<w:gridSpan w:val="2"/>` 구성품, 다음 행 `<w:vMerge/>` | (1,1) rowspan 2, (1,2) colspan 2, 6×6 | tc[1] `vmerge "restart"`, tc[2] `colspan 2`, 다음 행 `vmerge "continue"` → 변환 후 같은 병합, 6×6 | 같음 | OfficeCLI는 rowspan을 주지 않는다. continue를 세는 변환이 필요 |
| DOCX-2 | D-01 바닥글 `<w:fldSimple w:instr="PAGE"><w:r><w:t>1</w:t>…` | footer `"1"` | `/footer[1]` text `"1"`, 그 안 paragraph text `""` | 변환기 보완 후 같음 | 필드 결과는 part text에만 있다. 본문 문단 필드는 보완할 방법이 없다 (X-D04) |
| DOCX-3 | D-02 표1 (3,4) `<w:t>80 EA</w:t>` | `"80 EA"` (body_index 3, row 3, col 4) | `"80 EA"`, `/body/tbl[1]/tr[3]/tc[4]` | 같음 | 수량·단위 분리는 둘 다 하지 않는다 |
| PPTX-1 | T-02 슬라이드2 표 `<a:tc rowSpan="2">` 순번, `<a:tc gridSpan="2">` 구성품, `<a:tc hMerge="1">` | (1,1) rowspan 2, (1,2)·(1,4) colspan 2, 6×6 | tc[2] `colspan 2`, tc[3] `hmerge true` → 6×6 | 같음 (변환기 수정 후) | 덮인 셀도 tc로 남는다. 첫 변환 코드는 이를 잘못 세어 8열로 만들었다 (§10) |
| PPTX-2 | T-01 notesSlide `<a:t>발표자 노트: 정답셋 v2 기준…</a:t>` | speaker_notes, slide 4 | `query notes` → `/slide[4]/notes` 같은 텍스트 | 같음 | 호출 1회로 전체 노트를 받는다 |
| PPTX-3 | T-01 슬라이드 2·3 표 첫 행 머리글이 같다 (rowSpan 2, gridSpan 4) | t001 → t002, repeated_header_rows [1, 2] | 같음 (같은 공통 규칙 적용) | 같음 | 연결은 두 도구 기능이 아니라 공통 후처리 결과다 |

외부 문서 사례 4건은 `data/raw/e12_officecli/examples_external.json`에 로컬로만 둔다:
- X-HO-T03: SmartArt
- X-HO-D03: 인라인 sdt
- X-HO-D01: 바닥글 PAGE 필드
- X-D03: sdt 안 표

본문은 공개 파일에 옮기지 않았다. 증상은 §6에 있다.

## 8. 성능 (`summary.json` perf, 문서·방식별 3회)

- 측정 단위는 모두 자식 프로세스 1회다(시작 비용 포함). OfficeCLI는 문서당 2회 호출한다: `get /`, 그리고 batch.
- 실패: 13개 문서 × 2방식 × 3회 중 **0**.
- 첫 실행과 반복 중앙값의 차이는 작았다. 예: OfficeCLI D-01은 첫 실행 3.32 s, 반복 3.31 s.
  - 앞 단계에서 같은 파일을 이미 읽었으므로 OS 캐시가 데워진 상태다. 콜드 스타트는 미측정이다.
- OfficeCLI/기존 비율(전체 중앙값): **중앙값 7.8배, 범위 4.4~9.5배**.
  - 기존 파서의 프로세스 내부 파싱만 보면 DOCX·PPTX 0.006~0.027 s, XLSX 0.17~0.18 s다. 그래서 OfficeCLI와의 차이는 대부분 OfficeCLI 실행 비용이다.
- 피크 메모리: OfficeCLI가 4~33 MB 더 쓴다. 측정 범위 안의 문서는 모두 100 MB 미만이었다.
- 상주 모드나 1회 호출로 줄이는 방법은 시험하지 않았다(미측정).
- 성능 측정 중에는 네트워크 감시를 껐다. 감시를 켜면 폴링 비용 때문에 호출당 시간이 늘어난다.

## 9. 보안·운영 위험과 사고 기록

- **사고**: 탐색 단계(본 실행 전)에 Claude Code가 작성한 탐색 스크립트가 `officecli batch`를 원본 `data/documents/T-01_plan_comparison.pptx`에 **직접** 실행했다. 그 결과 원본 파일이 다시 쓰였다(해시 2ce8264f… → 019e5df3…).
  - 발견: 본 실행 시작 때 입력 해시 검사(`e03_run_parsers.verify_inputs`)가 "입력 해시 불일치 → 실험 중단"으로 멈추면서 드러났다.
  - 복구: 커밋된 blob(`git show HEAD:…`)으로 되돌렸다. 해시가 매니페스트(2ce8264f…)와 다시 같아졌고 `git status`에도 변경이 없다. 외부 문서 30개도 해시를 확인했고 불일치는 0이다.
  - 재발 방지:
    - 래퍼가 항상 임시 복사본에 실행한다.
    - batch에는 get/query만 허용한다.
    - 실행 시작과 끝에 모든 입력 해시를 다시 확인하고, 불일치하면 결과를 무효로 한다. 이번 본 실행 끝에서는 불일치 0이었다(`run_meta.json` inputs_unchanged_after_run).
- `batch`는 읽기 전용이 아니다. 조회만 해도 파일을 다시 쓴다. 본개발에서 쓴다면 원본 보관소에 직접 쓰지 말고 복사본에만 써야 한다.
  - 다시 쓴 내용의 차이는 분석하지 않았다(미측정).
- 서명되지 않은 exe다. 사내 배포 정책상 허용되는지는 팀 합의가 필요하다. 해시를 고정해 검증할 수는 있다.
- 업데이트 확인 통신은 환경변수로 끌 수 있다. 설정을 빠뜨리면 외부로 접속한다. 이때 문서 내용이 전송되는지는 소스상 업데이트 확인뿐이지만, 실측은 하지 않았다.

## 10. 공정성 — 본 실행 중 고친 OfficeCLI 변환기 결함

첫 실행의 OfficeCLI 점수에는 도구 한계가 아니라 제 변환 코드 결함이 섞여 있었다. 원시 출력을 확인해 고친 뒤 결과를 지우고 다시 실행했다. 정답·채점기·기존 파서 코드는 바꾸지 않았다.

| 결함 | 첫 실행 증상 | 수정 |
|---|---|---|
| batch 결과가 stdout에 바로 담기는 경우를 처리하지 않음 | X-T04 등 4개 문서 내용이 비고 슬라이드 수 불일치 | 파일과 stdout 둘 다 받고, 명령 수와 결과 수가 다르면 실패로 표시 |
| PPTX 병합: 앵커 뒤 colspan만큼 건너뜀 | T-01·T-02 병합 6/7·4/8, 열 수 8 | tc 하나 = 1열 |
| 공통 연결 규칙(header_repeat_rule)을 OfficeCLI IR에 빠뜨림 | T-01 연결 0/1 | v2와 같은 함수 적용 |
| 블록 sdt children이 빈 것을 그대로 둠 | X-D03 본문 14/27 | query paragraph로 보완 (→ 26/27) |
| 여러 문단 셀, 머리글·바닥글 필드 | X-D01·X-D02 셀 1개씩, X-HO-D01 바닥글 1/2 | 셀 children 문단을 줄바꿈으로 잇고, 단일 문단 part는 part text 사용 |
| 채점 결과 평탄화 (`e12_run.py`) | 합성 문서 지표가 빈 값 | grader 반환 최상위를 평탄화 |

§6의 남은 차이는 원시 출력에 정보 자체가 없거나, 위치를 알 수 없는 경우다.

## 11. 한계

- 외부 정답은 잠정 정답이다. holdout은 7개 문서로 작다.
- XLSX 시험은 합성 1개 파일(+ 캐시 없는 변형)과 E02 업체 파일 2개다. 대용량·실제 기업 XLSX는 시험하지 않았다(미측정).
- 수식 계산 엔진 검증은 수식 8개뿐이다.
- 성능은 작은 문서(5~631 KB)의 측정값이다. 대용량 확장성은 미측정이다.
- OfficeCLI 사용 방식(호출 2회, depth 30)은 이 실험에서 정한 것이다. 더 빠르거나 더 많이 얻는 사용법이 있을 수 있다.

## 12. 기술 선정 의견 (검토 필요)

| 형식 | 의견 | 이유 |
|---|---|---|
| XLSX | **보류** (현행 openpyxl 유지) | 정확도는 같고 4.4배 느리다. 장점은 수식 캐시가 없는 파일의 재계산 하나뿐이다. 그런 파일이 실제 기업 자료에 있는지 확인되면 "일부 기능에 보조 사용"(캐시 없음 감지 시 교차 확인)을 다시 검토한다 — 팀 합의 필요 |
| DOCX | **제외** (현행 E03 v2 유지) | 우위 지표가 없다. 콘텐츠 컨트롤·필드 텍스트를 놓치고 7.7~9.5배 느리다 |
| PPTX | **제외** (현행 E03 v2 유지) | SmartArt 텍스트를 지원하지 않는다(0/19). 그 밖에는 같고 7.3~8.3배 느리다 |
| PDF | 해당 없음 (NOT_SUPPORTED) | 현행 pdfplumber v2 유지 |

이 의견은 위 측정값에 근거한다. 검토 결과 2026-10-23 사용자가 **E12 OfficeCLI는 기술적으로 보류**로 정했다. 기존 파서(openpyxl, E03 v2, pdfplumber v2)와 E00~E11 결과는 그대로 유지한다. 기존 결정 기록(decisions.md)은 수정하지 않았다. 별도 결정 항목은 OfficeCLI를 다시 검토하게 될 때 추가한다.
