# E03 직접 파서 실패·미측정·오류 사례

> scripts/e03_run_parsers.py가 채점 결과로 자동 생성.

## 1. 실행 실패·미측정 조합

- 없음

## 2. 지표별 불일치 (분모 대비 미달)

- **pypdf × P-01**: text.block.exact 3/4; text.block.fine_location 0/4; text.caption.fine_location 0/2; table_detection.recall 0/2; cells.text 0/64 (IR에 표 구조 없음 (표 미검출·파서 미지원)); cells.header_text 0/16 (IR에 표 구조 없음 (표 미검출·파서 미지원)); cells.merge_spans 0/8 (IR에 표 구조 없음 (표 미검출·파서 미지원)); cells.fine_location 0/64 (IR에 표 구조 없음 (표 미검출·파서 미지원)); values.id 0/8; values.quantity 0/8; values.unit 0/8; reading_order.matched_elements 3/5
  - 블록 불일치: block CS1-b03 (단위 1) — 공백 무시 포함 여부 True
- **pypdf × P-02**: text.block.fine_location 0/6; text.caption.fine_location 0/2; table_detection.recall 0/3; cells.text 0/248 (IR에 표 구조 없음 (표 미검출·파서 미지원)); cells.header_text 0/23 (IR에 표 구조 없음 (표 미검출·파서 미지원)); cells.merge_spans 0/15 (IR에 표 구조 없음 (표 미검출·파서 미지원)); cells.fine_location 0/248 (IR에 표 구조 없음 (표 미검출·파서 미지원)); values.id 0/20; values.quantity 0/35; values.money 0/20; values.unit 0/35; values.date 0/20; reading_order.matched_elements 3/5; linkage.recall 0/1; linkage.repeated_header 0/1

## 3. 머리말·꼬리말의 쪽·슬라이드 안 위치 (읽기 순서 채점에서 제외한 요소의 관찰값)

- python-docx × D-01 CS1-b02 (단위 header): 1번째 / 1개 요소
- python-docx × D-02 CS2-b04 (단위 footer): 1번째 / 1개 요소
- python-pptx × T-02 CS1-b02 (단위 (1, 'slide')): 2번째 / 2개 요소
- pypdf × P-01 CS1-b02 (단위 1): 1번째 / 72개 요소
- pypdf × P-02 CS2-b04 (단위 1): 1번째 / 84개 요소
- pypdf × P-02 CS2-b04 (단위 2): 1번째 / 58개 요소
- pypdf × P-02 CS2-b04 (단위 3): 1번째 / 117개 요소
- pdfplumber × P-01 CS1-b02 (단위 1): 1번째 / 9개 요소
- pdfplumber × P-02 CS2-b04 (단위 1): 5번째 / 6개 요소
- pdfplumber × P-02 CS2-b04 (단위 2): 3번째 / 4개 요소
- pdfplumber × P-02 CS2-b04 (단위 3): 3번째 / 4개 요소

## 4. 파서가 보고한 지원 범위 밖 정보 (IR diagnostics)

- pypdf × P-01: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
- pypdf × P-02: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
- pdfplumber × P-01: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph
- pdfplumber × P-02: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph

## 5. 분모 0 (미측정) 지표

- python-docx × D-01: values.money, values.date, linkage.recall, linkage.precision, linkage.repeated_header
- python-docx × D-02: values.block_qty_unit, linkage.recall, linkage.precision, linkage.repeated_header
- python-pptx × T-01: values.id, values.unit, values.block_qty_unit
- python-pptx × T-02: values.money, values.date, linkage.recall, linkage.precision, linkage.repeated_header
- pypdf × P-01: table_detection.precision, values.money, values.date, linkage.recall, linkage.precision, linkage.repeated_header
- pypdf × P-02: table_detection.precision, values.block_qty_unit, linkage.precision
- pdfplumber × P-01: values.money, values.date, linkage.recall, linkage.precision, linkage.repeated_header
- pdfplumber × P-02: values.block_qty_unit
