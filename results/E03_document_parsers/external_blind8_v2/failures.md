# 실패·미측정 — external_blind8_v2

> 자동 생성. 텍스트 내용은 쓰지 않는다 (위치·개수만). 원인 분석은 docs/e03_external_generalization_report.md

- **X-T01 × python-pptx**: shape_char.precision 1649/2119†
- **X-P01 × pypdf**: table_detection.recall 0/2; structure.rows_cols_equal 0/2; cells.text_loose_grid 0/109; cells.text_strict_grid 0/109; cells.text_loose_bbox_aligned 0/109; cells.cell_bbox_iou_ge_0_5 0/109; cells.merge_spans 0/3; cells.column_header_text 0/6; cells.column_header_flag 0/6; cells.projected_row_header 0/3
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC2008195_table_0 (쪽 3): 정답 [30, 3] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC2008195_table_1 (쪽 5): 정답 [17, 3] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph / EXT-UNSUPPORTED: 괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔
- **X-P02 × pypdf**: table_detection.recall 0/4; structure.rows_cols_equal 0/4; cells.text_loose_grid 0/258; cells.text_strict_grid 0/258; cells.text_loose_bbox_aligned 0/258; cells.cell_bbox_iou_ge_0_5 0/258; cells.merge_spans 0/13; cells.column_header_text 0/36; cells.column_header_flag 0/36
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC2671505_table_0 (쪽 3): 정답 [8, 17] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC2671505_table_1 (쪽 4): 정답 [4, 7] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC2671505_table_2 (쪽 5): 정답 [3, 6] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC2671505_table_3 (쪽 7): 정답 [12, 8] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-P02 × pdfplumber**: table_detection.recall 3/4; table_detection.precision 3/4; structure.rows_cols_equal 2/4; cells.text_loose_grid 114/258; cells.text_strict_grid 114/258; cells.text_loose_bbox_aligned 178/258; cells.cell_bbox_iou_ge_0_5 183/258; cells.merge_spans 0/13; cells.column_header_text 13/36; cells.column_header_flag 24/36; cells.text_found_ignoring_structure 250/258; 잘못된 병합 2
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph / EXT-UNSUPPORTED: 괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔
  - 표 PMC2671505_table_0 (쪽 3): 정답 [8, 17] / 출력 [11, 15] / IoU 0.975 / 그 쪽 출력 표 1개
  - 표 PMC2671505_table_1 (쪽 4): 정답 [4, 7] / 출력 None / IoU None / 그 쪽 출력 표 1개
- **X-P03 × pypdf**: table_detection.recall 0/2; structure.rows_cols_equal 0/2; cells.text_loose_grid 0/252; cells.text_strict_grid 0/252; cells.text_loose_bbox_aligned 0/252; cells.cell_bbox_iou_ge_0_5 0/252; cells.merge_spans 0/10; cells.column_header_text 0/14; cells.column_header_flag 0/14; cells.projected_row_header 0/7
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC3296738_table_0 (쪽 4): 정답 [36, 5] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC3296738_table_1 (쪽 6): 정답 [18, 7] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-P03 × pdfplumber**: cells.text_strict_grid 248/252; cells.text_loose_bbox_aligned 5/252; cells.cell_bbox_iou_ge_0_5 5/252; cells.merge_spans 2/10; cells.column_header_flag 0/14; cells.projected_row_header 0/7
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph / EXT-UNSUPPORTED: 괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔
- **X-P04 × pypdf**: table_detection.recall 0/1; structure.rows_cols_equal 0/1; cells.text_loose_grid 0/53; cells.text_strict_grid 0/53; cells.text_loose_bbox_aligned 0/53; cells.cell_bbox_iou_ge_0_5 0/53; cells.merge_spans 0/3; cells.column_header_text 0/5; cells.column_header_flag 0/5
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC4729796_table_0 (쪽 4): 정답 [14, 4] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-P04 × pdfplumber**: table_detection.recall 0/1; structure.rows_cols_equal 0/1; cells.text_loose_grid 0/53; cells.text_strict_grid 0/53; cells.text_loose_bbox_aligned 0/53; cells.cell_bbox_iou_ge_0_5 0/53; cells.merge_spans 0/3; cells.column_header_text 0/5; cells.column_header_flag 0/5; cells.text_found_ignoring_structure 39/53
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph / EXT-UNSUPPORTED: 괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔
  - 표 PMC4729796_table_0 (쪽 4): 정답 [14, 4] / 출력 None / IoU None / 그 쪽 출력 표 0개
