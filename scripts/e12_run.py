"""E12 실행: OfficeCLI vs 기존 파서 (openpyxl · E03 v2 python-docx · E03 v2 python-pptx) — 같은 원본·같은 정답·같은 채점기.

    .\\.venv\\Scripts\\python.exe scripts\\e12_run.py

- XLSX: 합성 시험 파일 X12-01 (생성 정답 data/canonical/e12/xlsx_truth_v1.json) + E02 업체 XLSX 2개(정답 없이 두 도구 일치도만)
- DOCX·PPTX: E03 합성 샘플 4개 (생성 정답, e03_grade_parsers) + 외부 문서 (잠정 정답, e03_grade_external) — holdout과 blind8·dev(v2 개발 사용)를 분리
- PDF: OfficeCLI 읽기 미지원 (view pdf는 내보내기) → NOT_SUPPORTED, 비교하지 않음
- 성능: 문서·방식별 3회 (자식 프로세스, 첫 실행과 반복 구분). 네트워크 감시는 별도 1회
- 결과: results/E12_officecli/ (합성 문서 기반만). 외부 문서 출력·사례는 data/raw/e12_officecli/ (Git 제외, D-025)
- 외부 API·유료 서비스 없음. 기존 결과·정답 수정 없음.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import e03_grade_external as GX  # noqa: E402
import e03_grade_parsers as GS  # noqa: E402
import e03_run_parsers as RP  # noqa: E402
import e12_officecli as O  # noqa: E402

OUT = ROOT / "results" / "E12_officecli"
RAW = ROOT / "data" / "raw" / "e12_officecli" / "outputs"
XLSX = ROOT / "data" / "e12" / "X12-01_orders.xlsx"
XTRUTH = ROOT / "data" / "canonical" / "e12" / "xlsx_truth_v1.json"
REPEATS = 3
EXT_TRUTH = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"
SPLITS = json.loads((ROOT / "configs" / "e03_external_splits.json").read_text(encoding="utf-8"))


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 4) if xs else None


def child(cmd: list[str]) -> dict:
    """자식 프로세스 1회: 시간·피크 RSS(런처+자식 합)."""
    t0 = time.perf_counter()
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=fo, stderr=fe)
        proc, peak = psutil.Process(p.pid), 0
        while p.poll() is None:
            try:
                peak = max(peak, proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True)))
            except psutil.Error:
                pass
            time.sleep(0.005)
        fo.seek(0)
        out = fo.read().decode("utf-8", "replace").strip().splitlines()
    try:
        res = json.loads(out[-1])
    except Exception:
        res = {"ok": False}
    res.update({"wall_s": time.perf_counter() - t0, "peak_rss_mb": round(peak / 1048576, 1), "returncode": p.returncode})
    return res


# ------------------------------------------------------------------ XLSX
def openpyxl_extract(path: Path) -> dict:
    import openpyxl
    from openpyxl.utils import get_column_letter
    wf = openpyxl.load_workbook(path, data_only=False)
    wv = openpyxl.load_workbook(path, data_only=True)
    cells, merges, hr, hc = {}, set(), set(), set()
    for ws in wf.worksheets:
        vs = wv[ws.title]
        for row in ws.iter_rows():
            for c in row:
                if c.value is None:
                    continue
                v = vs[c.coordinate].value
                cells[(ws.title, c.coordinate)] = {"value": v, "formula": c.value if c.data_type == "f" else None, "data_type": c.data_type,
                                                   "is_date": c.is_date, "number_format": c.number_format}
        merges |= {(ws.title, str(r)) for r in ws.merged_cells.ranges}
        hr |= {(ws.title, i) for i, d in ws.row_dimensions.items() if d.hidden}
        hc |= {(ws.title, k) for k, d in ws.column_dimensions.items() if d.hidden}
    return {"cells": cells, "merges": merges, "hidden_rows": hr, "hidden_cols": hc}


def norm_val(v):
    if v is None:
        return None
    if hasattr(v, "date") and hasattr(v, "hour"):
        return v.date().isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def xlsx_score(tool: str, x: dict, truth: dict) -> dict:
    """정답 셀별 판정. 지표 정의는 두 도구에 같게 적용한다 (도구별 해석 차이는 note)."""
    rows, K = [], {k: [0, 0] for k in ("value", "formula_text", "text_number_kept_as_text", "date_recognized", "blank_kept_blank", "invalid_kept_as_text")}
    for t in truth["cells"]:
        key = (t["sheet"], t["cell"])
        c = x["cells"].get(key)
        if tool == "openpyxl":
            got = norm_val(c["value"]) if c else None
            ftxt = (c or {}).get("formula")
            is_text = (c or {}).get("data_type") == "s"
            is_date = bool((c or {}).get("is_date"))
        else:
            pick = (c.get("cached") or c.get("text")) if tool == "officecli_cached_only" and c else ((c.get("computed") or c.get("cached") or c.get("text")) if c else None)
            got = None if c is None or c.get("text") in (None, "(empty)") and not c.get("formula") else pick
            ftxt = ("=" + c["formula"]) if c and c.get("formula") else None
            is_text = (c or {}).get("type") == "SharedString"
            is_date = bool(c and c.get("numberformat") and any(s in c["numberformat"].lower() for s in ("yy", "mm-dd", "dd")))
        want = None if t["kind"] == "blank" else (str(t["value"]) if not isinstance(t["value"], float) or not t["value"].is_integer() else str(int(t["value"])))
        if t["kind"] == "blank":
            K["blank_kept_blank"][1] += 1
            K["blank_kept_blank"][0] += got is None
            ok = got is None
        else:
            K["value"][1] += 1
            ok = got == want
            K["value"][0] += ok
        if t["kind"] == "formula":
            K["formula_text"][1] += 1
            K["formula_text"][0] += ftxt == t["formula"]
        if t["note"] == "number_stored_as_text":
            K["text_number_kept_as_text"][1] += 1
            K["text_number_kept_as_text"][0] += is_text
        if t["note"] == "invalid_number":
            K["invalid_kept_as_text"][1] += 1
            K["invalid_kept_as_text"][0] += is_text and got == want
        if t["kind"] == "date":
            K["date_recognized"][1] += 1
            K["date_recognized"][0] += is_date and got == want
        rows.append({"sheet": t["sheet"], "cell": t["cell"], "kind": t["kind"], "truth": want, "got": got, "ok": ok})
    tm = {(m["sheet"], m["range"]) for m in truth["merges"]}
    th = {(h["sheet"], h["row"]) for h in truth["hidden_rows"]}
    tc = {(h["sheet"], h["col"]) for h in truth["hidden_cols"]}
    out = {k: f"{a}/{b}" for k, (a, b) in K.items()}
    out.update({"merges": f"{len(tm & x['merges'])}/{len(tm)}", "false_merges": len(x["merges"] - tm),
                "hidden_rows": f"{len(th & x['hidden_rows'])}/{len(th)}", "hidden_cols": f"{len(tc & x['hidden_cols'])}/{len(tc)}"})
    return {"metrics": out, "wrong_cells": [r for r in rows if not r["ok"]]}


def xlsx_agreement(path: Path) -> dict:
    """정답 없는 E02 업체 XLSX: 두 도구가 같은 셀에서 같은 값을 내는지 (값 문자열 비교)."""
    a = openpyxl_extract(path)
    b = O.xlsx_cells(O.extract(path))
    keys = set(a["cells"]) | {k for k, v in b["cells"].items() if v.get("text") not in (None, "(empty)")}
    same, diff = 0, []
    for k in sorted(keys):
        va = norm_val(a["cells"][k]["value"]) if k in a["cells"] else None
        vb = b["cells"].get(k, {})
        vb = None if vb.get("text") in (None, "(empty)") else (vb.get("computed") or vb.get("cached") or vb.get("text"))
        if va == vb:
            same += 1
        else:
            diff.append({"sheet": k[0], "cell": k[1], "openpyxl": va, "officecli": vb})
    return {"file": path.relative_to(ROOT).as_posix(), "cells_compared": len(keys), "same": same, "differences": diff[:20], "n_diff": len(diff),
            "merges_equal": a["merges"] == b["merges"], "openpyxl_merges": len(a["merges"]), "officecli_merges": len(b["merges"])}


# ------------------------------------------------------------------ DOCX·PPTX
def baseline_ir(rel: str, fmt: str, save: Path) -> tuple[dict | None, dict]:
    parser = {"docx": "python-docx", "pptx": "python-pptx"}[fmt]
    r = child([sys.executable, str(ROOT / "scripts" / "e03_ext_parse_doc.py"), "v2", parser, rel, "--save", str(save)])
    ir = json.loads(save.read_text(encoding="utf-8")) if r.get("ok") and save.exists() else None
    return ir, r


def officecli_ir(rel: str, fmt: str, monitor: bool = True) -> tuple[dict | None, dict]:
    src = ROOT / rel
    t0 = time.perf_counter()
    ex = O.extract(src, monitor)
    t1 = time.perf_counter()
    ir = (O.docx_ir if fmt == "docx" else O.pptx_ir)(rel, src, ex) if ex["root"] is not None else None
    t2 = time.perf_counter()
    calls = ex["calls"]
    return ir, {"ok": ir is not None and all(c.get("ok", True) for c in calls), "batch_output": [c.get("batch_output") for c in calls if "batch_output" in c],
                "extract_s": t1 - t0, "convert_s": t2 - t1, "cli_calls": len(calls), "cli_wall_s": sum(c["wall_s"] for c in calls),
                "peak_rss_mb": max(c["peak_rss_mb"] for c in calls), "source_unchanged": all(c["source_unchanged"] for c in calls),
                "copy_rewritten_by_batch": any(c["copy_changed"] for c in calls), "returncodes": [c["returncode"] for c in calls]}


def flat(m: dict, prefix="") -> dict:
    out = {}
    for k, v in m.items():
        if isinstance(v, dict) and {"numerator", "denominator", "status"} <= set(v):
            out[prefix + k] = "미측정" if v["status"] == "NOT_MEASURED" else f"{v['numerator']}/{v['denominator']}"
        elif isinstance(v, dict):
            out.update(flat(v, prefix + k + "."))
        elif not isinstance(v, list):
            out[prefix + k] = v
    return out


def perf_doc(rel: str, fmt: str) -> dict:
    """같은 문서를 두 방식으로 각 3회. 첫 실행과 반복(2·3회) 중앙값을 따로 기록."""
    base, oc = [], []
    with tempfile.TemporaryDirectory() as td:
        for i in range(REPEATS):
            if fmt == "xlsx":
                base.append(child([sys.executable, str(Path(__file__)), "--openpyxl-child", rel]))
            else:
                base.append(baseline_ir(rel, fmt, Path(td) / f"b{i}.json")[1])
            if fmt == "xlsx":
                t0 = time.perf_counter()
                ex = O.extract(ROOT / rel, monitor=False)
                O.xlsx_cells(ex)
                oc.append({"ok": ex["root"] is not None, "wall_s": time.perf_counter() - t0, "peak_rss_mb": max(c["peak_rss_mb"] for c in ex["calls"]),
                           "cli_calls": len(ex["calls"])})
            else:
                _, r = officecli_ir(rel, fmt, monitor=False)
                oc.append({**r, "wall_s": r["extract_s"] + r["convert_s"]})
    s = lambda runs, k: {"first": round(runs[0].get(k), 4) if runs and runs[0].get(k) is not None else None, "repeat_median": med([x.get(k) for x in runs[1:]]),
                         "all_median": med([x.get(k) for x in runs])}
    return {"doc": rel, "format": fmt,
            "baseline": {"wall_s": s(base, "wall_s"), "parse_s": s(base, "parse_seconds"), "peak_rss_mb": med([x.get("peak_rss_mb") for x in base]),
                         "failed": sum(not x.get("ok") for x in base)},
            "officecli": {"wall_s": s(oc, "wall_s"), "convert_s": s(oc, "convert_s"), "peak_rss_mb": med([x.get("peak_rss_mb") for x in oc]),
                          "failed": sum(not x.get("ok") for x in oc), "cli_calls": oc[0].get("cli_calls") if oc else None}}


def network_check(paths: list[str]) -> dict:
    """감시 전용 실행 (시간 측정과 분리): 실행 중 프로세스의 원격 TCP 연결."""
    seen = {}
    for rel in paths:
        ex = O.extract(ROOT / rel)
        seen[rel] = sorted({a for c in ex["calls"] for a in c["remote_connections"]})
    return {"documents": len(paths), "with_remote_connection": {k: v for k, v in seen.items() if v}, "OFFICECLI_SKIP_UPDATE": "1"}


def main() -> int:
    if "--openpyxl-child" in sys.argv:
        rel = sys.argv[sys.argv.index("--openpyxl-child") + 1]
        t0 = time.perf_counter()
        openpyxl_extract(ROOT / rel)
        print(json.dumps({"ok": True, "parse_seconds": time.perf_counter() - t0}))
        return 0
    if OUT.exists() and any(OUT.iterdir()):
        raise SystemExit("results/E12_officecli에 결과가 이미 있음 → 덮어쓰지 않음")
    if O.sha(O.EXE) != O.EXE_SHA256:
        raise SystemExit("officecli 실행 파일 해시 불일치 → 중단")
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    res = {"pdf": {"status": "NOT_SUPPORTED", "reason": "OfficeCLI v1.0.157 읽기 대상은 .docx/.xlsx/.pptx (help: <file> Office document path). PDF는 view pdf 내보내기만"}}
    # XLSX
    truth = json.loads(XTRUTH.read_text(encoding="utf-8"))
    assert O.sha(XLSX) == truth["sha256"], "X12 파일 해시 불일치"
    xo, xc = openpyxl_extract(XLSX), O.xlsx_cells(O.extract(XLSX))
    nc = ROOT / truth["variant_no_formula_cache"]["file"]
    assert O.sha(nc) == truth["variant_no_formula_cache"]["sha256"], "X12-02 파일 해시 불일치"
    yo, yc = openpyxl_extract(nc), O.xlsx_cells(O.extract(nc))
    res["xlsx"] = {"X12-01": {"openpyxl": xlsx_score("openpyxl", xo, truth), "officecli": xlsx_score("officecli", xc, truth)},
                   "X12-02_no_formula_cache": {"openpyxl": xlsx_score("openpyxl", yo, truth), "officecli": xlsx_score("officecli", yc, truth),
                                               "officecli_cached_only": xlsx_score("officecli_cached_only", yc, truth)},
                   "e02_vendor_agreement": [xlsx_agreement(ROOT / p) for p in ("data/vendor_a/vendor_a_master.xlsx", "data/vendor_b/vendor_b_master.xlsx")]}
    print("xlsx", {f: {k: v["metrics"]["value"] for k, v in res["xlsx"][f].items()} for f in ("X12-01", "X12-02_no_formula_cache")}, flush=True)
    # 합성 DOCX·PPTX
    docs = [d for d in RP.verify_inputs() if d["format"] in ("docx", "pptx")]
    st, locs = GS.load_truth()
    syn = []
    for d in docs:
        bir, brun = baseline_ir(d["file"], d["format"], OUT / "outputs" / "synthetic" / f"{d['doc_id']}__v2.json")
        oir, orun = officecli_ir(d["file"], d["format"])
        (OUT / "outputs" / "synthetic" / f"{d['doc_id']}__officecli.json").write_text(json.dumps(oir, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        syn.append({"doc_id": d["doc_id"], "format": d["format"], "truth": "GENERATED (E03 생성 정답)",
                    "baseline_v2": flat(GS.grade(bir, d, st, locs)), "officecli": flat(GS.grade(oir, d, st, locs)),
                    "officecli_run": orun, "officecli_diagnostics": [x["message"] for x in (oir or {}).get("diagnostics", [])]})
        print("synthetic", d["doc_id"], flush=True)
    res["synthetic"] = syn
    # 외부 DOCX·PPTX (잠정 정답)
    xt = {x["doc_id"]: x for x in json.loads(EXT_TRUTH.read_text(encoding="utf-8"))["documents"]} if EXT_TRUTH.exists() else {}
    ext = []
    for split in ("holdout", "blind8", "dev"):
        for did in SPLITS[split]:
            d = xt.get(did)
            if not d or d["format"] not in ("docx", "pptx"):
                continue
            rel = f"data/raw/external_documents/{d['format']}/{d['file']}"
            if not (ROOT / rel).exists() or O.sha(ROOT / rel) != d["sha256"]:
                ext.append({"doc_id": did, "split": split, "status": "NOT_MEASURED", "reason": "입력 없음·해시 불일치"})
                continue
            bir, _ = baseline_ir(rel, d["format"], RAW / f"{did}__v2.json")
            oir, orun = officecli_ir(rel, d["format"])
            (RAW / f"{did}__officecli.json").write_text(json.dumps(oir, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            ext.append({"doc_id": did, "split": split, "format": d["format"], "truth": "PROVISIONAL (잠정 정답, 사람 검수 없음)",
                        "baseline_v2": flat(GX.grade(bir, d).get("metrics", {})), "officecli": flat(GX.grade(oir, d).get("metrics", {})),
                        "officecli_run": orun, "officecli_diagnostics": sorted({x["message"] for x in (oir or {}).get("diagnostics", [])})})
            print("external", split, did, flush=True)
    res["external"] = ext
    # 성능 (3회)
    perf_paths = [("data/e12/X12-01_orders.xlsx", "xlsx"), ("data/vendor_b/vendor_b_master.xlsx", "xlsx")] + [(d["file"], d["format"]) for d in docs] + \
                 [(f"data/raw/external_documents/{xt[i]['format']}/{xt[i]['file']}", xt[i]["format"]) for i in SPLITS["holdout"] if i in xt and xt[i]["format"] in ("docx", "pptx")]
    res["perf"] = [perf_doc(p, f) for p, f in perf_paths]
    res["network"] = network_check([p for p, _ in perf_paths])
    meta = {"experiment_id": "E12", "status": "RUNNING", "run_timestamp": started, "officecli": {"version": O.VERSION, "sha256": O.EXE_SHA256, "source": "GitHub Release v1.0.157 (officecli-win-x64.exe)",
                                                                                                "signed": False, "license": "Apache-2.0", "env": "OFFICECLI_SKIP_UPDATE=1"},
            "baseline": {"xlsx": "openpyxl " + __import__("openpyxl").__version__, "docx": "E03 v2 python-docx", "pptx": "E03 v2 python-pptx"},
            "python": sys.version.split()[0], "external_calls": "none (paid API 0)", "repeats": REPEATS}
    # 실행 후 입력 불변 재확인 (탐색 중 원본에 직접 batch를 실행해 T-01이 바뀐 사고가 있었음 — 보고서 기록)
    RP.verify_inputs()
    changed = [d["doc_id"] for d in xt.values() if (ROOT / f"data/raw/external_documents/{d['format']}/{d['file']}").exists()
               and O.sha(ROOT / f"data/raw/external_documents/{d['format']}/{d['file']}") != d["sha256"]]
    for p, h in ((XLSX, truth["sha256"]), (nc, truth["variant_no_formula_cache"]["sha256"])):
        if O.sha(p) != h:
            changed.append(p.name)
    if changed:
        raise SystemExit(f"실행 후 입력 문서가 바뀜 → 결과 무효: {changed}")
    meta["inputs_unchanged_after_run"] = True
    for name, obj in (("results.json", res), ("run_meta.json", meta)):
        (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print("done", json.dumps(res["network"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
