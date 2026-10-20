# E04 예비 실험 — Upstage Document Parse 첫 호출 (P-02)

> E04 예비 (preflight) — E04 본 실험 아님. P-02 1개 문서·1회 호출. 전체 문서 정확도로 일반화하지 않는다. 직접 파서 비교는 미측정

## 1. 호출

- 입력: P-02 (합성 문서, 3쪽, SHA-256 `cf9de77765ddf04a…`)
- 결과: SUCCESS, HTTP 200, 처리시간 7.904s (네트워크 포함), 호출 1회, 재시도 0회
- 요청 옵션: `{"model": "document-parse", "mode": "standard", "ocr": "auto", "output_formats": "[\"html\", \"markdown\", \"text\"]", "coordinates": "true"}`
- 응답 모델: `document-parse-260930`, api 2.0, 과금 페이지 {'pages': 3, 'standard': [1, 2, 3]}
- 추정 비용: $0.03 (VAT 별도), VAT 포함 $0.033 — upstage.ai/pricing 공개 단가 (2026-10-20 조회). 실제 청구 금액은 콘솔 확인 전 미확인

## 2. 응답 구조

- 요소 14개: {'caption': 2, 'paragraph': 2, 'heading1': 1, 'table': 3, 'footer': 6}
- 표 요소: 3개 / 문서 전체 형식: {'html': True, 'markdown': True, 'text': True} / 요소별 형식: {'html': 14, 'markdown': 14, 'text': 14}
- 좌표: 요소별 4점(x, y), 페이지 크기 대비 비율 (0~1), 좌상단 원점으로 보임 — 공식 문서에 단위 명시 없음 (모든 요소 제공 = True)

## 3. E03 정답 대조

| 블록 | 정답 유형 | 기대 출현 | 검출 | API 분류 | bbox IoU |
|---|---|---|---|---|---|
| CS2-b01 | heading | 1 | 1 | ['caption'] | [0.796] |
| CS2-b02 | paragraph | 1 | 1 | ['paragraph'] | [0.711] |
| CS2-b03 | paragraph | 1 | 1 | ['paragraph'] | [0.71] |
| CS2-b04 | footer | 3 | 3 | ['footer'] | [0.674, 0.689, 0.669] |

| 표 캡션 | 검출 | API 분류 |
|---|---|---|
| CS2-T1 | True | ['heading1'] |
| CS2-T2 | True | ['caption'] |

| 표 조각 | 쪽 | API 요소 | 행(API/정답) | 열(API/정답) | 셀 일치 | 표 bbox IoU |
|---|---|---|---|---|---|---|
| CS2-T1#0 | 1 | 3 | 14/14 | 6/6 | 79/79 | 0.993 |
| CS2-T1#1 | 2 | 6 | 10/10 | 6/6 | 55/55 | 0.988 |
| CS2-T2#0 | 3 | 11 | 17/17 | 7/7 | 114/114 | 0.991 |

- 전체 셀: {'numerator': 248, 'denominator': 248, 'rate': 1.0, 'status': 'PASS'}
- 헤더 셀: {'numerator': 23, 'denominator': 23, 'rate': 1.0, 'status': 'PASS'}
- 병합 셀(span): {'numerator': 15, 'denominator': 15, 'rate': 1.0, 'status': 'PASS'}
- 제품·자재 코드: {'numerator': 35, 'denominator': 35, 'rate': 1.0, 'status': 'PASS'}
- 값 `due_date`: 20/20 (PASS)
- 값 `inventory_value_krw`: 10/10 (PASS)
- 값 `on_hand_qty`: 15/15 (PASS)
- 값 `order_id`: 20/20 (PASS)
- 값 `order_qty`: 20/20 (PASS)
- 값 `unit_cost`: 10/10 (PASS)

- 페이지 넘김 표: {'truth': 'CS2-T1이 1쪽(데이터 12행)과 2쪽(데이터 8행)으로 나뉘고 2쪽에서 헤더 2행 반복', 'api_elements_for_fragments': [3, 6], 'api_merged_into_one_table': False, 'explicit_continuation_field': False, 'repeated_header_recognized_in_fragment2': True, 'request_option': 'merge_multipage_tables 기본값(false)으로 요청 — 병합 기능(베타)은 시험하지 않음'}
- 원본 위치: {'coordinates': '제공됨 (요소 단위 bbox)', 'cell_level_coordinates': '제공 안 됨 (표 HTML에 셀 좌표 없음)', 'table_bbox_iou_threshold': 0.5, 'table_bbox_iou': {'CS2-T1#0': 0.993, 'CS2-T1#1': 0.988, 'CS2-T2#0': 0.991}}

## 4. 미비교

- direct_parser_comparison: 직접 파서(pypdf·pdfplumber 등) 실측 없음 → 미측정
- accuracy_generalization: 1개 문서 결과로 일반화하지 않음
- enhanced_mode: 호출하지 않음

## 5. 응답 보안 검사

- {'api_key_in_response': False, 'home_path_in_response': False, 'email_like_in_response': False, 'extra_top_level_fields': []}
