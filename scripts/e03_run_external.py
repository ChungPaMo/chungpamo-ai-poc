"""E03 외부 문서 평가 실행: 해시 검증 → 파싱 3회 반복(첫 실행 출력 보존) + 메모리 3회 → 독립 채점 → 결과 기록.

    .\\.venv\\Scripts\\python.exe scripts\\e03_run_external.py --version v1 --set blind8 --out external_baseline_v1

- 결과 폴더가 이미 있으면 중단한다 (최초 블라인드 결과 덮어쓰기 방지). 첫 실행 IR은 읽기 전용으로 둔다.
- 외부 문서 텍스트가 담긴 IR·정규화 출력은 <out>/outputs/ (Git 제외, D-025). 공개 후보 파일에는 텍스트를 쓰지 않는다.
- v1 = 커밋 34293ad의 src/parsers/doc_*.py (실행 전 Git blob 해시 대조), v2 = src/parsers/v2/.
- Upstage·외부 API 호출 없음.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import stat
import statistics
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_environment as ce  # noqa: E402
import e03_grade_external as G  # noqa: E402

TRUTH = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"
TRUTH_MANIFEST = ROOT / "results" / "E03_document_parsers" / "external_truth_v1" / "truth_manifest.json"
SPLITS = ROOT / "configs" / "e03_external_splits.json"
SOURCES = ROOT / "configs" / "e03_external_sources.json"
V1_COMMIT = "34293ad79c796fc5903ff336c93d52f5d5399b28"
V1_FILES = ["src/parsers/doc_common.py", "src/parsers/doc_docx.py", "src/parsers/doc_pdf.py", "src/parsers/doc_pptx.py", "src/parsers/doc_registry.py"]
PARSERS_FOR = {"docx": ["python-docx"], "pptx": ["python-pptx"], "pdf": ["pypdf", "pdfplumber"]}
REPEATS = 3
CHILD_TIMEOUT_S = 600


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def code_hashes(version: str) -> dict:
    if version == "v1":
        rows = {}
        for f in V1_FILES:
            work = git("hash-object", f)
            commit_blob = git("ls-tree", V1_COMMIT, f).split()[2]
            rows[f] = {"git_blob_worktree": work, "git_blob_at_34293ad": commit_blob, "same": work == commit_blob}
        if not all(r["same"] for r in rows.values()):
            raise SystemExit(f"v1 파서 코드가 커밋 {V1_COMMIT[:7]}와 다름 → 중단: {rows}")
        return {"commit": V1_COMMIT, "files": rows}
    files = sorted((ROOT / "src" / "parsers" / "v2").glob("*.py")) + [ROOT / "src" / "parsers" / f for f in ("doc_common.py", "doc_docx.py", "doc_pdf.py", "doc_pptx.py")]
    return {"commit": git("rev-parse", "HEAD") + " (+ 커밋 안 된 v2 코드)", "files": {f.relative_to(ROOT).as_posix(): sha(f.read_bytes()) for f in files}}


def child(version, parser, rel, trace=False, save=None) -> dict:
    cmd = [sys.executable, str(ROOT / "scripts" / "e03_ext_parse_doc.py"), version, parser, rel] + (["--trace-mem"] if trace else []) + (["--save", str(save)] if save else [])
    # stdout·stderr를 임시 파일로 받는다: 파서 라이브러리 경고가 stderr 파이프를 채우면 자식이 멈추는 문제 방지 (2026-10-20 dev 실행에서 발생)
    import tempfile
    t0 = time.perf_counter()
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=fo, stderr=fe)
        proc, peak, timed_out = psutil.Process(p.pid), 0, False
        while p.poll() is None:
            try:
                peak = max(peak, proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True)))
            except psutil.Error:
                pass
            if time.perf_counter() - t0 > CHILD_TIMEOUT_S:
                for c in proc.children(recursive=True):
                    c.kill()
                p.kill()
                timed_out = True
                break
            time.sleep(0.005)
        p.wait()
        fo.seek(0)
        fe.seek(0)
        out, err = fo.read(), fe.read()
    try:
        res = json.loads(out.decode("utf-8").strip().splitlines()[-1])
    except Exception:
        res = {"ok": False, "error_type": "Timeout" if timed_out else "ChildCrash",
               "error": f"{CHILD_TIMEOUT_S}s 초과" if timed_out else ce.mask_sensitive(err.decode("utf-8", "replace")[-400:])}
    res.update({"process_wall_seconds": time.perf_counter() - t0, "peak_rss_bytes": peak, "returncode": p.returncode,
                "stderr_lines": len(err.decode("utf-8", "replace").splitlines())})
    return res


def normalized_view(ir: dict) -> dict:
    return {"blocks": [{"id": b["block_id"], "type": b["type"], "text": G.norm(b["text"]), "loc": {k: v for k, v in b["location"].items() if k in ("page", "part", "slide_index", "shape_id", "body_index")}}
                       for b in ir["blocks"]],
            "tables": [{"id": t["table_id"], "n_rows": t["n_rows"], "n_cols": t["n_cols"], "loc": {k: v for k, v in t["location"].items() if k in ("page", "slide_index", "shape_id", "table_index", "bbox")},
                        "grid": [[r, c["col"], c["rowspan"], c["colspan"], G.norm(c["text"])] for c in t["cells"] for r in [c["row"]]]} for t in ir["tables"]]}


def flatten(d, prefix=""):
    for k, v in d.items():
        if isinstance(v, dict) and {"numerator", "denominator", "status"} <= set(v):
            yield prefix + k, ("미측정" if v["status"] == "NOT_MEASURED" else f"{v['numerator']}/{v['denominator']}"), v
        elif isinstance(v, dict):
            yield from flatten(v, prefix + k + ".")
        elif not isinstance(v, list):
            yield prefix + k, v, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["v1", "v2"], required=True)
    ap.add_argument("--set", choices=["blind8", "dev", "holdout"], required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = ROOT / "results" / "E03_document_parsers" / a.out
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} 이미 있음 — 기존 평가 결과를 덮어쓰지 않는다")
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    log = [f"[{started}] start version={a.version} set={a.set}"]
    truth_blob = TRUTH.read_bytes()
    tm = json.loads(TRUTH_MANIFEST.read_text(encoding="utf-8"))
    if sha(truth_blob) != tm["truth_sha256"]:
        raise SystemExit("정답 파일 해시가 고정값과 다름 → 중단")
    truth = {d["doc_id"]: d for d in json.loads(truth_blob)["documents"]}
    ids = json.loads(SPLITS.read_text(encoding="utf-8"))[a.set]
    src = {s["id"]: s for s in json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]}
    codes = code_hashes(a.version)
    (out / "outputs" / "first_run").mkdir(parents=True)
    (out / "outputs" / "normalized").mkdir(parents=True)
    runs, inputs = [], []
    for did in ids:
        d = truth[did]
        rel = f"data/raw/external_documents/{d['format']}/{d['file']}"
        p = ROOT / rel
        actual = sha(p.read_bytes()) if p.exists() else None
        inputs.append({"doc_id": did, "file": d["file"], "sha256": actual, "matches_truth_record": actual == d["sha256"]})
        if actual != d["sha256"]:
            log.append(f"{did}: 입력 없음 또는 해시 불일치 → 미측정 (대체하지 않음)")
            for parser in PARSERS_FOR[d["format"]]:
                runs.append({"doc_id": did, "parser": parser, "grade": {"doc_id": did, "status": "NOT_MEASURED", "reason": "입력 해시 불일치·없음"}, "perf": None})
            continue
        for parser in PARSERS_FOR[d["format"]]:
            save = out / "outputs" / "first_run" / f"{did}__{parser}.json"
            r1 = child(a.version, parser, rel, save=save)
            t_runs = [r1] + [child(a.version, parser, rel) for _ in range(REPEATS - 1)]
            m_runs = [child(a.version, parser, rel, trace=True) for _ in range(REPEATS)]
            ok = r1.get("ok")
            log.append(f"{did} {parser}: run1 ok={ok} " + ("" if ok else f"{r1.get('error_type')}: {r1.get('error')} @ {r1.get('where')}"))
            ir = json.loads(save.read_text(encoding="utf-8")) if ok and save.exists() else None
            if ir is not None:
                os.chmod(save, stat.S_IREAD)
                (out / "outputs" / "normalized" / save.name).write_text(json.dumps(normalized_view(ir), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            digests = {r.get("ir_sha256") for r in t_runs + m_runs if r.get("ok")}
            perf = {"ok_runs": sum(bool(r.get("ok")) for r in t_runs + m_runs), "total_runs": len(t_runs + m_runs),
                    "output_identical_across_runs": len(digests) == 1 and all(r.get("ok") for r in t_runs + m_runs),
                    "first_run_ir_sha256": r1.get("ir_sha256"),
                    "parse_seconds": [r.get("parse_seconds") for r in t_runs], "import_seconds": [r.get("import_seconds") for r in t_runs],
                    "peak_rss_mb": [round(r["peak_rss_bytes"] / 1048576, 1) for r in t_runs],
                    "py_heap_peak_mb": [round((r.get("py_heap_peak_bytes") or 0) / 1048576, 3) for r in m_runs],
                    "errors": sorted({f"{r.get('error_type')}: {r.get('error')} @ {r.get('where')}" for r in t_runs + m_runs if not r.get("ok")}),
                    "stderr_lines_first_run": r1.get("stderr_lines")}
            runs.append({"doc_id": did, "parser": parser, "grade": G.grade(ir, d), "perf": perf})
    write_results(out, a, started, codes, inputs, runs, tm, log)
    print(json.dumps({"out": out.relative_to(ROOT).as_posix(), "runs": [(r["doc_id"], r["parser"], r["grade"]["status"]) for r in runs]}, ensure_ascii=False))
    return 0


def med(xs, fmt="{:.4f}"):
    xs = [x for x in xs if x is not None]
    return fmt.format(statistics.median(xs)) if len(xs) == REPEATS else "측정실패"


def write_results(out, a, started, codes, inputs, runs, tm, log):
    rows = []
    for r in runs:
        g, p = r["grade"], r["perf"]
        row = {"doc_id": r["doc_id"], "parser": r["parser"], "status": g["status"], "reason": g.get("reason", "")}
        if g["status"] == "MEASURED":
            for k, v, _ in flatten(g["metrics"]):
                row[k] = v
        if p:
            row.update({"parse_s_median": med(p["parse_seconds"]), "import_s_median": med(p["import_seconds"]),
                        "peak_rss_mb_median": med(p["peak_rss_mb"], "{:.1f}"), "py_heap_mb_median": med(p["py_heap_peak_mb"], "{:.3f}"),
                        "ok_runs": f"{p['ok_runs']}/{p['total_runs']}", "output_identical": p["output_identical_across_runs"]})
        rows.append(row)
    cols = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", restval="")
    w.writeheader()
    w.writerows(rows)
    (out / "metrics.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    (out / "grading.json").write_text(json.dumps({"definition": G.__doc__, "results": runs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    from importlib.metadata import version as v
    meta = {"experiment": "E03 외부 문서 평가", "status": "RUNNING", "parser_version": a.version, "set": a.set, "run_timestamp": started,
            "python": sys.version.split()[0], "packages": {p: v(p) for p in ("python-docx", "python-pptx", "pypdf", "pdfplumber", "pdfminer.six", "lxml", "pypdfium2")},
            "code": codes, "grader_sha256": sha((ROOT / "scripts" / "e03_grade_external.py").read_bytes()),
            "truth": {"file": tm["truth_file"], "sha256": tm["truth_sha256"], "manual_review_performed": tm["manual_review_performed"]},
            "inputs": inputs, "repeats": REPEATS, "git_head": git("rev-parse", "HEAD"),
            "measurement": "자식 프로세스: parse_seconds(파일 열기~IR), import_seconds, 피크 RSS(런처+인터프리터, 5ms 폴링), tracemalloc Python 힙 피크(별도 3회). 첫 실행 IR만 채점",
            "upstage_api_calls": 0}
    (out / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    log.append(f"[{dt.datetime.now().astimezone().isoformat(timespec='seconds')}] done")
    (out / "run_log.txt").write_text(ce.mask_sensitive("\n".join(log)) + "\n", encoding="utf-8", newline="\n")
    man = {p.relative_to(out).as_posix(): sha(p.read_bytes()) for p in sorted(out.rglob("*")) if p.is_file()}
    (out / "sha256_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
