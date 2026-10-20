# E03 외부 DOCX·PPTX 정답 사람 검수 체크리스트 (D-026 — 방식만 승인, 담당 미배정)

- 작성: 2026-10-21. **검수는 아직 수행하지 않았다.** 검수 전 정답은 PROVISIONAL 또는 NEEDS_MANUAL_REVIEW로 남는다.
- 검수 목록(위치·항목만, 텍스트 없음): `results/E03_document_parsers/external_truth_v1/manual_review_template.csv` — 523항목 (생성: `scripts/e03_external_review_template.py`)
- 대조 대상: 로컬 정답 `data/canonical/external/e03_external_truth_v1.json`(Git 제외)의 `truth_json_path` 값 ↔ 뷰어에서 본 원본 (`data/raw/external_documents/`)
- 담당: 정답 작성자 1명 + 독립 검토자 1명 (역할만 기록, 실명은 공개 저장소에 쓰지 않음 — 배정은 사용자·팀 결정)

## 1. 공식 정답과 잠정 정답 구분

| 문서 | 공식 (VERIFIED_OFFICIAL, 검수 불필요·선택 확인) | 잠정 (PROVISIONAL, 검수 대상) | 정답 없음 (NOT_MEASURED) |
|---|---|---|---|
| X-D01 kitchen-sink | 표 2개·첫 표 가로·세로 병합·둘째 표 gridCol 없음·머리말/꼬리말 부품·각주/미주 0건 (README 계약) | 본문 문단 텍스트·순서, 셀 텍스트·span | 쪽 위치 |
| X-D02 google-docs | 본문 51문단(source.md 일치), 3열 표 세로 병합 2·gridSpan 1, 각주 2, 메모 1, 삽입 1 | 본문 3문단, 셀 텍스트, 각주 텍스트, 순서 | 쪽 위치 |
| X-T01 mixed | 슬라이드 11장, SmartArt 노드 11개(diagram.test.ts), 표·차트 존재 | 도형 텍스트·그룹 경로, 표 셀, 차트 텍스트 | 논리 읽기 순서 |
| X-T02 table-merge | 다섯 표의 행·열·병합 span, 슬라이드 1의 셀 2개 | 나머지 셀 텍스트 | 읽기 순서 |
| dev·holdout DOCX·PPTX | smartart-families SmartArt 4개·접두어 규칙(README) | 그 밖 전부 | 쪽 위치·논리 읽기 순서 |
| PDF 전부 | PubTables-1M 셀 주석 | — | 본문 텍스트·읽기 순서 |
| PDF X-P02 셀 2개 | — | NEEDS_MANUAL_REVIEW (주석 텍스트와 PDF 텍스트 불일치) | — |

## 2. 우선순위

1. blind8의 DOCX·PPTX 4건 (X-D01 49, X-D02 29, X-T01 59, X-T02 40 = 177항목) — v1·v2 비교표의 † 수치를 검증된 수치로 바꾸려면 필요
2. holdout DOCX·PPTX 7건 (252항목) — v2 일반화 † 수치 검증
3. dev 6건 (94항목) — 개발용이므로 마지막
4. PDF X-P02 NEEDS_MANUAL_REVIEW 셀 2개 — PDF 뷰어에서 해당 셀 글자 확인

## 3. 항목별 확인 방법

| 항목 | 뷰어에서 확인할 것 | 판정 |
|---|---|---|
| 본문 문단 텍스트 | 문단 글자 그대로 (변경 추적은 '모두 수락' 상태로 보기) | 글자·순서 일치 → MATCH |
| 본문 읽기 순서 | 문단·표가 문서에 나오는 순서 (콘텐츠 컨트롤 안 포함) | 순서 일치 |
| 표 행·열 수 | 병합을 펼친 격자 크기 | 일치 |
| 셀 텍스트·병합 | 해당 행·열 셀의 글자, 병합 범위(span) | 둘 다 일치 |
| 머리말·꼬리말·각주·미주 | 해당 영역 글자 (쪽 번호 필드 결과는 제외 규칙 그대로) | 일치 |
| 변경 추적 | 삽입은 수락 상태 텍스트에 있고 삭제는 없는지 | 일치 |
| PPTX 도형 텍스트·그룹 경로 | 선택 창(Selection Pane)에서 도형 id·그룹 소속, 텍스트 | 둘 다 일치 |
| SmartArt 노드 | 텍스트 창(Text Pane)의 노드 글자 | 일치 |
| 차트 텍스트 | 제목·항목·계열 이름 (데이터 편집 창) | 일치 |
| 논리 읽기 순서 | 현재 정답 없음 → 검수자가 슬라이드별 순서를 새로 정의 (정의 규칙을 함께 기록) | 신규 작성 |

- 뷰어: Microsoft Word·PowerPoint 또는 LibreOffice, **읽기 전용·매크로 사용 안 함**, 저장하지 않는다 (원본 해시 유지).
- 판정 불가(UNDECIDABLE): 뷰어마다 다르게 보이거나 규칙이 애매한 경우 — 사유를 비고에 쓰고 정답 상태는 NEEDS_MANUAL_REVIEW로 둔다.

## 4. 입력란 (CSV 열)

`author`(정답 작성자 역할명), `independent_reviewer`(독립 검토자 역할명), `result(MATCH/MISMATCH/UNDECIDABLE)`, `corrected_value_ref`(불일치 시 로컬 수정안 파일의 키 — 값은 CSV에 쓰지 않음), `note`, `reviewed_at`

## 5. 검수 후 정답 갱신 절차

1. 검수 CSV를 로컬(`data/raw/external_documents/review/`)에 보관하고, 공개용에는 집계(항목 수·MATCH/MISMATCH 수)만 둔다.
2. **v1을 고치지 않고** 새 파일 `data/canonical/external/e03_external_truth_v2.json`을 만든다: MATCH 항목 → `VERIFIED_MANUAL`, MISMATCH → 검토자 합의 값으로 바꾸고 `VERIFIED_MANUAL` + 변경 사유, UNDECIDABLE → `NEEDS_MANUAL_REVIEW`.
3. 작성자와 검토자가 다르게 판정한 항목은 합의 전까지 `NEEDS_MANUAL_REVIEW`.
4. 새 정답의 SHA-256을 `external_truth_v2/truth_manifest.json`에 기록하고, 기존 평가 결과(v1 정답 기준)는 그대로 둔 채 **저장된 첫 실행 IR을 v2 정답으로 다시 채점한 결과를 별도 폴더**에 쓴다 (파서 재실행 없음).
5. 정답을 고친 이유가 파서 출력을 본 결과여서는 안 된다 — 검수자는 파서 출력이 아니라 원본 뷰어만 본다.
