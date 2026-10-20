# E04 후속 실험 계획 — 직접 파서 vs Upstage Document Parse (설계안, 구현 없음)

- 작성일: 2026-10-20. E04 상태 `NOT_STARTED` (예비 호출 1회만 수행 — `results/E04_upstage_preflight/`)
- 스캔 PDF·OCR은 사용자 결정에 따라 **후순위** (DEC-20261020-10). 이 계획의 1차 범위는 텍스트형 PDF.
- 관련: [experiment_plan.md](experiment_plan.md) E04, [evaluation_protocol.md](evaluation_protocol.md) §10, [intermediate_representation.md](intermediate_representation.md) 0.2

## 0. 예비 호출에서 확인한 사실 (P-02 1건, 일반화 금지)

| 항목 | 실측 |
|---|---|
| 모델·모드 | `document-parse-260930`, standard, HTTP 200, 1회, 7.9초 |
| 과금 | 3쪽 (standard [1,2,3]). 실제 청구액 미확인 — 공개 단가 기준 추정 $0.03 (VAT 별도) |
| 표 | 조각 3개 검출, 셀 248/248, 병합 15/15, 표 영역 IoU 0.988~0.993 |
| 한계 | 요소 유형 분류 불일치(제목→caption, 표 캡션→heading1/caption), 쪽 넘김 표 연결 정보 없음(기본값 `merge_multipage_tables=false`), Markdown은 병합 구조 손실(HTML만 보존), 셀 단위 좌표 없음(요소 단위만), 직접 파서 비교 미측정 |

## 1. 비교 설계

| 비교 | 대상 문서 | 방식 | 지표 (protocol §3, §10) |
|---|---|---|---|
| A. 직접 파서 vs Upstage Standard | P-01, P-02 (로컬 보관본) + E03 파서 비교와 같은 PDF | 직접 파서(후보: pypdf, pdfplumber — 설치 승인 필요) 결과와 Upstage 결과를 같은 공통 IR(0.2)로 바꿔 같은 채점기로 비교 | 표 검출 재현율·정밀도, 셀 일치율, 병합 보존, 블록 순서, 값 보존, 위치(IoU) |
| B. HTML vs Markdown 구조 보존 | A와 같은 응답 | 같은 응답의 HTML·Markdown을 각각 표 격자로 복원 | 병합 영역 보존율(span 일치), 셀 일치율, 헤더 행 식별 |
| C. 쪽 넘김 표 연결 | P-02 | `merge_multipage_tables=true` 1회 vs 기존(false) 결과 | 논리 표 1개로 합쳐지는가, 반복 헤더 처리(중복 행 삽입 여부), 행 순서 |
| D. Enhanced 필요성 | 조건 충족 문서만 (§3) | standard vs enhanced 같은 문서 | 위 지표 + 쪽당 비용 3배 대비 개선 여부 |

- 같은 문서·같은 정답(E03 명세)·같은 채점기를 쓴다. 직접 파서 결과가 없으면 A는 `미측정`.
- 요소 유형 분류는 정답의 블록 유형과의 대응표(예: heading↔heading1/caption)를 미리 정하고, 분류 일치율을 별도 지표로 둔다.

## 2. `merge_multipage_tables` 공식 정보 (2026-10-20 API Reference 조회)

- 베타(Beta), boolean, 기본값 `false`. 설명: "When set to `true`, tables spanning multiple pages will be combined into one cohesive table structure."
- 지원 모드·모델·제약은 **문서에 명시 없음** → 호출 전 확인할 질문: standard에서도 동작하는가, 반복 헤더를 제거하는가, 과금 변화가 있는가. 확인 전에는 결과를 기능 보장으로 해석하지 않는다.
- 셀 단위 좌표: 문서에 언급 없음. `words=true`(단어 단위 OCR 결과·좌표, 응답 크기 증가 경고)로 단어 좌표를 받을 수 있다고 되어 있으나 텍스트형 PDF에서의 동작은 미확인.

## 3. Enhanced 비교가 필요한 조건 (모두 충족 시에만 제안)

1. Standard 결과에서 표 구조 오류(셀 불일치·병합 손실·표 미검출)가 실제로 관측됨
2. 해당 문서 유형이 MVP에서 처리해야 하는 유형임 (복잡한 표, 이미지·차트 포함)
3. 비용 상한 안에서 실행 가능 (enhanced 공개 단가 $0.03/쪽, standard의 3배)
- 현재(P-02 1건)는 조건 1이 관측되지 않아 Enhanced 비교 근거 없음.

## 4. 비용·호출 상한 (제안 — 사용자 승인 필요)

| 항목 | 제안 상한 |
|---|---|
| 문서당 호출 | 설정 조합당 1회 (자동 재시도 없음, 실패 시 승인 후 재호출) |
| 1차 본 실험 총 호출 | 10회 이하 |
| 1차 본 실험 총 쪽수 | 30쪽 이하 (standard 기준 추정 $0.30, VAT 별도) |
| Enhanced | 조건 §3 충족 문서만, 10쪽 이하 |
- 실행마다 호출 기록(문서 해시·옵션·HTTP 상태·과금 쪽수)을 남기고, 실제 청구액은 콘솔에서 확인해 별도 기록한다.
- 전송 대상: 합성·공개 문서만. 실기업 문서 금지.

## 5. Upstage 출력 → 공통 IR(0.2) 변환 방안

| Upstage 응답 | 공통 IR 0.2 |
|---|---|
| `model`, `api`, `usage` | `parser` (name·version·mode·api_calls), 과금 쪽수 |
| `elements[]` (category ≠ table) | `blocks[]` — `type`은 대응표로 변환, 원래 category는 `format_specific` 보존, `order`=응답 순서 |
| `elements[]` (category = table) `content.html` | `tables[]` — HTML 파싱으로 `cells[]`(row·col·rowspan·colspan·text) 생성. Markdown은 보조 |
| `coordinates` (4점, 0~1 비율) | `location.bbox` = 비율 × 페이지 크기(pt), top-left 원점, `bbox_unit=pt`. 원본 비율값은 `format_specific` 보존 |
| `page` | `location.page` |
| 표 조각 | 위치·헤더 반복으로 `logical_table_id`·`fragment_index` 추정 (API가 연결 정보를 주지 않으므로 '추정'으로 표시) |
| 응답 원문 | Git 제외 경로(`data/raw/...`)에만 보관, IR에는 SHA-256만 |

## 6. 보안

- API 키는 `.env`에서만 읽고 출력·저장하지 않는다 (`src/config/settings.py`, `tests/test_env_config.py`).
- 응답 원문·요청 헤더는 커밋하지 않는다. 공개 결과에는 집계 지표만.
- 실패 시 사용자 승인 없이 재호출하지 않는다.

## 7. 미결정 (사용자·팀)

- E04 본 실험 착수 승인, 호출·비용 상한 (§4)
- 직접 PDF 파서 설치 승인 (pypdf, pdfplumber / PyMuPDF는 D-018)
- `merge_multipage_tables` 시험 여부
- 요소 유형 대응표 확정
