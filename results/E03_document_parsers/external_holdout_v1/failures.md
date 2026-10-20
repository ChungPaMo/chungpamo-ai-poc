# 실패·미측정 — external_holdout_v1

> 자동 생성. 텍스트 내용은 쓰지 않는다 (위치·개수만). 원인 분석은 docs/e03_external_generalization_report.md

- **X-HO-P01 × pypdf**: table_detection.recall 0/1; structure.rows_cols_equal 0/1; cells.text_loose_grid 0/53; cells.text_strict_grid 0/53; cells.text_loose_bbox_aligned 0/53; cells.cell_bbox_iou_ge_0_5 0/53; cells.merge_spans 0/2; cells.column_header_text 0/4; cells.column_header_flag 0/4; cells.projected_row_header 0/1
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC2396182_table_0 (쪽 3): 정답 [19, 3] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-HO-P01 × pdfplumber**: table_detection.recall 0/1; table_detection.precision 0/1; structure.rows_cols_equal 0/1; cells.text_loose_grid 0/53; cells.text_strict_grid 0/53; cells.text_loose_bbox_aligned 0/53; cells.cell_bbox_iou_ge_0_5 0/53; cells.merge_spans 0/2; cells.column_header_text 0/4; cells.column_header_flag 0/4; cells.projected_row_header 0/1
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph
  - 표 PMC2396182_table_0 (쪽 3): 정답 [19, 3] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-HO-P02 × pypdf**: table_detection.recall 0/1; structure.rows_cols_equal 0/1; cells.text_loose_grid 0/27; cells.text_strict_grid 0/27; cells.text_loose_bbox_aligned 0/27; cells.cell_bbox_iou_ge_0_5 0/27; cells.merge_spans 0/2; cells.column_header_text 0/4; cells.column_header_flag 0/4
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC3465174_table_0 (쪽 3): 정답 [11, 3] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-HO-P02 × pdfplumber**: table_detection.recall 0/1; table_detection.precision 0/4; structure.rows_cols_equal 0/1; cells.text_loose_grid 0/27; cells.text_strict_grid 0/27; cells.text_loose_bbox_aligned 0/27; cells.cell_bbox_iou_ge_0_5 0/27; cells.merge_spans 0/2; cells.column_header_text 0/4; cells.column_header_flag 0/4
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph
  - 표 PMC3465174_table_0 (쪽 3): 정답 [11, 3] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-HO-P03 × pypdf**: table_detection.recall 0/2; structure.rows_cols_equal 0/2; cells.text_loose_grid 0/225; cells.text_strict_grid 0/225; cells.text_loose_bbox_aligned 0/225; cells.cell_bbox_iou_ge_0_5 0/225; cells.merge_spans 0/7; cells.column_header_text 0/13; cells.column_header_flag 0/13; cells.projected_row_header 0/3
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC3700768_table_0 (쪽 2): 정답 [11, 2] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC3700768_table_1 (쪽 4): 정답 [26, 9] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-HO-P03 × pdfplumber**: table_detection.recall 0/2; structure.rows_cols_equal 0/2; cells.text_loose_grid 0/225; cells.text_strict_grid 0/225; cells.text_loose_bbox_aligned 0/225; cells.cell_bbox_iou_ge_0_5 0/225; cells.merge_spans 0/7; cells.column_header_text 0/13; cells.column_header_flag 0/13; cells.projected_row_header 0/3
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph
  - 표 PMC3700768_table_0 (쪽 2): 정답 [11, 2] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC3700768_table_1 (쪽 4): 정답 [26, 9] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-HO-P04 × pypdf**: table_detection.recall 0/2; structure.rows_cols_equal 0/2; cells.text_loose_grid 0/371; cells.text_strict_grid 0/371; cells.text_loose_bbox_aligned 0/371; cells.cell_bbox_iou_ge_0_5 0/371; cells.merge_spans 0/19; cells.column_header_text 0/35; cells.column_header_flag 0/35; cells.projected_row_header 0/7
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC4828818_table_0 (쪽 4): 정답 [21, 11] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC4828818_table_1 (쪽 10): 정답 [16, 15] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-HO-P04 × pdfplumber**: table_detection.recall 0/2; structure.rows_cols_equal 0/2; cells.text_loose_grid 0/371; cells.text_strict_grid 0/371; cells.text_loose_bbox_aligned 0/371; cells.cell_bbox_iou_ge_0_5 0/371; cells.merge_spans 0/19; cells.column_header_text 0/35; cells.column_header_flag 0/35; cells.projected_row_header 0/7
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph
  - 표 PMC4828818_table_0 (쪽 4): 정답 [21, 11] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC4828818_table_1 (쪽 10): 정답 [16, 15] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-HO-D01 × python-docx**: PARSER_FAILED — 파서 출력 없음 (실행 실패) / 오류 ["AttributeError: 'NoneType' object has no attribute 'name' @ ['e03_ext_parse_doc.py:46:main', 'doc_docx.py:104:parse_docx']"]
- **X-HO-D03 × python-docx**: body_paragraph_exact 5/6†; body_char.recall 384/404†; reading_order.matched_elements 6/7†
- **X-HO-T03 × python-pptx**: smartart_node_text_found 0/19†
- **X-HO-T04 × python-pptx**: chart_text_found 0/12†
