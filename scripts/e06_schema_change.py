"""E06 규칙·스키마 변경 시나리오: Python/Pydantic · SQLite · RDF/SHACL의 수정 범위·데이터 이전·호환성·회귀 비교.

    .\\.venv\\Scripts\\python.exe scripts\\e06_schema_change.py

- 원본 파일은 바꾸지 않는다. 임시 폴더에 scripts·설정·정답셋을 복사하고 시나리오별 패치(정확한 문자열 치환)를 적용한 뒤,
  별도 프로세스에서 E05 평가셋 72개 전체를 다시 검증해 변경 전후 보고 차이를 비교한다.
- SHACL은 hybrid 엔진(Core shape는 pyshacl, SPARQL 규칙은 같은 질의를 rdflib로 1회)으로 회귀를 돌린다 (pyshacl 전체 실행은 72개×약 16초).
- 수정 범위 = 바뀐 파일 수와 diff의 +/− 줄 수 (사람 작업시간은 측정하지 않음 — 자동 실행시간과 구분).
"""

from __future__ import annotations

import copy
import difflib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "E06_rdf_shacl"
FILES = {"python": ["scripts/e01_models.py", "scripts/e05_validate_python.py"], "sqlite": ["scripts/e01_models.py", "scripts/e05_validate_sql.py"],
         "shacl": ["scripts/e01_models.py", "scripts/e06_shapes.py", "scripts/e06_build_rdf.py"]}

# 시나리오: 기술별 패치 (파일, 바꿀 문자열, 새 문자열). 의미 있는 실제 스키마 변경만 둔다.
SCENARIOS = {
    "SC1": {"title": "필수 속성 추가 — BOM.site_id 필수화 (다사이트 운영 가정)", "kind": "schema",
            "patches": {"python": [("scripts/e01_models.py", "    site_id: Optional[str] = None\n    base_qty", "    site_id: str\n    base_qty")],
                        "sqlite": [("scripts/e01_models.py", "    site_id: Optional[str] = None\n    base_qty", "    site_id: str\n    base_qty")],
                        "shacl": [("scripts/e01_models.py", "    site_id: Optional[str] = None\n    base_qty", "    site_id: str\n    base_qty")]}},
    "SC2": {"title": "유효기간 규칙 변경 — 종료일 포함 → 종료일 미포함 (QR-06① 판정식)", "kind": "rule",
            "patches": {"python": [("scripts/e05_validate_python.py", 'period = date(x["valid_from"]) <= yt and date(y["valid_from"]) <= xt',
                                    'period = date(x["valid_from"]) < yt and date(y["valid_from"]) < xt'),
                                   ("scripts/e05_validate_python.py", "if vf <= d <= (vt or dt.date.max) and", "if vf <= d < (vt or dt.date.max) and")],
                        "sqlite": [("scripts/e05_validate_sql.py", "WHERE x.valid_from <= COALESCE(y.valid_to, '9999-12-31') AND y.valid_from <= COALESCE(x.valid_to, '9999-12-31') ",
                                    "WHERE x.valid_from < COALESCE(y.valid_to, '9999-12-31') AND y.valid_from < COALESCE(x.valid_to, '9999-12-31') "),
                                   ("scripts/e05_validate_sql.py", "l.period_start <= COALESCE(b.valid_to, '9999-12-31')", "l.period_start < COALESCE(b.valid_to, '9999-12-31')")],
                        "shacl": [("scripts/e06_shapes.py", "FILTER((!BOUND(?yt) || ?xf <= ?yt) && (!BOUND(?xt) || ?yf <= ?xt)",
                                   "FILTER((!BOUND(?yt) || ?xf < ?yt) && (!BOUND(?xt) || ?yf < ?xt)"),
                                  ("scripts/e06_shapes.py", "(!BOUND(?vt{b[1:]}) || {d} <= ?vt{b[1:]})", "(!BOUND(?vt{b[1:]}) || {d} < ?vt{b[1:]})")]}},
    "SC3": {"title": "공급사 관계 규칙 변경 — 자재당 우선 공급사 '정확히 1개' → '최대 1개'", "kind": "rule",
            "patches": {"python": [("scripts/e05_validate_python.py", "        if n != 1:\n", "        if n > 1:\n")],
                        "sqlite": [("scripts/e05_validate_sql.py", "HAVING SUM(CASE WHEN is_preferred = 1 THEN 1 ELSE 0 END) <> 1", "HAVING SUM(CASE WHEN is_preferred = 1 THEN 1 ELSE 0 END) > 1")],
                        "shacl": [("scripts/e06_shapes.py", '    S.sparql("B11", "SupplierMaterial", "is_preferred", "none", f"""', '    if False: S.sparql("B11", "SupplierMaterial", "is_preferred", "none", f"""')]}},
    "SC4": {"title": "자재 코드 체계 변경 — M001 → MAT-0001 (데이터 이전, 규칙 변경 없음)", "kind": "data"},
    "SC5": {"title": "BOM 속성 추가 — 선택 속성 revision_note (모델·테이블 미반영 상태로 데이터에 먼저 등장)", "kind": "data"},
}


def diff_lines(a: str, b: str) -> int:
    return sum(1 for l in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---"))


def make_tree(tmp: Path, patches: list) -> dict:
    for d in ("scripts", "configs", "data/canonical/e05"):
        (tmp / d).mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "scripts").glob("e0*.py"):
        shutil.copy2(f, tmp / "scripts" / f.name)
    shutil.copy2(ROOT / "configs" / "e05_validation_rules.json", tmp / "configs")
    shutil.copy2(ROOT / "data" / "canonical" / "ground_truth_v2.json", tmp / "data" / "canonical")
    for f in (ROOT / "data" / "canonical" / "e05").glob("*.json"):
        shutil.copy2(f, tmp / "data" / "canonical" / "e05")
    changed = {}
    for rel, old, new in patches:
        p = tmp / rel
        s = p.read_text(encoding="utf-8")
        if s.count(old) != 1:
            raise SystemExit(f"패치 대상 문자열이 1회가 아님: {rel}: {old[:60]}")
        p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")
    for rel in {r for r, _, _ in patches}:
        changed[rel] = diff_lines((ROOT / rel).read_text(encoding="utf-8"), (tmp / rel).read_text(encoding="utf-8"))
    return changed


def run_child(tmp: Path, method: str) -> dict:
    r = subprocess.run([sys.executable, str(tmp / "scripts" / "e06_schema_change.py"), "--child", method], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"자식 실행 실패 {method}: {r.stderr[-2000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def child(method: str) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import logging
    logging.disable(logging.CRITICAL)
    import e05_dataset as D
    gt = D.load_gt()
    spec = json.loads((D.EVAL_DIR / "eval_set_v1.json").read_text(encoding="utf-8"))
    out = {}
    if method == "shacl":
        import e06_shapes
        ttl, _ = e06_shapes.shapes_ttl(gt["parameters"])
        out["_shapes_ttl"] = ttl
    for ds in spec["datasets"]:
        ents, _ = D.apply_ops(gt["entities"], ds["ops"], ds["dataset_id"])
        if method == "python":
            import e05_validate_python as M
            reps = M.validate(ents, gt["parameters"], ds["dataset_id"])["reports"]
        elif method == "sqlite":
            import e05_validate_sql as M
            reps = M.run_queries(ents, gt["parameters"], ds["dataset_id"])["reports"]
        else:
            import e06_validate_shacl as M
            reps = M.validate(ents, gt["parameters"], ds["dataset_id"], engine="hybrid")["reports"]
        out[ds["dataset_id"]] = sorted({f"{r['rule_id']}|{r['record_uid']}|{r['field']}" for r in reps if r["severity"] != "INFO"})
    print(json.dumps(out, ensure_ascii=False))


def regress(base: dict, new: dict) -> dict:
    changed = {}
    for k in base:
        if k.startswith("_"):
            continue
        a, b = set(base[k]), set(new[k])
        if a != b:
            changed[k] = {"removed": sorted(a - b), "added": sorted(b - a)}
    return changed


def data_scenarios(gt) -> dict:
    """SC4·SC5: 데이터 변경 — 규칙 코드는 그대로 두고, 이전해야 하는 값의 양과 기존 검증의 호환성을 본다."""
    import logging
    logging.disable(logging.CRITICAL)
    import e05_validate_python as PY
    import e05_validate_sql as SQL
    import e06_validate_shacl as SH
    from e06_build_rdf import build_graph, canonical_nt
    res = {}
    # SC4 자재 코드 변경
    ents = copy.deepcopy(gt["entities"])
    newid = {m["material_id"]: f"MAT-{int(m['material_id'][1:]):04d}" for m in ents["Material"]}
    fields = 0
    for ent, rows in ents.items():
        for r in rows:
            for f in ("material_id", "component_material_id"):
                if r.get(f) in newid and not (ent == "Inventory"):
                    r[f], fields = newid[r[f]], fields + 1
            if ent == "Inventory" and r.get("item_type") == "MATERIAL":
                r["item_id"], fields = newid[r["item_id"]], fields + 1
    rows_changed = sum(1 for e in ents for a, b in zip(ents[e], gt["entities"][e]) if a != b)
    before, after = set(canonical_nt(build_graph(gt["entities"], "clean")).splitlines()), set(canonical_nt(build_graph(ents, "clean")).splitlines())
    res["SC4"] = {"records_changed": rows_changed, "field_values_changed": fields, "rdf_triples_removed": len(before - after), "rdf_triples_added": len(after - before),
                  "rdf_note": "업무 ID에서 IRI를 만들므로 자재 키 노드 IRI가 바뀌고, 그 IRI를 가리키는 참조 트리플도 함께 바뀜",
                  "after_change_errors": {"python": len([r for r in PY.validate(ents, gt["parameters"], "SC4")["reports"] if r["severity"] != "INFO"]),
                                          "sqlite": len([r for r in SQL.run_queries(ents, gt["parameters"], "SC4")["reports"] if r["severity"] != "INFO"]),
                                          "shacl": len(SH.validate(ents, gt["parameters"], "SC4")["reports"])}}
    # SC5 BOM 선택 속성 추가
    ents = copy.deepcopy(gt["entities"])
    for b in ents["BOM"]:
        b["revision_note"] = f"rev-{b['bom_version']}"
    py = PY.validate(ents, gt["parameters"], "SC5")
    from e01_models import MODELS
    from pydantic import ValidationError
    pyd_errors = []
    for b in ents["BOM"]:
        try:
            MODELS["BOM"].model_validate(b)
        except ValidationError as e:
            pyd_errors += [x["type"] for x in e.errors()]
    import sqlite3
    con = sqlite3.connect(":memory:")
    SQL.staging(con, ents)
    sql_cols = [r[1] for r in con.execute('PRAGMA table_info("BOM")')]
    g = build_graph(ents, "SC5")
    from e06_build_rdf import CP
    sh = SH.validate(ents, gt["parameters"], "SC5")
    res["SC5"] = {"pydantic_raw_errors": sorted(set(pyd_errors)), "pydantic_raw_error_count": len(pyd_errors),
                  "python_full_reports": len([r for r in py["reports"] if r["severity"] != "INFO"]),
                  "python_note": "E05 검증기는 pydantic 오류 유형 extra_forbidden을 규칙에 대응시키지 않아 보고 없이 넘어감",
                  "sqlite_column_exists": "revision_note" in sql_cols, "sqlite_note": "적재 테이블 열이 모델 필드에서 정해져 새 속성 값은 적재되지 않고 사라짐",
                  "rdf_triples_with_new_property": len(list(g.triples((None, CP.BOM_revision_note, None)))), "shacl_reports": len(sh["reports"]),
                  "rdf_note": "변환기가 레코드의 모든 키를 속성으로 옮기므로 값은 그래프에 남고, shape가 없어 검증 대상은 아님 (열린 세계)"}
    return res


def main() -> int:
    if "--child" in sys.argv:
        child(sys.argv[sys.argv.index("--child") + 1])
        return 0
    sys.path.insert(0, str(ROOT / "scripts"))
    import e05_dataset as D
    gt = D.load_gt()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"scenarios": {}}
    with tempfile.TemporaryDirectory() as td:
        base_tree = Path(td) / "base"
        make_tree(base_tree, [])
        base = {m: run_child(base_tree, m) for m in FILES}
        for sid, sc in SCENARIOS.items():
            if sc["kind"] == "data":
                continue
            entry = {"title": sc["title"], "kind": sc["kind"], "methods": {}}
            for m, patches in sc["patches"].items():
                tree = Path(td) / f"{sid}_{m}"
                changed = make_tree(tree, patches)
                new = run_child(tree, m)
                e = {"files_changed": sorted(changed), "lines_changed": sum(changed.values()), "lines_by_file": changed}
                if m == "shacl":
                    e["generated_ttl_lines_changed"] = diff_lines(base["shacl"]["_shapes_ttl"], new["_shapes_ttl"])
                reg = regress(base[m], new)
                e["datasets_changed"] = len(reg)
                e["clean_reports_after"] = len(new["clean"])
                e["changes"] = reg
                entry["methods"][m] = e
            report["scenarios"][sid] = entry
    report["data_scenarios"] = data_scenarios(gt)
    for sid in ("SC4", "SC5"):
        report["data_scenarios"][sid]["title"] = SCENARIOS[sid]["title"]
    (OUT / "schema_change.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    for sid, e in report["scenarios"].items():
        print(sid, {m: (v["files_changed"], v["lines_changed"], v["datasets_changed"], v["clean_reports_after"]) for m, v in e["methods"].items()})
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if "note" not in kk} for k, v in report["data_scenarios"].items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
