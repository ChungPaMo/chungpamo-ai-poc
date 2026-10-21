"""E05 평가셋 공통: E01 정답셋 v2 적재, 레코드 선택(where), 변경 연산(set·add·remove) 적용, 데이터셋 해시.

검증기(e05_validate_*)와 채점기(e05_score)는 이 모듈로 데이터셋을 만들기만 하고, 주입 정답(기대 규칙)은 읽지 않는다.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "data" / "canonical" / "ground_truth_v2.json"
GT_SHA256 = "262dbe75dbfaf8c0c32003144d62e0b2057c61187dce4b548a457cf8819fc48e"
EVAL_DIR = ROOT / "data" / "canonical" / "e05"
ENTITY_ORDER = ["Unit", "Product", "Material", "Supplier", "SupplierMaterial", "BOM", "BOMLine", "Order", "SalesHistory",
                "Inventory", "Resource", "Operation", "ProductionPlan", "ProductionPlanLine"]


def load_gt() -> dict:
    blob = GT.read_bytes()
    if hashlib.sha256(blob).hexdigest() != GT_SHA256:
        raise SystemExit("ground_truth_v2.json 해시 불일치 → 중단")
    return json.loads(blob)


def dataset_sha256(entities: dict) -> str:
    return hashlib.sha256(json.dumps(entities, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def new_uid(*parts: str) -> str:
    return "rec_" + hashlib.sha256("|".join(("e05",) + parts).encode("utf-8")).hexdigest()[:16]


def _num(v):
    try:
        return Decimal(str(v)) if not isinstance(v, bool) and v is not None and re.fullmatch(r"-?\d+(\.\d+)?", str(v)) else None
    except InvalidOperation:
        return None


def _match(rec: dict, where: dict) -> bool:
    for k, cond in where.items():
        v = rec.get(k)
        if isinstance(cond, dict):
            for op, x in cond.items():
                a, b = (_num(v), _num(x)) if _num(v) is not None and _num(x) is not None else (v, x)   # 숫자면 숫자로, 아니면 문자열(ISO 날짜)로 비교
                if v is None or not {">=": lambda: a >= b, "<=": lambda: a <= b, ">": lambda: a > b, "<": lambda: a < b, "!=": lambda: a != b}[op]():
                    return False
        elif v != cond:
            return False
    return True


def select(entities: dict, entity: str, where: dict, many: bool = False) -> list[dict]:
    hits = [r for r in entities[entity] if _match(r, where)]
    if not many and len(hits) != 1:
        raise ValueError(f"선택 결과가 1건이 아님: {entity} {where} → {len(hits)}건")
    return hits


def apply_ops(base: dict, ops: list[dict], tag: str) -> tuple[dict, list[dict]]:
    """연산을 순서대로 적용. 반환: (새 엔터티, 연산별 실제 효과 기록)."""
    ents = copy.deepcopy(base)
    effects = []
    for i, op in enumerate(ops):
        kind, ent = op["op"], op["entity"]
        if kind == "set":
            for r in select(ents, ent, op["where"], op.get("many", False)):
                effects.append({"op": i, "kind": "set", "entity": ent, "record_uid": r["record_uid"], "field": op["field"],
                                "old": r.get(op["field"]), "new": op["value"]})
                r[op["field"]] = op["value"]
        elif kind == "add":
            src = select(ents, ent, op["copy_of"])[0] if op.get("copy_of") else {}
            rec = {**copy.deepcopy(src), **op.get("values", {})}
            rec["record_uid"] = op.get("record_uid") or new_uid(tag, str(i))
            ents[ent].append(rec)
            effects.append({"op": i, "kind": "add", "entity": ent, "record_uid": rec["record_uid"]})
        elif kind == "remove":
            gone = select(ents, ent, op["where"], op.get("many", False))
            ids = {r["record_uid"] for r in gone}
            ents[ent] = [r for r in ents[ent] if r["record_uid"] not in ids]
            effects += [{"op": i, "kind": "remove", "entity": ent, "record_uid": u} for u in sorted(ids)]
        else:
            raise ValueError(kind)
    return ents, effects


def resolve(entities_after: dict, entities_before: dict, ref: dict, effects: list[dict]) -> list[str]:
    """정답 대상 참조 → record_uid 목록. {"added": 연산번호} 또는 {"entity", "where", "many"}."""
    if "added" in ref:
        return [e["record_uid"] for e in effects if e["kind"] == "add" and e["op"] == ref["added"]]
    src = entities_before if ref.get("before") else entities_after
    return [r["record_uid"] for r in select(src, ref["entity"], ref["where"], ref.get("many", False))]


def materialize(spec: dict, dataset_id: str) -> dict:
    """평가셋 명세(eval_set_v1.json)의 데이터셋 하나를 엔터티 dict로 만든다."""
    gt = load_gt()
    ds = next(d for d in spec["datasets"] if d["dataset_id"] == dataset_id)
    ents, _ = apply_ops(gt["entities"], ds["ops"], dataset_id)
    return ents
