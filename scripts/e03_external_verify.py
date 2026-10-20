"""외부 문서 평가 결과 재검증: 저장된 첫 실행 IR을 같은 채점기로 다시 채점해 grading.json과 비교하고,
holdout 무결성(동결 순서·코드 해시·중복·결과 불변)과 공식/잠정 정답 혼합 여부를 확인한다. 결과 파일은 바꾸지 않는다.

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_verify.py

출력: results/E03_document_parsers/external_verification.json (텍스트 없는 공개용)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import e03_grade_external as G

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "results" / "E03_document_parsers"
TRUTH = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"
RUNS = ["external_baseline_v1", "external_dev_v1", "external_dev_v2", "external_holdout_v1", "external_holdout_v2", "external_blind8_v2"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def agg(results, fmt, key, parser=None):
    n = d = 0
    statuses = set()
    for r in results:
        g = r["grade"]
        if g.get("format") != fmt or (parser and r["parser"] != parser):
            continue
        v = g["metrics"]
        for k in key.split("."):
            v = v.get(k) if isinstance(v, dict) else None
        if isinstance(v, dict) and v.get("denominator"):
            n += v["numerator"]
            d += v["denominator"]
            statuses.add(v.get("truth_status") or "VERIFIED_OFFICIAL")
    return {"numerator": n, "denominator": d, "truth_status": sorted(statuses), "mixed_official_and_provisional": len(statuses) > 1}


def main() -> int:
    truth_blob = TRUTH.read_bytes()
    truth = {d["doc_id"]: d for d in json.loads(truth_blob)["documents"]}
    splits = json.loads((ROOT / "configs" / "e03_external_splits.json").read_text(encoding="utf-8"))
    freeze = json.loads((B / "external_v2_freeze.json").read_text(encoding="utf-8"))
    out = {"truth_sha256": sha(TRUTH), "truth_matches_manifest": sha(TRUTH) == json.loads((B / "external_truth_v1" / "truth_manifest.json").read_text(encoding="utf-8"))["truth_sha256"],
           "runs": {}}
    stored_all = {}
    for run in RUNS:
        d = B / run
        meta = json.loads((d / "run_meta.json").read_text(encoding="utf-8"))
        man = json.loads((d / "sha256_manifest.json").read_text(encoding="utf-8"))
        stored = json.loads((d / "grading.json").read_text(encoding="utf-8"))["results"]
        stored_all[run] = stored
        mism = []
        for r in stored:
            p = d / "outputs" / "first_run" / f"{r['doc_id']}__{r['parser']}.json"
            ir = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
            again = G.grade(ir, truth[r["doc_id"]])
            if json.dumps(again, sort_keys=True, ensure_ascii=False) != json.dumps(r["grade"], sort_keys=True, ensure_ascii=False):
                mism.append(f"{r['doc_id']}×{r['parser']}")
        out["runs"][run] = {
            "parser_version": meta["parser_version"], "set": meta["set"], "start": meta["run_timestamp"],
            "manifest_files": len(man), "manifest_changed": [k for k, v in man.items() if sha(d / k) != v],
            "regrade_mismatch": mism, "grader_sha256": meta["grader_sha256"], "truth_sha256": meta["truth"]["sha256"],
            "v2_code_equals_freeze": all(meta["code"]["files"].get(k) == v for k, v in freeze["files"].items()) if meta["parser_version"] == "v2" else None,
        }
    # holdout 무결성
    hv1, hv2 = out["runs"]["external_holdout_v1"], out["runs"]["external_holdout_v2"]
    out["holdout_integrity"] = {
        "freeze_before_holdout_runs": freeze["frozen_at"] <= hv1["start"] and freeze["frozen_at"] <= hv2["start"],
        "v2_code_at_holdout_equals_freeze": hv2["v2_code_equals_freeze"],
        "current_v2_code_equals_freeze": all(sha(ROOT / k) == v for k, v in freeze["files"].items()),
        "holdout_results_unchanged": not hv1["manifest_changed"] and not hv2["manifest_changed"],
        "same_grader_and_truth_all_runs": len({r["grader_sha256"] for r in out["runs"].values()}) == 1 and len({r["truth_sha256"] for r in out["runs"].values()}) == 1,
        "holdout_not_in_dev_list": not (set(splits["holdout"]) & set(splits["dev"])),
        "dev_tuning_evidence": "v2 개발 루프 스크립트는 dev 목록만 읽음(작업 기록). 파서 소스에 holdout 문서 식별 문자열 없음은 테스트로 확인. 개발 중 holdout 출력 열람 여부는 기록·코드로 완전 증명할 수 없음 → '로그상 미사용'으로만 확인",
    }
    # 중복 (파일 해시, PMC ID, PubTables 표 ID)
    by_split = {}
    for k in ("blind8", "dev", "holdout"):
        docs = [truth[i] for i in splits[k]]
        by_split[k] = {"sha": {d["sha256"] for d in docs}, "file": {d["file"] for d in docs},
                       "tables": {t["table_id"] for d in docs if d.get("truth") and d["format"] == "pdf" for t in d["truth"]["tables"]}}
    dup = {}
    for a, b in (("blind8", "dev"), ("blind8", "holdout"), ("dev", "holdout")):
        dup[f"{a}-{b}"] = {k: sorted(by_split[a][k] & by_split[b][k]) for k in ("sha", "file", "tables")}
    out["duplicates_between_splits"] = dup
    # 핵심 지표 재계산 (저장 결과에서)
    hv1r, hv2r = stored_all["external_holdout_v1"], stored_all["external_holdout_v2"]
    out["recomputed"] = {
        "holdout_pdf_tables": {"v1": agg(hv1r, "pdf", "table_detection.recall", "pdfplumber"), "v2": agg(hv2r, "pdf", "table_detection.recall", "pdfplumber")},
        "holdout_pdf_cells_grid": {"v1": agg(hv1r, "pdf", "cells.text_loose_grid", "pdfplumber"), "v2": agg(hv2r, "pdf", "cells.text_loose_grid", "pdfplumber")},
        "holdout_pdf_merges": {"v1": agg(hv1r, "pdf", "cells.merge_spans", "pdfplumber"), "v2": agg(hv2r, "pdf", "cells.merge_spans", "pdfplumber")},
        "blind8_role": "회귀 측정 (최초 실패 분석에서 출력·정답 열람)",
    }
    # 공식·잠정 혼합 집계 여부 (비교표 지표 전체)
    mixed = []
    for run, res in stored_all.items():
        for fmt, keys in (("pdf", ["table_detection.recall", "cells.text_loose_grid", "cells.merge_spans"]),
                          ("docx", ["body_paragraph_exact", "cells.text_strict_grid", "footnotes"]),
                          ("pptx", ["shape_text_exact", "cells.merge_spans", "smartart_node_text_found", "chart_text_found"])):
            for k in keys:
                a = agg(res, fmt, k, "pdfplumber" if fmt == "pdf" else None)
                if a["mixed_official_and_provisional"] or "MIXED" in a["truth_status"]:
                    mixed.append({"run": run, "format": fmt, "metric": k, "truth_status": a["truth_status"]})
    out["aggregates_mixing_official_and_provisional"] = mixed
    (B / "external_verification.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"regrade_mismatch": {k: v["regrade_mismatch"] for k, v in out["runs"].items()}, "holdout_integrity": {k: v for k, v in out["holdout_integrity"].items() if k != "dev_tuning_evidence"},
                      "duplicates": dup, "recomputed": {k: v for k, v in out["recomputed"].items() if k != "blind8_role"}, "mixed": mixed}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
