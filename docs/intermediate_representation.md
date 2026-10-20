# 문서 파싱 공통 중간 JSON 표현 (E02~E04) — 설계안

- 작성일: 2026-10-20 (설계안, **E03·E04 미구현**)
- 대상 형식 (전체 파싱 검증 범위 확정): **CSV, XLSX, DOCX, PDF, HWP, HWPX, PPTX**
- 목적: 형식이 달라도 같은 채점기·같은 지표([evaluation_protocol.md](evaluation_protocol.md) §3, §10)로 비교할 수 있게, 파서 출력을 하나의 표현으로 맞춘다. 형식별 고유 정보(페이지 좌표, 슬라이드 도형, HWP 문단·컨트롤 등)는 버리지 않고 `location`과 `format_specific`에 보존한다.
- E02 1차 출력(`results/E02_tabular_parsing/output/`)은 이 설계 이전에 만든 표 형식 전용 구조다. E02 구현 범위는 넓히지 않으며, 이 표현으로의 변환은 E03 착수 시 검토한다(§6).

## 1. 최상위 구조

```json
{
  "schema": "chungpamo.parse_ir", "schema_version": "0.1",
  "document": {...},          // 원본 파일 메타데이터
  "parser": {...},            // 사용한 파서·버전·옵션
  "blocks": [...],            // 텍스트 블록 (읽기 순서)
  "tables": [...],            // 표 구조 (셀 단위)
  "extracted_values": [...],  // 업무 필드로 해석한 값 (정규화 전/후)
  "records": [...],           // 공통 데이터 모델 레코드 (표 형식 입력·표에서 만든 레코드)
  "diagnostics": [...],       // 입력 오류·추출 실패·경고
  "format_specific": {...}    // 형식 고유 정보 (손실 방지용 원자료)
}
```

## 2. 구성 요소

### 2.1 document

| 필드 | 설명 |
|---|---|
| `source_file` | 데이터 루트 기준 상대 경로 (사용자 경로 금지) |
| `format` | `csv` / `xlsx` / `docx` / `pdf` / `hwp` / `hwpx` / `pptx` |
| `sha256`, `bytes` | 원본 무결성 |
| `encoding` | 텍스트 형식만 (예: `cp949`, `utf-8-sig`) |
| `units_of_division` | 형식별 분할 단위 수: `{"sheets": n}` / `{"pages": n}` / `{"sections": n}` / `{"slides": n}` |
| `is_scanned` | PDF 등에서 텍스트 레이어가 없는 스캔 문서인지 (판정 방법 기록) |
| `origin_class` | `SYNTHETIC` / `PUBLIC_REAL` 등 ([data_provenance_policy.md](data_provenance_policy.md)) |

### 2.2 parser

`{"name": "python-pptx", "version": "…", "mode": "direct" | "ocr" | "api", "options": {...}, "api_calls": n}` — 외부 API를 쓰면 호출 수와 요청 ID(비밀값 제외)를 남긴다.

### 2.3 blocks (텍스트 블록)

| 필드 | 설명 |
|---|---|
| `block_id` | 문서 안에서 유일 (`b0001`) |
| `type` | `heading` / `paragraph` / `list_item` / `caption` / `header` / `footer` / `footnote` / `slide_title` / `slide_body` / `speaker_notes` / `image_alt` / `other` |
| `order` | 파서가 판단한 읽기 순서 (0부터) |
| `text` | 추출 텍스트 (공백 정규화 전 원문) |
| `location` | §3 위치 표현 |
| `level` | 제목·목록 수준 (알 수 있는 경우) |
| `style` | 글꼴·굵게 등 (선택, 형식이 제공하는 경우만) |

### 2.4 tables (표 구조)

| 필드 | 설명 |
|---|---|
| `table_id` | 문서 안에서 유일 (`t001`) |
| `location` | 표 전체 위치 (§3) |
| `n_rows`, `n_cols` | 병합을 펼친 논리 격자 크기 |
| `header_rows` | 헤더 행 수 (파서 판단) |
| `cells` | `[{row, col, rowspan, colspan, text, raw, is_header, location}]` — 병합 영역은 앵커 셀 1개 + span으로 표현 ([evaluation_protocol.md](evaluation_protocol.md) §3.4와 같은 규칙) |
| `continuation` | 페이지·슬라이드를 넘어 이어지는 표: `{"continues_from": table_id, "continues_to": table_id, "repeated_header": bool}` (§3.5) |
| `caption_block_id` | 표 제목 블록 |
| `detection` | `native`(파일 구조에 표가 있음) / `inferred`(좌표·선으로 추정) — PDF·스캔에서 구분 |

### 2.5 extracted_values

| 필드 | 설명 |
|---|---|
| `field` | 공통 모델 필드명 (예: `product_id`, `qty_per`, `doc_version`) |
| `raw` | 원문 문자열 |
| `value` | 정규화 값 (표준 단위·ISO 날짜) |
| `unit_raw`, `unit` | 원문 단위와 표준 단위 |
| `source` | `{"block_id"}` 또는 `{"table_id", "row", "col"}` — 위치 역추적 경로 |
| `method` | `table_header_match` / `pattern` / `label_value` 등 추출 방법 |

### 2.6 records

E02의 레코드와 같은 의미: `{"entity", "values", "source": {"file", 위치…, "cells": {field: {...}}}, "field_errors"}`. 표 형식 입력(CSV/XLSX)은 records가 주 출력이고, 문서 형식은 표·추출값에서 만든 레코드를 넣는다.

### 2.7 diagnostics

`{"code", "severity": "error"|"warning", "location", "field", "message", "raw"}` — 오류 코드는 evaluation_protocol.md §2.4(ERR-*)와 추출 실패 코드(아래)를 함께 쓴다.

| 추출 실패 코드 (E03·E04용, 신규) | 의미 |
|---|---|
| `EXT-EMPTY` | 출력이 비어 있음 (스캔 PDF를 텍스트 추출한 경우 등) |
| `EXT-OPEN-FAIL` | 파일 열기 실패 (암호·배포용 HWP, 손상 등) |
| `EXT-TABLE-LOST` | 표가 있다고 알려진 위치에서 표 구조를 얻지 못함 |
| `EXT-UNSUPPORTED` | 파서가 해당 형식·요소를 지원하지 않음 |

## 3. 원본 위치(location) 표현 — 형식별

모든 위치는 `{"format": ..., ...}` 객체이며, 형식별 필드를 그대로 둔다. 좌표·번호의 기준(0/1부터)을 명시한다.

| 형식 | 필드 | 기준 |
|---|---|---|
| CSV | `row`, `col`, `column_name` | 물리 행·열 1부터 (헤더 포함) |
| XLSX | `sheet`, `row`, `col`, `cell_ref`(예: `C5`), `merged_range` | 1부터 |
| DOCX | `body_index`(본문 요소 순번), `paragraph_index`, `table_index`, `row`, `col`, `part`(`body`/`header`/`footer`/`footnotes`), `section_index` | 0부터 (python-docx 순서) |
| PDF | `page`, `bbox` [x0, y0, x1, y1], `bbox_unit`(`pt`), `bbox_origin`(`top-left`/`bottom-left`), `char_start`/`char_end`(선택) | 페이지 1부터, 좌표계는 파서마다 다르므로 반드시 기록 |
| HWP | `section`, `paragraph`, `control_index`(표·그림 컨트롤), `row`, `col`, `stream`(OLE 스트림명) | 0부터 (도구 출력 기준, 도구명 함께 기록) |
| HWPX | `section_file`(예: `Contents/section0.xml`), `xpath` 또는 `paragraph_id`, `table_index`, `row`, `col` | XML 구조 기준 |
| PPTX | `slide_index`, `slide_id`, `shape_id`, `shape_name`, `placeholder_type`, `row`, `col`(표 도형), `part`(`slide`/`notes`), `bbox`(EMU 또는 pt 변환값과 단위) | 슬라이드 1부터 |

## 4. 형식별 고유 정보 보존 (format_specific)

| 형식 | 보존할 정보 (예) |
|---|---|
| CSV | 구분자, 줄바꿈, BOM, 인코딩 판별 근거 |
| XLSX | 시트 목록, 병합 범위 전체, 셀 표시 형식(`number_format`), 숨김 행·열 |
| DOCX | 스타일 이름, 머리말·꼬리말, 각주, 변경 추적 여부 |
| PDF | 텍스트 레이어 유무, 회전, 글꼴 정보 요약, 표 추정 근거(선·좌표) |
| HWP | 문서 버전, 배포용·암호 여부, 사용한 변환 경로(직접 / HWPX 변환 / PDF 변환) |
| HWPX | 패키지 매니페스트, 섹션 파일 목록 |
| PPTX | 슬라이드 레이아웃, 도형 순서(z-order), 그룹 도형 구조, 발표자 노트 |

## 5. 원칙

1. **출력 생성과 정확 추출을 구분한다**: `diagnostics`에 `EXT-EMPTY` 등이 있으면 출력이 있어도 정확도는 따로 채점한다 (protocol §1.2).
2. **원문 보존**: `raw`·`text`는 정규화 전 원문, `value`는 정규화 후 값. 둘 다 남긴다.
3. **정답 비의존**: 파서는 정답셋을 읽지 않는다. 매핑 설정은 별도 파일로 두고 출처를 기록한다 (E02와 같은 원칙).
4. **민감정보 금지**: 위치에 사용자 경로를 쓰지 않는다. API 키·요청 헤더를 저장하지 않는다.

## 6. E02 출력과의 대응 (변환은 E03 착수 시 검토)

| E02 1차 출력 | 중간 표현 |
|---|---|
| `files[]` (인코딩·구분자·헤더 행) | `document` + `format_specific` |
| `headers[]` (병합 헤더 group/name) | `tables[].cells` 헤더 행 + `format_specific.merged_ranges` |
| `entities{}` 레코드 + `source.cells` | `records[]` (같은 구조) |
| `diagnostics[]` | `diagnostics[]` (같은 구조, `location` 객체로 정리) |

## 7. 미확정

- `bbox` 일치 판정 기준(IoU 임계값) — 팀 합의 필요 (protocol §10.3)
- HWP 위치 표현은 사용할 도구가 정해진 뒤 확정
- 스키마 검증 방법(JSON Schema 또는 pydantic) — E03 착수 시 결정
