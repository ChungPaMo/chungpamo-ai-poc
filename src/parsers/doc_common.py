"""E03 문서 파서 공통: 공통 중간 JSON(스키마 0.2) 골격, 표 조각 연결 후처리.

파서는 정답 명세·위치 메타데이터를 읽지 않는다. 문서 파일만 입력으로 받는다.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

SCHEMA_VERSION = "0.2"
PAGE_NUMBER_RE = re.compile(r"^\d+\s*/\s*\d+$|^-?\s*\d+\s*-?$")


def new_ir(path: Path, rel: str, fmt: str, parser: dict) -> dict:
    data = path.read_bytes()
    return {
        "schema": "chungpamo.parse_ir", "schema_version": SCHEMA_VERSION,
        "document": {"source_file": rel, "format": fmt, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)},
        "parser": {**parser, "mode": "direct", "api_calls": 0},
        "blocks": [], "tables": [], "extracted_values": [], "records": [], "diagnostics": [],
        "format_specific": {},
    }


def diag(ir: dict, code: str, message: str, severity: str = "warning", location: dict | None = None) -> None:
    ir["diagnostics"].append({"code": code, "severity": severity, "location": location, "field": None, "message": message, "raw": None})


def finalize_order(ir: dict, sequence: list[str]) -> None:
    """읽기 순서: 블록·표를 같은 순번 공간에 놓는다 (format_specific.reading_sequence). 블록 order = 그 순번."""
    ir["format_specific"]["reading_sequence"] = sequence
    pos = {x: i for i, x in enumerate(sequence)}
    for b in ir["blocks"]:
        b["order"] = pos[b["block_id"]]


def _row_signature(table: dict, row: int) -> tuple:
    return tuple((c["col"], c["rowspan"], c["colspan"], re.sub(r"\s+", " ", c["text"]).strip())
                 for c in sorted(table["cells"], key=lambda c: c["col"]) if c["row"] == row)


def link_fragments(ir: dict, unit_key: str) -> int:
    """페이지·슬라이드를 넘는 표 조각 연결 (라이브러리 기능이 아닌 공통 후처리 규칙, 결과는 'inferred'로 표시).

    규칙: 읽기 순서상 연속한 두 표 a→b가 (1) 바로 다음 page/slide에 있고 (2) 열 수가 같고 (3) b의 첫 행부터
    1행 이상이 a의 첫 행들과 같고 (4) a가 그 단위의 마지막 본문 요소, b가 첫 본문 요소일 때 연결한다.
    매 단위에 반복되는 텍스트(머리말·꼬리말 후보)와 쪽 번호 형태의 텍스트는 본문 요소에서 뺀다.
    """
    seq = ir["format_specific"]["reading_sequence"]
    blocks = {b["block_id"]: b for b in ir["blocks"]}
    tables = {t["table_id"]: t for t in ir["tables"]}
    unit = lambda x: (blocks.get(x) or tables[x])["location"].get(unit_key)
    units = {unit(x) for x in seq}
    per_unit_texts = {}
    for b in ir["blocks"]:
        per_unit_texts.setdefault(re.sub(r"\s+", " ", b["text"]).strip(), set()).add(unit(b["block_id"]))
    furniture = {t for t, us in per_unit_texts.items() if len(units) > 1 and us == units} | {t for t in per_unit_texts if PAGE_NUMBER_RE.match(t)}
    body = [x for x in seq if x in tables or re.sub(r"\s+", " ", blocks[x]["text"]).strip() not in furniture]
    links = 0
    tseq = [x for x in seq if x in tables]
    for a_id, b_id in zip(tseq, tseq[1:]):
        a, b = tables[a_id], tables[b_id]
        ua, ub = unit(a_id), unit(b_id)
        if ua is None or ub is None or ub != ua + 1 or a["n_cols"] != b["n_cols"]:
            continue
        a_last = [x for x in body if unit(x) == ua][-1] == a_id
        b_first = [x for x in body if unit(x) == ub][0] == b_id
        k = 0
        while k < min(a["n_rows"], b["n_rows"]) - 1 and _row_signature(a, k + 1) == _row_signature(b, k + 1) and _row_signature(a, k + 1):
            k += 1
        if not (a_last and b_first and k >= 1):
            continue
        root = a.get("logical_table_id") or a_id
        a["logical_table_id"] = root
        a.setdefault("fragment_index", 0)
        a["continuation"] = {**(a.get("continuation") or {}), "continues_to": b_id, "method": "header_repeat_rule", "detection": "inferred"}
        b["logical_table_id"] = root
        b["fragment_index"] = a["fragment_index"] + 1
        b["repeated_header_rows"] = list(range(1, k + 1))
        b["continuation"] = {**(b.get("continuation") or {}), "continues_from": a_id, "repeated_header": True,
                             "method": "header_repeat_rule", "detection": "inferred"}
        links += 1
    return links
