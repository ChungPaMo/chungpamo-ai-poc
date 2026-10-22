# E10 데이터 계약 — 파서 출력 → ERP 매핑 후보 → 검증 → 승인

> 작성 2026-10-21 (계약 v0.1 초안, **미구현**). 공통 IR 0.2([intermediate_representation.md](intermediate_representation.md))의 구조·버전은 바꾸지 않는다. 이 계약은 IR **다음 단계**(ERP 매핑)에서만 쓰는 별도 형식이다. 기존 파서 출력은 변경하지 않는다.
> DDL 대응: [schemas/e10_mock_erp.sql](../schemas/e10_mock_erp.sql)

## 0. 설계 원칙

| 원칙 | 계약상 구현 |
|---|---|
| 파싱과 ERP 필드 매핑 분리 | 파서는 IR만 낸다. 매핑 입력은 IR의 `extracted_values`·`records`에서 만든다 (`MappingInput`) |
| 후보 탐색과 값 검증 분리 | `MappingCandidate.validation_status`는 후보 생성기가 아니라 공통 검증 단계가 채운다 |
| 값 검증과 저장 승인 분리 | 검증 통과(`PASSED`)여도 `ApprovalLog`에 `APPROVED`가 없으면 본 테이블 반영 불가 |
| 동일 원본 재반입 시 중복 방지 | `ImportBatch.source_sha256` + `source_reference`가 같은 후보는 같은 `dedup_key` → 이미 반영된 키는 신규 생성 금지 |
| 구버전 데이터 처리 | `document_version`·BOM `bom_version`·유효기간을 비교해 기존보다 오래된 버전은 `SUPERSEDED_INPUT`으로 표시, 덮어쓰기 금지 |
| 원본 위치 추적 | 모든 후보는 IR `location`을 그대로 담은 `source_reference`를 가진다. 반영 레코드 → `ApprovalLog.resulting_record_id` → 후보 → 원본 위치 |
| dry-run 변경 전후 비교 | `ImportBatch.mode = DRY_RUN`이면 `StagingRecord.before/after`만 만들고 승인 단계로 가지 않는다 |
| 실제 ERP 직접 쓰기 금지 | 반영 대상은 모의 ERP(SQLite)뿐. 실제 ERP 연결 정보 필드를 두지 않는다 |
| 신뢰도 | `score`는 해당 방식이 실제로 산출한 점수가 있을 때만 채운다. 없으면 null + `review_flag`. **추정 신뢰도를 만들지 않는다** |

## 1. 입력 — MappingInput

IR 값 1개(또는 레코드 셀 1개)당 1건.

| 필드 | 타입 | 필수 | 출처 (IR 0.2) |
|---|---|---|---|
| input_id | string | 필수 | `{batch_id}:{순번}` |
| source_file | string | 필수 | `document.source_file` (데이터 루트 기준 상대 경로, 사용자 경로 금지) |
| source_sha256 | string (64 hex) | 필수 | `document.sha256` |
| location | object | 필수 | IR §3 형식별 위치 그대로 (`page`/`sheet`/`row`/`col`/`cell_ref`/`bbox` 등) |
| extracted_field | string \| null | 선택 | `extracted_values[].field` (파서가 해석한 필드명, 없으면 null) |
| raw_value | string | 필수 | `extracted_values[].raw` 또는 `records[].source.cells[field].raw` |
| normalized_value | string \| null | 선택 | `extracted_values[].value` (정규화 실패 시 null) |
| unit | string \| null | 선택 | `unit` (원문 단위는 `unit_raw`) |
| unit_raw | string \| null | 선택 | `unit_raw` |
| document_version | string \| null | 선택 | 문서에서 추출한 `doc_version` 값 (없으면 null) |
| parser_name | string | 필수 | `parser.name` + `parser.version` |
| extraction_confidence | number \| null | 선택 | **파서·OCR·API가 실제로 낸 점수만** (현재 IR 0.2 출력에는 없음 → null) |
| review_flag | string[] | 필수 | 파서 진단에서 옮긴 플래그 (예: `EXT-TABLE-LOST`, `ERR-NUMFMT`), 없으면 [] |

## 2. 매핑 후보 — MappingCandidate

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| candidate_id | string | 필수 | `{batch_id}:{input_id}:{method}:{순번}` |
| batch_id | string | 필수 | ImportBatch |
| source_reference | object | 필수 | `{source_file, source_sha256, location}` (MappingInput에서 복사) |
| proposed_entity | enum | 필수 | ProductMaster, MaterialMaster, SupplierMaster, SupplierItem, UnitMaster, BOMHeader, BOMLine, SalesOrder(E01 Order — SQL 예약어 회피로 테이블명만 다름), Inventory, ProductionCapacity, Routing |
| proposed_field | string | 필수 | E01 필드명 (예: `qty_per`) |
| proposed_value | string | 필수 | 모의 ERP 기준 단위·형식으로 바꾼 값 (변환 전 값은 MappingInput.raw_value) |
| target_key | object \| null | 선택 | 대상 레코드 키 (예: `{"bom_id": "BOM-FG001-V1", "line_no": 2}`). 신규면 null |
| matching_method | enum | 필수 | RULE_CODE_TABLE, RULE_HEADER, RULE_NAME_EXACT, KEYWORD_BM25, EMBEDDING, TRI_CHEF, LLM |
| score | number \| null | 선택 | 방식이 실제로 낸 점수 (BM25 점수·유사도 등). 규칙 기반은 null |
| rank | integer | 필수 | 같은 입력에 대한 후보 순위 (1부터) |
| validation_status | enum | 필수 | NOT_VALIDATED, PASSED, FAILED, SUPERSEDED_INPUT |
| validation_errors | ValidationIssue[] | 필수 | §3 |
| review_required | boolean | 필수 | §5 자동 승인 조건을 하나라도 못 맞추면 true |
| dedup_key | string | 필수 | `sha256(source_sha256 + location + proposed_entity + proposed_field)` |

## 3. 검증 오류 — ValidationIssue

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| issue_id | string | 필수 | — |
| candidate_id | string | 필수 | — |
| rule_id | string | 필수 | E05 규칙 ID(S01~V12) 또는 E10 규칙(`M-*`, `configs/e10_mapping_rules.json`) |
| error_code | string | 필수 | evaluation_protocol §2.4 오류 코드 |
| severity | enum | 필수 | ERROR, WARNING |
| message | string | 필수 | — |
| evidence | object | 선택 | 비교 대상 값·기존 레코드 키 등 |

## 4. 승인 대기·승인 결과

### 4.1 StagingRecord

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| staging_id | string | 필수 | — |
| batch_id | string | 필수 | — |
| target_entity | enum | 필수 | §2 proposed_entity와 같음 |
| target_key | object | 필수 | 반영 대상 키 |
| operation | enum | 필수 | INSERT, UPDATE (DELETE 없음) |
| before | object \| null | 필수 | 현재 본 테이블 값 (INSERT면 null) |
| after | object | 필수 | 반영안 |
| candidate_ids | string[] | 필수 | 근거 후보 |
| blocking_issue_count | integer | 필수 | ERROR 검증 오류 수 (> 0이면 승인 불가) |

### 4.2 ApprovalLog (승인 결과)

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| approval_id | string | 필수 | — |
| candidate_id | string | 필수 | 요청 계약 필드 (레코드 단위 승인은 staging_id로 묶음) |
| staging_id | string | 필수 | — |
| approval_status | enum | 필수 | PENDING, APPROVED, REJECTED |
| reviewer | string \| null | APPROVED·REJECTED일 때 필수 | 역할 코드 (E10-ASM-02, 실명 금지) |
| approved_at | string (ISO 8601) \| null | APPROVED일 때 필수 | — |
| rejection_reason | string \| null | REJECTED일 때 필수 | — |
| resulting_record_id | string \| null | APPROVED이고 반영됐을 때 필수 | 본 테이블 레코드의 record_uid |

**규칙**: `reviewer`가 없거나 `approval_status ≠ APPROVED`인 데이터는 모의 ERP 본 테이블에 반영되지 않는다. `blocking_issue_count > 0`인 staging은 APPROVED로 바꿀 수 없다 (DDL 트리거 초안).

## 5. 자동 승인(auto-accept) 후보 조건 — 초안

다음을 **모두** 만족할 때만 `review_required = false`. 그래도 사전 PoC에서는 자동 승인도 ApprovalLog에 `reviewer = "AUTO_RULE"`로 남긴다.

1. matching_method = RULE_CODE_TABLE (사내 코드 대응표 정확 일치) 또는 원본 값이 사내 코드와 정확히 일치
2. validation_status = PASSED (ERROR 0건)
3. dedup_key가 기존 반영 기록에 없음
4. SUPERSEDED_INPUT 아님
5. 대상 필드가 자동 승인 허용 목록에 있음 (`configs/e10_mapping_rules.json` `auto_accept.allowed_fields`, 팀 합의 필요)

## 6. ImportBatch

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| batch_id | string | 필수 | — |
| source_file, source_sha256 | string | 필수 | — |
| parser_name | string | 필수 | — |
| document_version | string \| null | 선택 | — |
| mode | enum | 필수 | DRY_RUN, STAGE |
| created_at | string (ISO 8601) | 필수 | — |
| previous_batch_id | string \| null | 선택 | 같은 sha256의 이전 반입 (재반입 탐지) |

## 7. 미확정

- 실제 ERP의 엔터티·필드·키 (D-036) — 확인되면 계약의 `proposed_entity`·필드 목록을 실제 ERP 기준으로 다시 정한다.
- 승인 절차(1인/2인 승인, 승인 권한) — 도메인·KPI 담당 현업 조사 후 확정.
- 자동 승인 허용 필드와 점수 기준 — 팀 합의 필요.
