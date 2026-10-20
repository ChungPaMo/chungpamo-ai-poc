# E03 결과 요약 — 1단계-b 문서 샘플 생성·독립 검증

> 자동 생성. 상태 **RUNNING**. 실행 2026-10-20T14:40:28+09:00, 기준 커밋 `5587f80fa5e39965b927bd5a706dc72078a5da70`

- 1단계(설계·정답 명세) 산출물은 보존: `data/canonical/e03_document_truth_v1.json` (SHA-256 `982af3be…`, 변경 없음)
- 텍스트 블록 수 정정: 텍스트 블록 13→11 (1단계 보고 오기 정정, 명세 파일은 불변)
- 제외: scan_pdf: S-01·S-02 생성 보류 (OCR 우선순위 제외, 설계·명세는 보존); hwp_hwpx: 생성·변환·파싱 안 함 (미측정); ocr: 설치·실험 안 함; upstage_api: 호출 안 함; parser_comparison: 시작 안 함

## 1. 생성 문서

| 문서 | 형식 | 내용 | 크기(byte) | SHA-256 | 생성(s) | PASS | FAIL | 미측정 | 수동검수 필요 | 뷰어 검수 |
|---|---|---|---|---|---|---|---|---|---|---|
| D-01 | docx | CS1 | 38,911 | `4e6e9c7707442688…` | 0.1022 | 12 | 0 | 1 | 1 | 미검수 |
| D-02 | docx | CS2 | 39,298 | `3211c39ee3925144…` | 0.4478 | 12 | 0 | 1 | 1 | 미검수 |
| P-01 | pdf_text | CS1 | 33,045 | `27cff01a4c876628…` | 0.0123 | 13 | 0 | 0 | 1 | 미검수 |
| P-02 | pdf_text | CS2 | 45,577 | `cf9de77765ddf04a…` | 0.0164 | 13 | 0 | 0 | 1 | 미검수 |
| T-01 | pptx | CS3 | 37,885 | `2ce8264fc778d659…` | 0.0467 | 13 | 0 | 0 | 1 | 미검수 |
| T-02 | pptx | CS1 | 31,950 | `7ff3ec3f477d0862…` | 0.0402 | 12 | 0 | 1 | 1 | 미검수 |

## 2. 검증 항목별 결과

| 항목 | D-01 | D-02 | P-01 | P-02 | T-01 | T-02 |
|---|---|---|---|---|---|---|
| 1_package_format | PASS | PASS | PASS | PASS | PASS | PASS |
| 2_not_corrupted | PASS | PASS | PASS | PASS | PASS | PASS |
| 3_text_blocks | PASS 4/4 | PASS 4/4 | PASS 4/4 | PASS 4/4 | PASS 3/3 | PASS 3/3 |
| 4_text_order | PASS | PASS | PASS | PASS | PASS | PASS |
| 5_table_count | PASS 2/2 | PASS 2/2 | PASS 2/2 | PASS 3/3 | PASS 3/3 | PASS 2/2 |
| 6_cell_count | PASS 64/64 | PASS 241/241 | PASS 64/64 | PASS 248/248 | PASS 62/62 | PASS 64/64 |
| 7_merged_cells | PASS 8/8 | PASS 10/10 | PASS 8/8 | PASS 15/15 | PASS 7/7 | PASS 8/8 |
| 8_numbers_units_dates | PASS 16/16 | PASS 95/95 | PASS 16/16 | PASS 95/95 | PASS 31/31 | PASS 16/16 |
| 9_canonical_refs | PASS 16/16 | PASS 95/95 | PASS 16/16 | PASS 95/95 | PASS 31/31 | PASS 16/16 |
| 10_source_location | PASS 6/6 | PASS 6/6 | PASS 68/68 | PASS 254/254 | PASS 6/6 | PASS 5/5 |
| 11_multi_page_slide | NOT_MEASURED | NOT_MEASURED | PASS | PASS | PASS | PASS |
| 12_header_footer_notes | PASS 2/2 | PASS 2/2 | PASS 1/1 | PASS 1/1 | PASS | NOT_MEASURED |
| 13_visual_layout | NEEDS_MANUAL_REVIEW | NEEDS_MANUAL_REVIEW | NEEDS_MANUAL_REVIEW | NEEDS_MANUAL_REVIEW | NEEDS_MANUAL_REVIEW | NEEDS_MANUAL_REVIEW |
| 14_metadata_privacy | PASS | PASS | PASS | PASS | PASS | PASS |

- PDF 텍스트 레이어: 자체 최소 디코더(ToUnicode)로 모든 셀·블록 텍스트를 해독해 확인. **외부 PDF 파서의 추출 정확도는 아님** (E03 파서 비교 단계)
- 원본 위치: 생성 기록 위치를 저장된 파일 내부(OOXML 요소 순번·도형 ID, PDF 콘텐츠 스트림 좌표)와 대조한 결과. **파서가 추출한 위치의 정확도는 미측정**
- 13_visual_layout: 뷰어 미검수 → 모두 NEEDS_MANUAL_REVIEW

## 3. 재현성

- 바이트 단위: 전 파일 일치 (7개 파일)
- 구조 단위: {'run1_eq_run2': True, 'project_eq_rerun': True, 'basis': '독립 검증 결과(항목별 상태·분자·분모)'}
- 내용 단위: {'run1_eq_run2': True, 'project_eq_rerun': True, 'basis': '생성 위치 메타데이터 전체(블록·표 조각·셀 위치·도형 ID) + 검증기의 텍스트·셀 대조'}
- 고정 방법: OOXML: zip 항목 시각·core.xml 시각 고정(e01_common.normalize_xlsx), 문서 속성 고정 / PDF: reportlab invariant=1(생성 시각·문서 ID 고정)

## 4. 테스트

- pytest: {'total': 76, 'passed': 75, 'failed': 1, 'errors': 0, 'skipped': 0}
- 실패 테스트: ['tests/test_e01_dataset.py::test_regeneration_is_byte_identical']
- **회귀(E01)**: tests/test_e01_dataset.py::test_regeneration_is_byte_identical — 이번 단계에서 설치한 lxml 때문에 openpyxl이 xlsx XML을 lxml로 기록하게 되어(openpyxl.xml.LXML=True), E01 생성기가 다시 만든 xlsx 4개의 내부 XML 바이트가 커밋된 E01 파일과 달라짐
  - 근거: 셀 값은 4개 파일 모두 동일. 환경변수 OPENPYXL_LXML=False로 실행하면 E01 재생성 산출물 31개가 커밋본과 바이트 일치
  - 조치: 수정하지 않음 (E00~E02 코드 변경 금지 지시)
  - 수정 방안: E01 생성 코드에서 openpyxl import 전에 OPENPYXL_LXML=False 지정 (E01 코드 변경 — 승인 필요)
  - 수정 방안: tests/conftest.py에서 테스트 환경 고정 (테스트 인프라 변경 — 승인 필요)
  - 수정 방안: E01 바이트 기준을 lxml 기록 결과로 다시 만들기 (E01 산출물 변경 — 비권장)

## 5. 패키지

- {'python-docx': '1.2.0', 'reportlab': '5.0.1', 'python-pptx': '1.0.2', 'lxml': '6.1.3', 'pillow': '13.0.0', 'xlsxwriter': '3.2.9', 'charset-normalizer': '3.5.2'}
