# 실패·미측정 — external_dev_v2

> 자동 생성. 텍스트 내용은 쓰지 않는다 (위치·개수만). 원인 분석은 docs/e03_external_generalization_report.md

- **X-P05 × pypdf**: NOT_MEASURED — 정답 없음
- **X-P05 × pdfplumber**: NOT_MEASURED — 정답 없음
- **X-DV-P01 × pypdf**: table_detection.recall 0/1; structure.rows_cols_equal 0/1; cells.text_loose_grid 0/372; cells.text_strict_grid 0/372; cells.text_loose_bbox_aligned 0/372; cells.cell_bbox_iou_ge_0_5 0/372; cells.column_header_text 0/12; cells.column_header_flag 0/12
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC2275741_table_0 (쪽 4): 정답 [31, 12] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-DV-P01 × pdfplumber**: cells.text_loose_grid 370/372; cells.text_strict_grid 370/372; cells.text_loose_bbox_aligned 340/372; cells.cell_bbox_iou_ge_0_5 340/372; cells.column_header_text 10/12; cells.column_header_flag 11/12; 잘못된 병합 1
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph / EXT-UNSUPPORTED: 괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔
- **X-DV-P02 × pypdf**: table_detection.recall 0/2; structure.rows_cols_equal 0/2; cells.text_loose_grid 0/120; cells.text_strict_grid 0/120; cells.text_loose_bbox_aligned 0/120; cells.cell_bbox_iou_ge_0_5 0/120; cells.column_header_text 0/10; cells.column_header_flag 0/10
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC3170591_table_0 (쪽 3): 정답 [12, 6] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC3170591_table_1 (쪽 4): 정답 [12, 4] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph / EXT-UNSUPPORTED: 괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔
- **X-DV-P03 × pypdf**: table_detection.recall 0/4; structure.rows_cols_equal 0/4; cells.text_loose_grid 0/191; cells.text_strict_grid 0/191; cells.text_loose_bbox_aligned 0/191; cells.cell_bbox_iou_ge_0_5 0/191; cells.merge_spans 0/14; cells.column_header_text 0/28; cells.column_header_flag 0/28; cells.projected_row_header 0/2; cells.text_found_ignoring_structure 188/191
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC3554437_table_0 (쪽 3): 정답 [8, 10] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC3554437_table_1 (쪽 3): 정답 [16, 5] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC3554437_table_2 (쪽 7): 정답 [5, 4] / 출력 None / IoU None / 그 쪽 출력 표 0개
  - 표 PMC3554437_table_3 (쪽 8): 정답 [9, 8] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-DV-P03 × pdfplumber**: structure.rows_cols_equal 3/4; cells.text_loose_grid 177/191; cells.text_strict_grid 150/191; cells.text_loose_bbox_aligned 169/191; cells.cell_bbox_iou_ge_0_5 172/191; cells.merge_spans 5/14; cells.column_header_text 21/28; cells.column_header_flag 24/28; cells.text_found_ignoring_structure 188/191; 잘못된 병합 1
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph / EXT-UNSUPPORTED: 괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔
  - 표 PMC3554437_table_1 (쪽 3): 정답 [16, 5] / 출력 [14, 5] / IoU 0.995 / 그 쪽 출력 표 2개
- **X-DV-P04 × pypdf**: table_detection.recall 0/1; structure.rows_cols_equal 0/1; cells.text_loose_grid 0/47; cells.text_strict_grid 0/47; cells.text_loose_bbox_aligned 0/47; cells.cell_bbox_iou_ge_0_5 0/47; cells.merge_spans 0/6; cells.column_header_text 0/7; cells.column_header_flag 0/7
  - 파서 진단: EXT-UNSUPPORTED: pypdf는 표 구조(행·열·병합) 추출 기능이 없음 — 표 셀 텍스트는 줄 텍스트에 섞여 나옴 / EXT-UNSUPPORTED: pypdf extract_text는 텍스트 좌표(bbox)를 주지 않음 — 위치는 page·줄 순번만 / EXT-UNSUPPORTED: 문단 구분 정보 없음 — 줄 단위 블록 (여러 줄 문단은 나뉨)
  - 표 PMC4695698_table_0 (쪽 1): 정답 [9, 6] / 출력 None / IoU None / 그 쪽 출력 표 0개
- **X-DV-P04 × pdfplumber**: cells.text_loose_bbox_aligned 44/47; cells.cell_bbox_iou_ge_0_5 44/47; cells.merge_spans 2/6
  - 파서 진단: EXT-UNSUPPORTED: 블록 유형(제목·캡션·머리말 등)은 구분하지 않음 — 모두 paragraph / EXT-UNSUPPORTED: 괘선 없는 표 영역 추정 규칙은 줄바꿈된 셀을 여러 행으로 나눔
