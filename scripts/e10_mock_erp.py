"""E10 모의 ERP 최소 검증 코드 — 업체 행 → 매핑 후보 → 검증 → staging → 승인 → 모의 ERP 반영.

완성형 ERP가 아니다. 실제 ERP에 연결하지 않으며 외부 전송 기능이 없다 (SQLite 메모리 DB 또는 로컬 파일만).
- DDL: schemas/e10_mock_erp.sql v0.2 (PRAGMA foreign_keys = ON을 연결마다 켜고 값 1을 확인한다)
- 매핑 규칙: configs/e10_mapping_rules.json v0.2, 업체 헤더·코드·형식: configs/e02_vendor_mapping.json (참조만)
- 값 검증: E05 Python 검증기(scripts/e05_validate_python.py)를 그대로 재사용 — 제안 레코드를 현재 모의 ERP 상태에 합쳐 검사
- 안전장치는 두 겹: 애플리케이션 검사(승인자·검증 오류·원본 해시·결정 상태) + DB 제약(트리거·FK·CHECK)
- 평가셋 정답은 읽지 않는다 (scripts/e10_run.py가 채점).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

import e05_dataset as D
import e05_validate_python as PY

ROOT = Path(__file__).resolve().parents[1]
DDL = (ROOT / "schemas" / "e10_mock_erp.sql").read_text(encoding="utf-8")
RULES = json.loads((ROOT / "configs" / "e10_mapping_rules.json").read_text(encoding="utf-8"))
VENDORS = json.loads((ROOT / "configs" / "e02_vendor_mapping.json").read_text(encoding="utf-8"))
E05_RULES = PY.RULES

# 모의 ERP 테이블 ↔ E01 엔터티, 업무 키
TABLES = {"UnitMaster": ("Unit", ("unit_code",)), "ProductMaster": ("Product", ("product_id",)), "MaterialMaster": ("Material", ("material_id",)),
          "SupplierMaster": ("Supplier", ("supplier_id",)), "SupplierItem": ("SupplierMaterial", ("supplier_id", "material_id")),
          "BOMHeader": ("BOM", ("bom_id",)), "BOMLine": ("BOMLine", ("bom_id", "line_no")), "SalesOrder": ("Order", ("order_id",)),
          "Inventory": ("Inventory", ("item_type", "item_id", "as_of_date")), "ProductionCapacity": ("Resource", ("resource_id",)),
          "Routing": ("Operation", ("operation_id",))}
ENT2TABLE = {e: t for t, (e, _) in TABLES.items()}
BOOL_COLS = {"outsourcing_allowed", "is_preferred", "is_active"}
INT_COLS = {"manuf_lead_time_days", "lead_time_days", "line_no", "sequence_no"}
REVIEWERS = [("SYSTEM_BOOTSTRAP", "BOOTSTRAP", 1), ("AUTO_RULE", "AUTO_RULE", 1), ("REVIEWER_A", "REVIEWER", 1), ("REVIEWER_B", "REVIEWER", 1),
             ("REVIEWER_OLD", "REVIEWER", 0)]
NAME_LOOKUP = {"product_name": ("ProductMaster", "product_id", "product_name")}   # 코드 대신 품명이 온 경우 (M-04·M-05)
BOOTSTRAP_DOC_VERSION = "2026-10-20"
AUTO_POLICY = RULES["auto_accept"]["experimental_policy_e10_v1"]
BOM_HEADER_FIELDS = {"_group", "product_id", "bom_version", "status", "is_active", "valid_from", "valid_to", "min_qty", "max_qty", "site_id", "base_qty"}
BOM_LINE_FIELDS = {"line_no", "component_type", "component_id", "qty_per", "unit", "scrap_rate"}


def table_fields(file_entity: str, table: str, fields) -> set:
    """업체 파일의 필드 후보 중 해당 모의 ERP 테이블 레코드를 만든 것."""
    if file_entity == "BOMLine":
        return set(fields) & (BOM_HEADER_FIELDS if table == "BOMHeader" else BOM_LINE_FIELDS)
    return set(fields)


def now() -> str:
    return dt.datetime(2026, 10, 21, 12, 0, 0).isoformat()      # 결정적 재현을 위해 고정 시각 (실제 시각 아님)


def h(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()


def to_db(col, v):
    if v is None:
        return None
    if col in BOOL_COLS:
        return int(bool(v))
    if col in INT_COLS:
        return int(v)
    return str(v)


def from_db(col, v):
    if v is None:
        return None
    if col in BOOL_COLS:
        return bool(v)
    if col in INT_COLS:
        return int(v)
    return v


class MockERP:
    def __init__(self, path: str = ":memory:", mapper: str = "v1", auto_policy: str | None = None):
        """mapper="v1": 1차 실행 동작 그대로 (기준선 재현용 — 같은 필드 후보를 나중 값으로 덮어씀, 실험용 자동 승인 정책).
        mapper="v2": 같은 필드 후보 충돌을 M-24 CONFLICT(ERROR)로 기록하고 값을 확정하지 않음, 비활성 BOM 대상 라인 M-25,
                     자동 승인 기본값 REVIEW_REQUIRED(auto_policy=None) — "experimental"을 명시하면 신규 주문 INSERT에만 실험 정책 적용."""
        self.mapper = mapper
        self.auto_policy = ("experimental" if mapper == "v1" else None) if auto_policy is None else (None if auto_policy == "none" else auto_policy)
        self.con = sqlite3.connect(path, isolation_level=None)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.fk_on = self.con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        if not self.fk_on:
            raise RuntimeError("foreign_keys를 켤 수 없음")
        self.con.executescript(DDL)
        self.con.executemany("INSERT INTO Reviewer VALUES (?,?,?)", REVIEWERS)
        self.cols = {t: [r[1] for r in self.con.execute(f'PRAGMA table_info("{t}")') if r[1] != "approved_by"] for t in TABLES}
        self.events = []          # 시험 관찰 기록 (거부·차단·탐지)

    # ------------------------------------------------------------ 기본 조회
    def q(self, sql, *a):
        return self.con.execute(sql, a).fetchall()

    def current(self, table, key: dict):
        _, kf = TABLES[table]
        r = self.con.execute(f'SELECT {",".join(self.cols[table])} FROM "{table}" WHERE ' + " AND ".join(f"{k} = ?" for k in kf),
                             [to_db(k, key[k]) for k in kf]).fetchone()
        return None if r is None else {c: from_db(c, v) for c, v in zip(self.cols[table], r)}

    def snapshot(self, gt) -> dict:
        """현재 모의 ERP 본 테이블 + ERP 밖 E01 엔터티(계획·판매이력) → E05 검증기 입력."""
        ents = {e: [] for e in D.ENTITY_ORDER}
        for t, (e, _) in TABLES.items():
            for r in self.con.execute(f'SELECT {",".join(self.cols[t])} FROM "{t}"'):
                rec = {c: from_db(c, v) for c, v in zip(self.cols[t], r)}
                rec["origin_class"] = "SYNTHETIC" if e != "SalesHistory" else rec.get("origin_class")
                ents[e].append(rec)
        for e in ("SalesHistory", "ProductionPlan", "ProductionPlanLine"):
            ents[e] = json.loads(json.dumps(gt["entities"][e]))
        return ents

    # ------------------------------------------------------------ 초기 적재
    def bootstrap(self, gt):
        """E01 정답셋 v2의 ERP 엔터티를 승인 기록과 함께 적재 (승인자 SYSTEM_BOOTSTRAP). 이것도 트리거를 거친다."""
        bid = "BOOTSTRAP-E01-V2"
        self.con.execute("INSERT INTO ImportBatch VALUES (?,?,?,?,?,?,?,?)", (bid, "data/canonical/ground_truth_v2.json", D.GT_SHA256, "e01_canonical",
                                                                            BOOTSTRAP_DOC_VERSION, "STAGE", now(), None))
        self.con.execute("BEGIN")
        for t, (e, kf) in TABLES.items():
            for rec in gt["entities"][e]:
                key = {k: rec[k] for k in kf}
                sid, aid = f"STG-{bid}-{t}-{h(*key.values())[:12]}", f"APR-{bid}-{t}-{h(*key.values())[:12]}"
                row = {c: rec.get(c) for c in self.cols[t]}
                self.con.execute("INSERT INTO StagingRecord VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 (sid, bid, t, json.dumps(key, ensure_ascii=False), "INSERT", None, json.dumps(row, ensure_ascii=False), "[]", 0, D.GT_SHA256, 0))
                self.con.execute("INSERT INTO ApprovalLog VALUES (?,?,?,?,?,?,?,?)", (aid, sid, None, "APPROVED", "SYSTEM_BOOTSTRAP", now(), None, None))
                self._write(t, row, aid)
                self.con.execute("UPDATE ApprovalLog SET resulting_record_id = ? WHERE approval_id = ?", (rec["record_uid"], aid))
                self.con.execute("INSERT INTO ChangeHistory VALUES (?,?,?,?,?,?,?,?)", (f"HIS-{aid}", t, json.dumps(key, ensure_ascii=False), "INSERT", None,
                                                                                         json.dumps(row, ensure_ascii=False), aid, now()))
        self.con.execute("COMMIT")

    def _write(self, table, row, approval_id, update=False):
        cols = self.cols[table]
        if update:
            _, kf = TABLES[table]
            self.con.execute(f'UPDATE "{table}" SET ' + ", ".join(f"{c} = ?" for c in cols if c not in kf) + ", approved_by = ? WHERE " +
                             " AND ".join(f"{k} = ?" for k in kf), [to_db(c, row.get(c)) for c in cols if c not in kf] + [approval_id] + [to_db(k, row[k]) for k in kf])
        else:
            self.con.execute(f'INSERT INTO "{table}" ({",".join(cols)}, approved_by) VALUES ({",".join("?" * (len(cols) + 1))})',
                             [to_db(c, row.get(c)) for c in cols] + [approval_id])

    # ------------------------------------------------------------ 매핑 (규칙 기반)
    def map_row(self, vendor: str, file: str, row: dict, row_no: int, ref: dict):
        """업체 행 1개 → 필드 후보 목록 + 레코드 제안. 해석 실패는 issue로 남기고 값을 만들지 않는다."""
        V = VENDORS["vendors"][vendor]
        fdef = next(f for f in V["files"] if f["path"] == file)
        cols = fdef["columns"]
        out, issues = {}, []

        def cand(header, field, value, method, entity, review=False, score=None, raw=None):
            prev = out.get(field)
            if self.mapper == "v2" and prev is not None and str(prev["value"]) != str(value):
                # 같은 필드에 서로 다른 후보 (예: 코드 → FG002, 품명 → FG001): 덮어쓰지 않고 충돌로 남긴다
                issues.append(("M-24", field, "ERROR", f"CONFLICT: '{prev['header']}'→{prev['value']} vs '{header}'→{value}",
                               {"candidates": [{"header": prev["header"], "value": prev["value"], "method": prev["method"]},
                                               {"header": header, "value": value, "method": method}]}))
                out[field] = {**prev, "value": None, "review": True, "conflict": True}
                return
            if self.mapper == "v2" and prev is not None:
                return                                   # 같은 값을 가리키는 두 번째 근거 — 첫 후보 유지
            out[field] = {"header": header, "field": field, "value": value, "method": method, "entity": entity, "review": review, "score": score, "raw": raw}

        types = {}
        for hname, raw in row.items():
            c = cols.get(hname)
            if c is None:
                if hname in NAME_LOOKUP:
                    table, field, name_col = NAME_LOOKUP[hname]
                    norm = lambda s: re.sub(r"\s+", "", s or "").casefold()
                    hits = sorted({r[0] for r in self.q(f'SELECT {field}, {name_col} FROM "{table}"') if norm(r[1]) == norm(raw)})
                    if not hits:
                        hits = sorted({r[0] for r in self.q(f'SELECT {field}, {name_col} FROM "{table}"') if norm(r[1]).startswith(norm(raw))})
                        if len(hits) == 1:
                            hits = []          # 접두 일치 1건은 근거가 약하므로 후보로만 두지 않는다 (명시 규칙 없음)
                    if len(hits) == 1:
                        cand(hname, field, hits[0], "RULE_NAME_EXACT", fdef["entity"], review=True, raw=raw)
                    elif len(hits) > 1:
                        cand(hname, field, None, "RULE_NAME_EXACT", fdef["entity"], review=True, raw=raw)
                        issues.append(("M-21", field, "ERROR", f"품명 '{raw}'이 여러 레코드와 일치: {hits}", {"candidates": hits}))
                    else:
                        cand(hname, field, None, "RULE_NAME_EXACT", fdef["entity"], review=True, raw=raw)
                        issues.append(("R01", field, "ERROR", f"품명 '{raw}'과 일치하는 제품 없음", {}))
                else:
                    issues.append(("M-01", hname, "WARNING", f"설정에 없는 헤더 '{hname}'", {}))
                continue
            types[c["field"]] = c
        for hname, raw in row.items():
            c = cols.get(hname)
            if c is None:
                continue
            f, t = c["field"], c["type"]
            val, err = self._convert(V, c, raw, row, cols)
            if err:
                issues.append((err[0], f, "ERROR", err[1], {"raw": raw}))
            method = "RULE_CODE_TABLE" if t in ("code", "item_code", "id_rule") else "RULE_HEADER"
            cand(hname, f, val, method, fdef["entity"], raw=raw)
        return fdef, out, issues

    def _convert(self, V, c, raw, row, cols):
        t = c["type"]
        if raw is None or raw == "":
            return None, None
        if t in ("code", "item_code"):
            kind = c.get("codes")
            if t == "item_code":
                tcol = c["type_column"]
                tval = cols[tcol]["values"].get(row.get(tcol))
                kind = {"MATERIAL": "material", "PRODUCT": "product"}.get(tval)
            table = {"product": V["codes"]["product"], "material": V["codes"]["material"], "supplier": V["codes"]["supplier"], "resource": V["codes"]["resource"]}.get(kind, {})
            if raw in table:
                return table[raw], None
            master = {"product": ("ProductMaster", "product_id"), "material": ("MaterialMaster", "material_id")}.get(kind)
            if master and self.q(f'SELECT 1 FROM "{master[0]}" WHERE {master[1]} = ?', raw):
                return raw, None                                    # M-03 사내 코드 정확 일치
            return raw, ({"product": "R01", "material": "R02", "supplier": "R03", "resource": "R05"}.get(kind, "R01"), f"코드 '{raw}'가 코드표·사내 코드에 없음")
        if t == "id_rule":
            r = V["id_rules"][c["rule"]]
            m = re.match(r["pattern"], raw)
            return (r["template"].format(n=int(m.group(1))), None) if m else (raw, ("S05", f"ID 규칙 불일치 '{raw}'"))
        if t in ("qty", "number", "price_per_unit", "ratio"):
            s = raw.replace(",", "") if V["number_format"] == "thousands" and re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", raw) else raw
            if not re.fullmatch(r"-?\d+(\.\d+)?", s):                # M-11: NaN·지수·전각·공백 거부
                return raw, ("S02", f"숫자 형식 오류 '{raw}'")
            return str(Decimal(s)), None
        if t == "int":
            return (int(raw), None) if re.fullmatch(r"\d+", raw) else (raw, ("S02", f"정수 형식 오류 '{raw}'"))
        if t == "date":
            try:
                return dt.datetime.strptime(raw, V["date_format"]).date().isoformat(), None
            except ValueError:
                return raw, ("S03", f"날짜 형식 오류 '{raw}'")
        if t == "enum":
            return (c["values"][raw], None) if raw in c["values"] else (raw, ("S04", f"허용되지 않은 값 '{raw}'"))
        if t == "unit":
            u = V["unit_labels"].get(raw, raw)
            return (u, None) if u in VENDORS["units"] else (raw, ("R07", f"단위 '{raw}' 없음"))
        if t == "bool":
            return (V["bool"][raw], None) if raw in V["bool"] else (raw, ("S02", f"불리언 형식 오류 '{raw}'"))
        return raw, None

    def proposals(self, fdef, fields):
        """필드 후보 → 모의 ERP 레코드 제안 [(table, key, record)]."""
        v = {f: x["value"] for f, x in fields.items()}
        if fdef["entity"] == "Order":
            rec = {k: v.get(k) for k in ("order_id", "product_id", "order_qty", "unit", "order_date", "due_date", "priority", "status")}
            return [("SalesOrder", rec)]
        if fdef["entity"] == "BOMLine":
            bom_id = f"BOM-{v.get('product_id')}-{v.get('bom_version')}"
            head = {"bom_id": bom_id, **{k: v.get(k) for k in ("product_id", "bom_version", "status", "is_active", "valid_from", "valid_to", "min_qty",
                                                                 "max_qty", "site_id", "base_qty")}}
            mat = v.get("component_type") == "MATERIAL"
            line = {"bom_id": bom_id, "line_no": v.get("line_no"), "component_type": v.get("component_type"),
                    "component_material_id": v.get("component_id") if mat else None, "component_product_id": None if mat else v.get("component_id"),
                    "qty_per": v.get("qty_per"), "unit": v.get("unit"), "scrap_rate": v.get("scrap_rate"), "line_type": "ITEM"}
            return [("BOMHeader", head), ("BOMLine", line)]
        raise ValueError(f"E10 1차 범위 밖 파일: {fdef['path']}")

    # ------------------------------------------------------------ 반입 (staging)
    def stage_batch(self, gt, batch: dict) -> dict:
        bid = batch["batch_id"]
        if self.q("SELECT 1 FROM ImportBatch WHERE batch_id = ?", bid):
            self.events.append({"event": "BATCH_RERUN_IGNORED", "batch_id": bid})
            return {"batch_id": bid, "reused": True, "staged": [], "auto_committed": [], "duplicates": [], "diff": []}
        prev = self.q("SELECT batch_id FROM ImportBatch WHERE source_sha256 = ? ORDER BY created_at, batch_id", batch["source_sha256"])
        self.con.execute("INSERT INTO ImportBatch VALUES (?,?,?,?,?,?,?,?)", (bid, batch["source_file"], batch["source_sha256"], "e10_rule_mapper",
                                                                            batch.get("document_version"), batch["mode"], now(), prev[-1][0] if prev else None))
        props = []
        for r in batch["rows"]:
            ref = {"source_file": batch["source_file"], "source_sha256": batch["source_sha256"], "location": {"format": "csv", "row": r["row"]}}
            fdef, fields, issues = self.map_row(batch["vendor"], batch["file"], r["cells"], r["row"], ref)
            for table, rec in self.proposals(fdef, fields):
                key = {k: rec[k] for k in TABLES[table][1]}
                tf = table_fields(fdef["entity"], table, fields)
                issue_fields = tf | ({"*"} if table != "BOMHeader" else set())
                props.append({"table": table, "key": key, "rec": rec, "row": r["row"], "issues": [i for i in issues if i[1] in issue_fields],
                              "cands": [f"CND-{bid}-{r['row']}-{f}" for f in sorted(tf)], "methods": {fields[f]["method"] for f in tf}, "ref": ref})
            for f, x in fields.items():
                table = next(t for t, _ in [("BOMHeader", 0), ("BOMLine", 0)] if f in table_fields(fdef["entity"], t, fields)) if fdef["entity"] == "BOMLine" \
                    else ENT2TABLE[fdef["entity"]]
                self.con.execute("INSERT INTO MappingCandidate VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (f"CND-{bid}-{r['row']}-{f}", bid, json.dumps(ref, ensure_ascii=False), str(x["raw"]), table, x["field"],
                                  "" if x["value"] is None else str(x["value"]), None, x["method"], x["score"], 1, "NOT_VALIDATED", int(x["review"]),
                                  h(ref["source_sha256"], json.dumps(ref["location"]), x["field"])))
        # 같은 배치 안 같은 ERP 키: 값이 같으면 중복(1건만), 다르면 충돌(M-20)
        groups = {}
        for p in props:
            groups.setdefault((p["table"], json.dumps(p["key"], sort_keys=True)), []).append(p)
        dups, kept = [], []
        for (table, _), ps in groups.items():
            first = ps[0]
            if len(ps) > 1:
                same = all(json.dumps(p["rec"], sort_keys=True, default=str) == json.dumps(first["rec"], sort_keys=True, default=str) for p in ps)
                if same:
                    dups.append({"table": table, "key": first["key"], "rows": [p["row"] for p in ps], "kind": "IN_BATCH_DUPLICATE"})
                    first["issues"].append(("S08", "*", "WARNING", f"같은 배치에 같은 레코드 {len(ps)}건 — 1건만 staging", {"rows": [p["row"] for p in ps]}))
                    kept.append(first)
                else:
                    dups.append({"table": table, "key": first["key"], "rows": [p["row"] for p in ps], "kind": "KEY_CONFLICT"})
                    for p in ps:
                        p["issues"].append(("M-20", "*", "ERROR", "같은 ERP 키에 서로 다른 값 제안", {"rows": [x["row"] for x in ps]}))
                        kept.append(p)
            else:
                kept.append(first)
        staged, auto, diff = [], [], []
        snap = self.snapshot(gt)
        for i, p in enumerate(kept):
            table, key, rec = p["table"], p["key"], p["rec"]
            statuses = ("'APPROVED'", "'PENDING'", "'HOLD'") if self.mapper == "v2" else ("'APPROVED'",)   # v2: 승인 대기 중 재반입도 중복 (v1 결함 D-4)
            if self.q("SELECT 1 FROM StagingRecord s JOIN ApprovalLog a ON a.staging_id = s.staging_id JOIN ImportBatch b ON b.batch_id = s.batch_id "
                      f"WHERE b.source_sha256 = ? AND s.target_entity = ? AND s.target_key = ? AND a.approval_status IN ({','.join(statuses)})",
                      batch["source_sha256"], table, json.dumps(key, ensure_ascii=False, default=str)):
                dups.append({"table": table, "key": key, "rows": [p["row"]], "kind": "REIMPORT_SAME_SOURCE"})
                for c in p["cands"]:
                    self.con.execute("UPDATE MappingCandidate SET validation_status = 'DUPLICATE_REIMPORT' WHERE candidate_id = ?", (c,))
                continue
            cur = self.current(table, key) if all(v is not None for v in key.values()) else None
            row = {**(cur or {}), **{k: v for k, v in rec.items()}}
            row["record_uid"] = cur["record_uid"] if cur else D.new_uid("e10", table, *map(str, key.values()))
            if cur and all(str(cur.get(k)) == str(row.get(k)) for k in self.cols[table]):
                diff.append({"table": table, "key": key, "operation": "NOOP"})
                continue
            op = "UPDATE" if cur else "INSERT"
            issues = list(p["issues"])
            issues += self._e05_issues(snap, table, row, cur)
            if op == "UPDATE" and table == "BOMHeader" and (batch.get("document_version") or "") < self._doc_version(table, key):
                issues.append(("M-15", "*", "ERROR", f"구버전 입력: 문서 버전 {batch.get('document_version')} < 반영본 {self._doc_version(table, key)}", {}))
            uniq = {}
            for it in issues:
                uniq.setdefault((it[0], it[1]), it)
            issues = list(uniq.values())
            blocking = sum(1 for it in issues if it[2] == "ERROR")
            if self.mapper == "v2" and table == "BOMLine":
                hdr = self.current("BOMHeader", {"bom_id": rec["bom_id"]}) or next((q["rec"] for q in kept if q["table"] == "BOMHeader" and q["key"]["bom_id"] == rec["bom_id"]), None)
                if hdr is not None and hdr.get("is_active") is False:
                    issues.append(("M-25", "*", "WARNING", f"비활성 BOM {rec['bom_id']}에 대한 라인 변경", {}))
            review = int(op == "UPDATE" or bool(issues) or not p["methods"] <= {"RULE_HEADER", "RULE_CODE_TABLE"} or batch["mode"] != "STAGE")
            if self.mapper == "v2" and not (self.auto_policy == "experimental" and table == "SalesOrder" and op == "INSERT"):
                review = 1                               # v2 기본: 자동 승인 정책 미확정 → REVIEW_REQUIRED
            sid = f"STG-{bid}-{i:03d}"
            d = {"staging_id": sid, "table": table, "key": key, "operation": op, "before": cur, "after": {c: row.get(c) for c in self.cols[table]},
                 "blocking": blocking, "review_required": bool(review), "issues": [{"rule_id": a, "field": b, "severity": c, "message": m} for a, b, c, m, _ in issues]}
            diff.append(d)
            if batch["mode"] == "DRY_RUN":
                continue
            self.con.execute("INSERT INTO StagingRecord VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (sid, bid, table, json.dumps(key, ensure_ascii=False, default=str), op, None if cur is None else json.dumps(cur, ensure_ascii=False, default=str),
                              json.dumps(d["after"], ensure_ascii=False, default=str), json.dumps(p["cands"]), blocking, batch["source_sha256"], review))
            for n, (rule, field, sev, msg, ev) in enumerate(issues):
                cid = next((c for c in p["cands"] if c.endswith("-" + field)), p["cands"][0] if p["cands"] else None)
                if cid:
                    code = E05_RULES[rule]["error_code"] if rule in E05_RULES else next((r.get("error_code") for r in RULES["value_rules"] if r["rule_id"] == rule), "E10")
                    self.con.execute("INSERT INTO ValidationIssue VALUES (?,?,?,?,?,?,?)", (f"ISS-{sid}-{n}", cid, rule, code, sev, msg, json.dumps(ev, ensure_ascii=False)))
            for c in p["cands"]:
                self.con.execute("UPDATE MappingCandidate SET validation_status = ? WHERE candidate_id = ?",
                                 ("SUPERSEDED_INPUT" if any(it[0] == "M-15" for it in issues) else ("FAILED" if blocking else "PASSED"), c))
            self.con.execute("INSERT INTO ApprovalLog VALUES (?,?,?,?,?,?,?,?)", (f"APR-{sid}", sid, None, "PENDING", None, None, None, None))
            staged.append(sid)
            if not review and self.auto_policy == "experimental" and AUTO_POLICY["allowed_fields"] == "*":
                res = self.approve(sid, "AUTO_RULE", batch["source_sha256"])
                if res["ok"]:
                    auto.append(sid)
        return {"batch_id": bid, "reused": False, "staged": staged, "auto_committed": auto, "duplicates": dups, "diff": diff}

    def _doc_version(self, table, key):
        r = self.q("SELECT b.document_version FROM ChangeHistory c JOIN ApprovalLog a ON a.approval_id = c.approval_id JOIN StagingRecord s ON s.staging_id = a.staging_id "
                   "JOIN ImportBatch b ON b.batch_id = s.batch_id WHERE c.target_entity = ? AND c.target_key = ? ORDER BY c.committed_at DESC, c.history_id DESC",
                   table, json.dumps(key, ensure_ascii=False, default=str))
        return (r[0][0] or "") if r else ""

    def _e05_issues(self, snap, table, row, cur):
        """제안 레코드를 현재 상태에 합쳐 E05 검증기로 검사 — 제안 레코드에 대한 보고만 가져온다 (INFO 제외)."""
        ent = TABLES[table][0]
        rec = {**({} if cur is None else cur), **row, "origin_class": "SYNTHETIC"}
        ents = {e: list(v) for e, v in snap.items()}
        ents[ent] = [r for r in ents[ent] if r.get("record_uid") != rec["record_uid"]] + [rec]
        out = []
        for r in PY.validate(ents, {"reference_date": "2026-11-15", "site_id": None}, "e10")["reports"]:
            if r["record_uid"] == rec["record_uid"] and r["severity"] != "INFO":
                out.append((r["rule_id"], r["field"] if r["field"] != "*" else "*", r["severity"], r["explanation"], {"e05_rule": r["rule_id"]}))
        return out

    # ------------------------------------------------------------ 결정
    def _check(self, sid, reviewer, current_source_sha):
        a = self.q("SELECT a.approval_status, s.blocking_issue_count, s.source_sha256, b.mode FROM ApprovalLog a JOIN StagingRecord s ON s.staging_id = a.staging_id "
                   "JOIN ImportBatch b ON b.batch_id = s.batch_id WHERE a.staging_id = ?", sid)
        if not a:
            return "NO_SUCH_STAGING"
        status, blocking, sha, mode = a[0]
        rv = self.q("SELECT role, active FROM Reviewer WHERE reviewer_code = ?", reviewer)
        if not rv or not rv[0][1] or rv[0][0] not in ("REVIEWER", "AUTO_RULE"):
            return "BAD_REVIEWER"
        if status not in ("PENDING", "HOLD"):
            return "ALREADY_DECIDED"
        if mode != "STAGE":
            return "DRY_RUN_BATCH"
        if blocking:
            return "BLOCKING_ISSUES"
        if current_source_sha is not None and current_source_sha != sha:
            return "STALE_SOURCE"
        return None

    def approve(self, sid, reviewer, current_source_sha=None, fail_after_write=False) -> dict:
        why = self._check(sid, reviewer, current_source_sha)
        if why:
            self.events.append({"event": "APPROVE_REFUSED", "staging_id": sid, "reason": why, "reviewer": reviewer})
            return {"ok": False, "reason": why}
        table, key_json, op, after_json = self.q("SELECT target_entity, target_key, operation, after_json FROM StagingRecord WHERE staging_id = ?", sid)[0]
        after, aid = json.loads(after_json), f"APR-{sid}"
        try:
            self.con.execute("BEGIN")
            self.con.execute("UPDATE ApprovalLog SET approval_status = 'APPROVED', reviewer = ?, approved_at = ? WHERE approval_id = ?", (reviewer, now(), aid))
            before = self.current(table, json.loads(key_json))
            self._write(table, after, aid, update=(op == "UPDATE"))
            if fail_after_write:
                raise RuntimeError("시험용 주입 실패 (트랜잭션 중간)")
            self.con.execute("INSERT INTO ChangeHistory VALUES (?,?,?,?,?,?,?,?)", (f"HIS-{aid}", table, key_json, op,
                                                                                     None if before is None else json.dumps(before, ensure_ascii=False, default=str),
                                                                                     after_json, aid, now()))
            self.con.execute("UPDATE ApprovalLog SET resulting_record_id = ? WHERE approval_id = ?", (after["record_uid"], aid))
            self.con.execute("COMMIT")
            return {"ok": True}
        except Exception as e:                       # 트리거·제약 위반 또는 주입 실패 → 전체 되돌림
            self.con.execute("ROLLBACK")
            self.events.append({"event": "APPROVE_ROLLED_BACK", "staging_id": sid, "reason": f"{type(e).__name__}: {e}"})
            return {"ok": False, "reason": "ROLLED_BACK", "error": f"{type(e).__name__}: {e}"}

    def decide(self, sid, reviewer, status, reason=None) -> dict:
        """반려(REJECTED) 또는 보류(HOLD)."""
        a = self.q("SELECT approval_status FROM ApprovalLog WHERE staging_id = ?", sid)
        rv = self.q("SELECT active FROM Reviewer WHERE reviewer_code = ?", reviewer)
        if not a or a[0][0] not in ("PENDING", "HOLD") or not rv or not rv[0][0]:
            self.events.append({"event": f"{status}_REFUSED", "staging_id": sid})
            return {"ok": False}
        self.con.execute("UPDATE ApprovalLog SET approval_status = ?, reviewer = ?, rejection_reason = ? WHERE staging_id = ?", (status, reviewer, reason, sid))
        return {"ok": True}

    def raw_insert_attempt(self, table, row, approval_id) -> dict:
        """애플리케이션을 거치지 않고 본 테이블에 직접 쓰기 시도 (M12) — DB 트리거가 막아야 한다."""
        try:
            self.con.execute("BEGIN")
            self._write(table, row, approval_id)
            self.con.execute("COMMIT")
            return {"blocked": False}
        except sqlite3.DatabaseError as e:
            self.con.execute("ROLLBACK")
            return {"blocked": True, "error": str(e)}

    def counts(self) -> dict:
        return {t: self.q(f'SELECT COUNT(*) FROM "{t}"')[0][0] for t in list(TABLES) + ["ChangeHistory", "ApprovalLog", "StagingRecord", "MappingCandidate", "ValidationIssue"]}
