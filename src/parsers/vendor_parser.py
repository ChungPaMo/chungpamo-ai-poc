"""E02 업체 파일 파서 (Baseline: 표준 csv + openpyxl).

업체 설정(configs/e02_vendor_mapping.json)만으로 업체 파일을 공통 레코드로 바꾼다.
정답셋 폴더의 파일은 읽지 않는다 (테스트가 정답 폴더 없이 실행해 확인).

진단 범위 (파서 단계에서 구조적으로 판단 가능한 것만):
  ERR-TABLE   헤더가 설정 열 구성과 다름 → 해당 시트·파일 파싱 중단
  ERR-MISSING 필수 열 값 비어 있음
  ERR-NUMFMT  숫자 형식 오류        ERR-DATE   날짜 형식 오류·존재하지 않는 날짜
  ERR-BADREF  코드 대응표에 없는 제품·자재·공급사 코드
  ERR-RESREL  공정(Operation)이 대응표에 없는 자원 코드를 참조
  ERR-UNIT    알 수 없는 단위 또는 품목 단위 차원과 다른 수량 단위
  ERR-DUPID   같은 파일 안에서 레코드 키 중복
  ERR-IDVER   같은 BOM 번호 행들의 헤더 값(제품·버전 등) 불일치, ID 규칙 불일치
  ERR-VALUE   허용 목록에 없는 열거값 (주입 오류 유형 밖, 발생 시 오탐으로 채점됨)
업무 규칙 오류(납기<주문일, 할당>보유, BOM 순환, BOM 버전 유효조건 중복)는 E05 검증 대상이며 여기서 판단하지 않는다.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from normalization.values import (NormalizeError, as_text, fmt, is_empty, normalize_unit, parse_bool, parse_date,
                                  parse_enum, parse_int, parse_number, price_to_standard, to_standard)
from parsers.tabular import Table, read_csv, read_xlsx

BOM_HEADER_FIELDS = ("product_id", "bom_version", "status", "is_active", "valid_from", "valid_to", "min_qty", "max_qty",
                     "site_id", "base_qty")


def load_config(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class VendorParser:
    def __init__(self, config: dict, vendor: str, data_root: Path, dataset_prefix: str = "") -> None:
        self.cfg = config
        self.v = config["vendors"][vendor]
        self.vendor = vendor
        self.units = config["units"]
        self.std = config["standard_units"]
        self.root = Path(data_root)
        self.prefix = dataset_prefix            # "" (정상) 또는 "invalid/"
        self.diagnostics: list[dict] = []
        self.material_unit: dict[str, str] = {}  # 업체 자재 코드 → 업체 표기 단위 (자재 마스터에서)
        self.entities: dict[str, list[dict]] = defaultdict(list)
        self.files: list[dict] = []
        self.headers: list[dict] = []

    # ---------------- 진단 ----------------
    def diag(self, t: Table, row: int, column: str, field: str, code: str, message: str, raw=None, severity="error") -> None:
        self.diagnostics.append({"vendor": self.vendor, "file": t.path, "sheet": t.sheet, "row": row, "column": column,
                                 "field": field, "error_code": code, "severity": severity, "message": message,
                                 "raw": None if raw is None else as_text(raw)})

    # ---------------- 실행 ----------------
    def file_specs(self) -> list[dict]:
        specs = []
        by_path = {f["path"]: f for f in self.v["files"] if "same_as" not in f}
        for f in self.v["files"]:
            if "same_as" in f:
                base = dict(by_path[f["same_as"]])
                base.update({"path": f["path"], "sheet": f["sheet"]})
                specs.append(base)
            else:
                specs.append(f)
        return specs

    def run(self, only: str | None = None, timer=None) -> dict:
        for spec in self.file_specs():
            label = spec["path"] + (f":{spec['sheet']}" if spec.get("sheet") else "")
            if only and label != only:
                continue
            if timer:
                with timer(label):
                    self.parse_file(spec)
            else:
                self.parse_file(spec)
        return {"vendor": self.vendor, "dataset": "invalid" if self.prefix else "clean", "files": self.files,
                "headers": self.headers, "entities": dict(self.entities), "diagnostics": self.diagnostics}

    def parse_file(self, spec: dict) -> None:
        rel = f"{self.prefix}{self.v['dir']}/{spec['path']}"
        path = self.root / rel
        info = {"file": rel, "sheet": spec.get("sheet", ""), "entity": spec["entity"], "run_ok": False, "output_generated": False,
                "records": 0, "error": None}
        self.files.append(info)
        try:
            t = read_xlsx(path, rel, spec["sheet"]) if spec.get("sheet") else read_csv(path, rel)
        except Exception as exc:  # noqa: BLE001 - 읽기 실패는 실행 실패로 기록
            info["error"] = f"{type(exc).__name__}: {exc}"
            return
        info.update(t.meta)
        self.headers.append({"file": rel, "sheet": t.sheet, "header_rows": t.header_rows, "header": t.header})
        expected = list(spec["columns"])
        actual = [h["name"] for h in t.header]
        while actual and actual[-1] in (None, ""):
            actual.pop()
        info["run_ok"] = True
        if actual != expected:
            self.diag(t, t.header_rows, "*", "*", "ERR-TABLE",
                      f"헤더 열 구성이 설정과 다름 (기대 {len(expected)}열, 실제 {actual})")
            info["error"] = "헤더 불일치로 파싱 중단"
            return
        col_index = {h["name"]: h["col_index"] for h in t.header if h["name"]}
        records = []
        for row_no, row in t.data_rows():
            rec = self.parse_row(t, spec, col_index, row_no, row)
            records.append(rec)
        if spec.get("bom_flattened"):
            records = self.build_bom(t, spec, records)
        self.check_duplicates(t, spec, records)
        for r in records:
            r.pop("_row_cells", None)
        self.entities[spec["entity"]].extend(records)
        if spec.get("derive"):
            self.derive(spec, records)
        info["records"] = len(records)
        info["output_generated"] = bool(records)

    # ---------------- 행 파싱 ----------------
    def parse_row(self, t: Table, spec: dict, col_index: dict, row_no: int, row: list) -> dict:
        cols = spec["columns"]
        raw = {c: (row[col_index[c] - 1] if col_index[c] - 1 < len(row) else None) for c in cols}
        values, errors = {}, set()
        nf, df = self.v["number_format"], self.v["date_format"]

        def fail(col, e: NormalizeError):
            errors.add(col)
            # 다른 파일·시트의 오류 때문에 판단할 수 없게 된 값은 오류가 아니라 경고 (파생 영향)
            severity = "warning" if e.error_code == "ERR-UNRESOLVED" else "error"
            at = e.column if e.column in cols else col
            self.diag(t, row_no, at, cols[at]["field"], e.error_code, e.message, raw[at], severity)

        units_norm = {}
        for col, c in cols.items():  # 단위 열 먼저
            if c["type"] == "unit":
                if is_empty(raw[col]):
                    continue
                try:
                    units_norm[col] = normalize_unit(raw[col], self.units, self.v["unit_labels"])
                except NormalizeError as e:
                    fail(col, e)
        for col, c in cols.items():
            f = c["field"]
            r = raw[col]
            if is_empty(r):
                values[f] = None
                if c.get("required"):
                    errors.add(col)
                    self.diag(t, row_no, col, f, "ERR-MISSING", "필수값 누락", r)
                continue
            try:
                values[f] = self.convert(c, col, r, raw, units_norm, values, spec, nf, df)
            except NormalizeError as e:
                values[f] = None
                fail(col, e)
        if spec.get("material_master") and values.get("material_id") is not None:
            ucol = next(col for col, c in cols.items() if c["type"] == "unit")
            if ucol in units_norm:
                code_col = next(col for col, c in cols.items() if c["field"] == "material_id")
                self.material_unit[as_text(raw[code_col])] = units_norm[ucol]
        source = {"vendor": self.vendor, "file": t.path, "sheet": t.sheet, "row": row_no,
                  "cells": {cols[col]["field"]: {"column": col, "col_index": col_index[col], "raw": None if raw[col] is None else as_text(raw[col])}
                            for col in cols}}
        return {"entity": spec["entity"], "values": values, "source": source, "field_errors": sorted(cols[c]["field"] for c in errors),
                "_row_cells": raw}

    def code(self, kind: str, r, entity: str) -> str:
        s = as_text(r)
        table = self.v["codes"].get(kind, {})
        if s not in table:
            code = "ERR-RESREL" if (kind == "resource" and entity == "Operation") else "ERR-BADREF"
            raise NormalizeError(code, f"코드 대응표({kind})에 없는 코드: {s!r}")
        return table[s]

    def convert(self, c: dict, col: str, r, raw: dict, units_norm: dict, values: dict, spec: dict, nf: str, df: str):
        t = c["type"]
        if t == "text":
            return as_text(r)
        if t == "code":
            return self.code(c["codes"], r, spec["entity"])
        if t == "item_code":
            kind_raw = raw[c["type_column"]]
            kind = parse_enum(kind_raw, spec["columns"][c["type_column"]]["values"])
            return self.code("material" if kind == "MATERIAL" else "product", r, spec["entity"])
        if t == "id_rule":
            rule = self.v["id_rules"][c["rule"]]
            m = re.match(rule["pattern"], as_text(r))
            if not m:
                raise NormalizeError("ERR-IDVER", f"ID 규칙({rule['pattern']})에 맞지 않음: {as_text(r)!r}")
            return rule["template"].format(n=int(m.group(1)))
        if t == "enum":
            return parse_enum(r, c["values"])
        if t == "bool":
            return parse_bool(r, self.v["bool"])
        if t == "int":
            return parse_int(r, nf)
        if t == "number":
            return fmt(parse_number(r, nf))
        if t == "ratio":
            return fmt(parse_number(r, nf))
        if t == "percent":
            return fmt(parse_number(r, nf) / 100)
        if t == "date":
            return parse_date(r, df).isoformat()
        if t == "unit":
            if col not in units_norm:
                raise NormalizeError("ERR-UNIT", f"알 수 없는 단위: {r!r}")
            return self.std[self.units[units_norm[col]]["dimension"]]
        if t == "price_per_unit":
            u = units_norm.get(c["unit_column"])
            if u is None:
                raise NormalizeError("ERR-UNIT", "가격 단위를 알 수 없음")
            return fmt(price_to_standard(parse_number(r, nf), u, self.units, self.std))
        if t == "qty":
            q = parse_number(r, nf)
            if "unit_column" in c:
                u = units_norm.get(c["unit_column"])
            else:
                code_raw = as_text(raw[c["unit_from_material"]])
                u = self.material_unit.get(code_raw)
                if u is None:
                    raise NormalizeError("ERR-UNRESOLVED", f"자재 마스터에서 {code_raw!r}의 단위를 찾지 못함")
            if u is None:
                raise NormalizeError("ERR-UNIT", "수량 단위를 알 수 없음")
            if "item_column" in c:
                self.check_dimension(c, raw, u, spec)
            v, _ = to_standard(q, u, self.units, self.std)
            return fmt(v)
        raise ValueError(f"알 수 없는 열 형식: {t}")

    def check_dimension(self, c: dict, raw: dict, unit: str, spec: dict) -> None:
        """수량 단위 차원이 품목 단위 차원과 같은지. 제품은 COUNT, 자재는 업체 자재 마스터 단위 기준."""
        item_raw = as_text(raw[c["item_column"]])
        cols = spec["columns"]
        type_col = cols[c["item_column"]].get("type_column")
        is_material = False
        if type_col:
            try:
                is_material = parse_enum(raw[type_col], cols[type_col]["values"]) == "MATERIAL"
            except NormalizeError:
                return
        if is_material:
            mu = self.material_unit.get(item_raw)
            if mu is None:
                return  # 자재 마스터 없음 → 검사 불가 (경고 없이 생략)
            expected = self.units[mu]["dimension"]
        else:
            expected = "COUNT"
        if self.units[unit]["dimension"] != expected:
            raise NormalizeError("ERR-UNIT", f"품목 {item_raw!r} 단위 차원({expected})과 수량 단위({unit}) 불일치",
                                 column=c.get("unit_column"))

    # ---------------- BOM 평면 표 → 헤더/라인 ----------------
    def build_bom(self, t: Table, spec: dict, records: list[dict]) -> list[dict]:
        cols = spec["columns"]
        field_col = {c["field"]: col for col, c in cols.items()}
        groups = defaultdict(list)
        for r in records:
            groups[r["values"].get("_group")].append(r)
        lines = []
        for g, rows in groups.items():
            header = {}
            for f in BOM_HEADER_FIELDS:
                vals = Counter(json.dumps(r["values"].get(f)) for r in rows if f not in r["field_errors"])
                if not vals:
                    header[f] = None
                    continue
                top, top_n = vals.most_common(1)[0]
                if len(vals) > 1:
                    for r in rows:
                        if f not in r["field_errors"] and json.dumps(r["values"].get(f)) != top:
                            self.diag(t, r["source"]["row"], field_col[f], f, "ERR-IDVER",
                                      f"같은 BOM 번호({g})의 다른 행과 {f} 값이 다름 (다수 값 {json.loads(top)!r})",
                                      r["source"]["cells"][f]["raw"])
                            r["field_errors"].append(f)
                header[f] = json.loads(top)
            bom_id = None
            if header.get("product_id") and header.get("bom_version"):
                bom_id = self.v["id_rules"]["bom"]["template"].format(**header)
            self.entities["BOM"].append({"entity": "BOM", "values": {"bom_id": bom_id, **header},
                                         "source": {"vendor": self.vendor, "file": t.path, "sheet": t.sheet,
                                                    "rows": [r["source"]["row"] for r in rows], "group": g},
                                         "field_errors": []})
            for r in rows:
                v = r["values"]
                comp = v.pop("component_id", None)
                line = {"bom_id": bom_id, "line_no": v.get("line_no"), "component_type": v.get("component_type"),
                        "component_material_id": comp if v.get("component_type") == "MATERIAL" else None,
                        "component_product_id": comp if v.get("component_type") == "PRODUCT" else None,
                        "qty_per": v.get("qty_per"), "unit": v.get("unit"), "scrap_rate": v.get("scrap_rate")}
                r["values"] = line
                r["source"]["cells"]["component_material_id" if v.get("component_type") == "MATERIAL" else "component_product_id"] = \
                    r["source"]["cells"].pop("component_id")
                lines.append(r)
        return lines

    def check_duplicates(self, t: Table, spec: dict, records: list[dict]) -> None:
        keyf = spec["key"]
        groups = defaultdict(list)
        for r in records:
            k = tuple(r["values"].get(f) for f in keyf)
            if None not in k:
                groups[k].append(r)
        cols = spec["columns"]
        first_key_col = next((col for col, c in cols.items() if c["field"] == keyf[0]), None) or \
            next(col for col, c in cols.items() if c["field"] == "_group")
        for k, rs in groups.items():
            if len(rs) > 1:
                for r in rs:
                    self.diag(t, r["source"]["row"], first_key_col, keyf[0], "ERR-DUPID",
                              f"같은 파일 안 키 중복 {k} ({len(rs)}행: {[x['source']['row'] for x in rs]})",
                              r["source"]["cells"].get(keyf[0], {}).get("raw"))

    def derive(self, spec: dict, records: list[dict]) -> None:
        d = spec["derive"]
        seen = {}
        for r in records:
            vals = {f: r["values"].get(f) for f in d["fields"]}
            k = tuple(vals[f] for f in d["key"])
            if None in k or k in seen:
                continue
            seen[k] = True
            self.entities[d["entity"]].append({"entity": d["entity"], "values": vals,
                                               "source": {**r["source"], "cells": {f: r["source"]["cells"][f] for f in d["fields"]}},
                                               "field_errors": []})


def parse_vendor(config: dict, vendor: str, data_root: Path, invalid: bool = False, only: str | None = None, timer=None) -> dict:
    """업체 1곳의 파일 전체(또는 only로 지정한 파일 1개)를 파싱한다."""
    p = VendorParser(config, vendor, data_root, "invalid/" if invalid else "")
    out = p.run(only=only, timer=timer)
    return out
