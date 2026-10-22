-- E10 모의 ERP DDL v0.2 (2026-10-21). v0.1(설계 초안) → v0.2: E10 최소 검증 코드(scripts/e10_mock_erp.py)가 실제로 적재·시험하는 판.
--   v0.2 변경: Reviewer·ChangeHistory 추가, ApprovalLog에 HOLD·결정 후 변경 금지·승인자 FK, 모든 본 테이블에 승인 확인 트리거(INSERT·UPDATE).
-- 대상: SQLite 3.45 (STRICT 테이블). 모의 ERP이며 실제 기업 ERP 스키마가 아니다 (수요기업 ERP 미확인, D-036).
-- 본 테이블의 필드명·타입은 E01 모델(scripts/e01_models.py)과 docs/manufacturing_data_schema.md §3을 그대로 따른다.
-- 수량·금액은 원본 정밀도 보존을 위해 TEXT(10진 문자열)로 둔다 (E05: REAL 변환 시 판정 차이 위험).
-- 연결마다 반드시: PRAGMA foreign_keys = ON;  (SQLite 기본값 0 — E05 실측)
-- 날짜 유효성은 date(x) = x 왕복 비교로만 확인 가능 (date('2026-02-30') = '2026-03-02' — E05 실측).

-- =====================================================================
-- 1. staging 계층 (승인 이전에는 여기에만 쓴다)
-- =====================================================================

CREATE TABLE ImportBatch (
  batch_id          TEXT PRIMARY KEY,
  source_file       TEXT NOT NULL,                 -- 데이터 루트 기준 상대 경로 (사용자 경로 금지)
  source_sha256     TEXT NOT NULL CHECK (length(source_sha256) = 64),
  parser_name       TEXT NOT NULL,
  document_version  TEXT,
  mode              TEXT NOT NULL CHECK (mode IN ('DRY_RUN', 'STAGE')),
  created_at        TEXT NOT NULL,
  previous_batch_id TEXT REFERENCES ImportBatch(batch_id)
) STRICT;
CREATE INDEX ix_batch_sha ON ImportBatch(source_sha256);

CREATE TABLE MappingCandidate (
  candidate_id      TEXT PRIMARY KEY,
  batch_id          TEXT NOT NULL REFERENCES ImportBatch(batch_id),
  source_reference  TEXT NOT NULL,                 -- JSON {source_file, source_sha256, location}
  raw_value         TEXT NOT NULL,
  proposed_entity   TEXT NOT NULL CHECK (proposed_entity IN ('ProductMaster','MaterialMaster','SupplierMaster','SupplierItem','UnitMaster',
                                                             'BOMHeader','BOMLine','SalesOrder','Inventory','ProductionCapacity','Routing')),
  proposed_field    TEXT NOT NULL,
  proposed_value    TEXT NOT NULL,
  target_key        TEXT,                          -- JSON, 신규면 NULL
  matching_method   TEXT NOT NULL CHECK (matching_method IN ('RULE_CODE_TABLE','RULE_HEADER','RULE_NAME_EXACT','KEYWORD_BM25','EMBEDDING','TRI_CHEF','LLM')),
  score             REAL,                          -- 방식이 실제로 낸 점수만. 규칙 기반은 NULL
  rank              INTEGER NOT NULL CHECK (rank >= 1),
  validation_status TEXT NOT NULL DEFAULT 'NOT_VALIDATED' CHECK (validation_status IN ('NOT_VALIDATED','PASSED','FAILED','SUPERSEDED_INPUT','DUPLICATE_REIMPORT')),
  review_required   INTEGER NOT NULL CHECK (review_required IN (0, 1)),
  dedup_key         TEXT NOT NULL
) STRICT;
CREATE INDEX ix_cand_dedup ON MappingCandidate(dedup_key);

CREATE TABLE ValidationIssue (
  issue_id     TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES MappingCandidate(candidate_id),
  rule_id      TEXT NOT NULL,                      -- E05 규칙 ID 또는 E10 규칙(M-*)
  error_code   TEXT NOT NULL,
  severity     TEXT NOT NULL CHECK (severity IN ('ERROR','WARNING')),
  message      TEXT NOT NULL,
  evidence     TEXT                                -- JSON
) STRICT;

CREATE TABLE StagingRecord (
  staging_id           TEXT PRIMARY KEY,
  batch_id             TEXT NOT NULL REFERENCES ImportBatch(batch_id),
  target_entity        TEXT NOT NULL,
  target_key           TEXT NOT NULL,              -- JSON
  operation            TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE')),   -- DELETE 없음
  before_json          TEXT,                       -- INSERT면 NULL
  after_json           TEXT NOT NULL,
  candidate_ids        TEXT NOT NULL,              -- JSON 배열
  blocking_issue_count INTEGER NOT NULL DEFAULT 0 CHECK (blocking_issue_count >= 0),
  source_sha256        TEXT NOT NULL,              -- staging 시점 원본 해시 (승인 시 원본이 바뀌었는지 확인)
  review_required      INTEGER NOT NULL CHECK (review_required IN (0, 1))
) STRICT;

CREATE TABLE Reviewer (                            -- 등록된 승인자 (역할 코드만, 실명·계정 없음 — E10-ASM-02)
  reviewer_code TEXT PRIMARY KEY,
  role          TEXT NOT NULL CHECK (role IN ('REVIEWER','AUTO_RULE','BOOTSTRAP')),
  active        INTEGER NOT NULL CHECK (active IN (0, 1))
) STRICT;

CREATE TABLE ApprovalLog (
  approval_id         TEXT PRIMARY KEY,
  staging_id          TEXT NOT NULL UNIQUE REFERENCES StagingRecord(staging_id),   -- staging 1건당 결정 1건
  candidate_id        TEXT REFERENCES MappingCandidate(candidate_id),
  approval_status     TEXT NOT NULL CHECK (approval_status IN ('PENDING','APPROVED','REJECTED','HOLD')),
  reviewer            TEXT REFERENCES Reviewer(reviewer_code),   -- 자동 승인은 'AUTO_RULE'
  approved_at         TEXT,
  rejection_reason    TEXT,
  resulting_record_id TEXT,
  CHECK (approval_status = 'PENDING' OR reviewer IS NOT NULL),
  CHECK (approval_status <> 'APPROVED' OR approved_at IS NOT NULL),
  CHECK (approval_status <> 'REJECTED' OR rejection_reason IS NOT NULL)
) STRICT;

-- 검증 오류(ERROR)가 남은 staging은 승인할 수 없다 (INSERT·UPDATE 모두)
CREATE TRIGGER trg_no_approve_with_errors BEFORE INSERT ON ApprovalLog
WHEN NEW.approval_status = 'APPROVED'
 AND (SELECT blocking_issue_count FROM StagingRecord WHERE staging_id = NEW.staging_id) > 0
BEGIN SELECT RAISE(ABORT, 'E10: blocking validation issues — approval not allowed'); END;

CREATE TRIGGER trg_no_approve_with_errors_upd BEFORE UPDATE ON ApprovalLog
WHEN NEW.approval_status = 'APPROVED'
 AND (SELECT blocking_issue_count FROM StagingRecord WHERE staging_id = NEW.staging_id) > 0
BEGIN SELECT RAISE(ABORT, 'E10: blocking validation issues — approval not allowed'); END;

-- 이미 결정된(APPROVED·REJECTED) 기록은 다시 바꿀 수 없다 (승인 요청 중복, 사후 변경 방지). resulting_record_id 기록만 허용
CREATE TRIGGER trg_decision_immutable BEFORE UPDATE ON ApprovalLog
WHEN OLD.approval_status IN ('APPROVED','REJECTED')
 AND (NEW.approval_status IS NOT OLD.approval_status OR NEW.reviewer IS NOT OLD.reviewer OR NEW.approved_at IS NOT OLD.approved_at)
BEGIN SELECT RAISE(ABORT, 'E10: decision already recorded'); END;

CREATE TABLE ChangeHistory (                        -- 승인 후 반영 이력 (변경 전·후 보존)
  history_id    TEXT PRIMARY KEY,
  target_entity TEXT NOT NULL,
  target_key    TEXT NOT NULL,
  operation     TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE')),
  before_json   TEXT,
  after_json    TEXT NOT NULL,
  approval_id   TEXT NOT NULL REFERENCES ApprovalLog(approval_id),
  committed_at  TEXT NOT NULL
) STRICT;

-- =====================================================================
-- 2. 모의 ERP 본 테이블 (승인된 staging에서만 쓴다)
--    approved_by: 반영 근거 ApprovalLog.approval_id (필수). 트리거가 APPROVED 여부를 확인한다.
-- =====================================================================

CREATE TABLE UnitMaster (
  record_uid TEXT PRIMARY KEY, unit_code TEXT NOT NULL UNIQUE,
  dimension TEXT NOT NULL CHECK (dimension IN ('MASS','COUNT','TIME')),
  base_unit_code TEXT NOT NULL, to_base_factor TEXT NOT NULL,
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id)
) STRICT;

CREATE TABLE ProductMaster (
  record_uid TEXT PRIMARY KEY, product_id TEXT NOT NULL UNIQUE, product_name TEXT NOT NULL,
  product_type TEXT NOT NULL CHECK (product_type IN ('FINISHED','SEMI_FINISHED')),
  base_unit TEXT NOT NULL REFERENCES UnitMaster(unit_code), safety_stock_qty TEXT NOT NULL,
  manuf_lead_time_days INTEGER NOT NULL CHECK (manuf_lead_time_days >= 0),
  outsourcing_allowed INTEGER NOT NULL CHECK (outsourcing_allowed IN (0, 1)), outsourcing_unit_cost TEXT,
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id)
) STRICT;

CREATE TABLE MaterialMaster (
  record_uid TEXT PRIMARY KEY, material_id TEXT NOT NULL UNIQUE, material_name TEXT NOT NULL,
  base_unit TEXT NOT NULL REFERENCES UnitMaster(unit_code), unit_cost TEXT NOT NULL, safety_stock_qty TEXT NOT NULL,
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id)
) STRICT;

CREATE TABLE SupplierMaster (
  record_uid TEXT PRIMARY KEY, supplier_id TEXT NOT NULL UNIQUE, supplier_name TEXT NOT NULL,
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id)
) STRICT;

CREATE TABLE SupplierItem (                         -- E01 SupplierMaterial
  record_uid TEXT PRIMARY KEY,
  supplier_id TEXT NOT NULL REFERENCES SupplierMaster(supplier_id), material_id TEXT NOT NULL REFERENCES MaterialMaster(material_id),
  lead_time_days INTEGER NOT NULL CHECK (lead_time_days >= 0), min_order_qty TEXT, is_preferred INTEGER NOT NULL CHECK (is_preferred IN (0, 1)),
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id),
  UNIQUE (supplier_id, material_id)
) STRICT;

CREATE TABLE BOMHeader (                            -- E01 BOM
  record_uid TEXT PRIMARY KEY, bom_id TEXT NOT NULL UNIQUE, product_id TEXT NOT NULL REFERENCES ProductMaster(product_id),
  bom_version TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('DRAFT','APPROVED')), is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
  valid_from TEXT NOT NULL CHECK (date(valid_from) = valid_from), valid_to TEXT CHECK (valid_to IS NULL OR date(valid_to) = valid_to),
  min_qty TEXT NOT NULL, max_qty TEXT, site_id TEXT, base_qty TEXT NOT NULL,
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id),
  UNIQUE (product_id, bom_version),
  CHECK (NOT (is_active = 1 AND status <> 'APPROVED')),
  CHECK (valid_to IS NULL OR valid_to >= valid_from)
) STRICT;
-- 활성 버전 간 기간·수량 겹침(QR-06①)과 순환(QR-05)은 다른 행을 봐야 하므로 제약이 아니라 승인 전 검증 질의(E05 B02·B01)로 확인한다.

CREATE TABLE BOMLine (
  record_uid TEXT PRIMARY KEY, bom_id TEXT NOT NULL REFERENCES BOMHeader(bom_id), line_no INTEGER NOT NULL CHECK (line_no >= 1),
  component_type TEXT NOT NULL CHECK (component_type IN ('MATERIAL','PRODUCT')),
  component_material_id TEXT REFERENCES MaterialMaster(material_id), component_product_id TEXT REFERENCES ProductMaster(product_id),
  qty_per TEXT NOT NULL, unit TEXT NOT NULL REFERENCES UnitMaster(unit_code), scrap_rate TEXT, line_type TEXT,
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id),
  UNIQUE (bom_id, line_no),
  CHECK ((component_type = 'MATERIAL') = (component_material_id IS NOT NULL) AND (component_type = 'PRODUCT') = (component_product_id IS NOT NULL))
) STRICT;

CREATE TABLE SalesOrder (                           -- E01 Order ("Order"는 SQL 예약어라 이름만 바꿈, 필드는 같음)
  record_uid TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE, product_id TEXT NOT NULL REFERENCES ProductMaster(product_id),
  order_qty TEXT NOT NULL, unit TEXT NOT NULL REFERENCES UnitMaster(unit_code),
  order_date TEXT NOT NULL CHECK (date(order_date) = order_date), due_date TEXT NOT NULL CHECK (date(due_date) = due_date),
  priority TEXT NOT NULL CHECK (priority IN ('NORMAL','URGENT')), status TEXT NOT NULL CHECK (status IN ('OPEN','CLOSED','CANCELLED')),
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id),
  CHECK (due_date >= order_date)
) STRICT;

CREATE TABLE Inventory (
  record_uid TEXT PRIMARY KEY, item_type TEXT NOT NULL CHECK (item_type IN ('PRODUCT','MATERIAL')), item_id TEXT NOT NULL,
  as_of_date TEXT NOT NULL CHECK (date(as_of_date) = as_of_date), on_hand_qty TEXT NOT NULL, allocated_qty TEXT, on_order_qty TEXT,
  expected_receipt_date TEXT, unit TEXT NOT NULL REFERENCES UnitMaster(unit_code),
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id),
  UNIQUE (item_type, item_id, as_of_date)
) STRICT;
-- item_id는 item_type에 따라 ProductMaster 또는 MaterialMaster를 가리키는 조건부 참조라 FK로 표현하지 않는다 (승인 전 검증 질의 E05 R01·R02).

CREATE TABLE ProductionCapacity (                   -- E01 Resource (능력 단위: 시간/일)
  record_uid TEXT PRIMARY KEY, resource_id TEXT NOT NULL UNIQUE, resource_name TEXT NOT NULL,
  resource_type TEXT NOT NULL CHECK (resource_type IN ('MACHINE','LINE','WORKCENTER')),
  regular_hours_per_day TEXT NOT NULL, overtime_hours_per_day_max TEXT NOT NULL, cost_per_hour TEXT NOT NULL, overtime_cost_per_hour TEXT NOT NULL,
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id)
) STRICT;

CREATE TABLE Routing (                              -- E01 Operation
  record_uid TEXT PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE, product_id TEXT NOT NULL REFERENCES ProductMaster(product_id),
  sequence_no INTEGER NOT NULL CHECK (sequence_no >= 1), resource_id TEXT NOT NULL REFERENCES ProductionCapacity(resource_id),
  run_time_per_unit_h TEXT NOT NULL, setup_time_h TEXT NOT NULL,
  approved_by TEXT NOT NULL REFERENCES ApprovalLog(approval_id),
  UNIQUE (product_id, sequence_no)
) STRICT;

-- =====================================================================
-- 3. 승인 없는 반영 차단 — 모든 본 테이블에 INSERT·UPDATE·DELETE 트리거 (애플리케이션 검증과 별도로 DB가 한 번 더 막는다)
--    v0.2 수정(E10 시험에서 발견): 이미 쓰인 승인 기록을 재사용한 직접 UPDATE가 통과하던 문제 →
--    승인 기록이 APPROVED이고, 아직 반영에 쓰이지 않았고(resulting_record_id IS NULL), 이 테이블의 staging에 대한 것이어야 한다. UPDATE는 새 승인을 요구한다.
-- =====================================================================
CREATE TRIGGER trg_unitmaster_insert_requires_approval BEFORE INSERT ON UnitMaster
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'UnitMaster' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_unitmaster_update_requires_approval BEFORE UPDATE ON UnitMaster
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'UnitMaster' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_unitmaster_no_delete BEFORE DELETE ON UnitMaster BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_productmaster_insert_requires_approval BEFORE INSERT ON ProductMaster
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'ProductMaster' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_productmaster_update_requires_approval BEFORE UPDATE ON ProductMaster
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'ProductMaster' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_productmaster_no_delete BEFORE DELETE ON ProductMaster BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_materialmaster_insert_requires_approval BEFORE INSERT ON MaterialMaster
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'MaterialMaster' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_materialmaster_update_requires_approval BEFORE UPDATE ON MaterialMaster
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'MaterialMaster' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_materialmaster_no_delete BEFORE DELETE ON MaterialMaster BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_suppliermaster_insert_requires_approval BEFORE INSERT ON SupplierMaster
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'SupplierMaster' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_suppliermaster_update_requires_approval BEFORE UPDATE ON SupplierMaster
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'SupplierMaster' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_suppliermaster_no_delete BEFORE DELETE ON SupplierMaster BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_supplieritem_insert_requires_approval BEFORE INSERT ON SupplierItem
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'SupplierItem' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_supplieritem_update_requires_approval BEFORE UPDATE ON SupplierItem
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'SupplierItem' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_supplieritem_no_delete BEFORE DELETE ON SupplierItem BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_bomheader_insert_requires_approval BEFORE INSERT ON BOMHeader
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'BOMHeader' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_bomheader_update_requires_approval BEFORE UPDATE ON BOMHeader
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'BOMHeader' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_bomheader_no_delete BEFORE DELETE ON BOMHeader BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_bomline_insert_requires_approval BEFORE INSERT ON BOMLine
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'BOMLine' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_bomline_update_requires_approval BEFORE UPDATE ON BOMLine
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'BOMLine' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_bomline_no_delete BEFORE DELETE ON BOMLine BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_salesorder_insert_requires_approval BEFORE INSERT ON SalesOrder
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'SalesOrder' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_salesorder_update_requires_approval BEFORE UPDATE ON SalesOrder
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'SalesOrder' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_salesorder_no_delete BEFORE DELETE ON SalesOrder BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_inventory_insert_requires_approval BEFORE INSERT ON Inventory
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'Inventory' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_inventory_update_requires_approval BEFORE UPDATE ON Inventory
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'Inventory' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_inventory_no_delete BEFORE DELETE ON Inventory BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_productioncapacity_insert_requires_approval BEFORE INSERT ON ProductionCapacity
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'ProductionCapacity' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_productioncapacity_update_requires_approval BEFORE UPDATE ON ProductionCapacity
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'ProductionCapacity' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_productioncapacity_no_delete BEFORE DELETE ON ProductionCapacity BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;

CREATE TRIGGER trg_routing_insert_requires_approval BEFORE INSERT ON Routing
WHEN (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'Routing' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_routing_update_requires_approval BEFORE UPDATE ON Routing
WHEN NEW.approved_by IS OLD.approved_by OR (SELECT a.approval_status = 'APPROVED' AND a.resulting_record_id IS NULL AND s.target_entity = 'Routing' FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id WHERE a.approval_id = NEW.approved_by) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'E10: not approved — staging only'); END;

CREATE TRIGGER trg_routing_no_delete BEFORE DELETE ON Routing BEGIN SELECT RAISE(ABORT, 'E10: delete not allowed'); END;
