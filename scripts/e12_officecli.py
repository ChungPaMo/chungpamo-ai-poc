"""E12 OfficeCLI 실행·변환 모듈 — OfficeCLI(iOfficeAI) 읽기 명령의 JSON 출력을 E03 공통 IR 0.2로 바꾼다 (DOCX·PPTX), XLSX는 셀 사전으로.

- 실행 파일: 로컬 앱 데이터 폴더의 officecli v1.0.157 (GitHub Release, SHA256SUMS 일치 확인). 저장소에 넣지 않는다.
- 항상 OFFICECLI_SKIP_UPDATE=1 (소스 확인: 이 값이면 업데이트 확인 HTTP 요청을 하지 않음).
- 원본은 건드리지 않는다: 임시 복사본에서 실행하고, 실행 전후 원본 해시를 비교한다.
- 읽기 명령만 사용: get, query, batch(조회 명령만). 실행 중 외부 TCP 연결을 psutil로 감시해 기록한다.
- 변환 규칙: OfficeCLI가 주지 않는 정보는 만들지 않는다 (예: SmartArt 텍스트 — get/view에 없음 → 진단 메모만).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from parsers.doc_common import link_fragments  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.157"
EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "chungpamo-tools" / "officecli" / f"v{VERSION}" / "officecli.exe"
EXE_SHA256 = "bd64eba587e56cc71709cdd1f38ae9ac77cd65a9c8ea744b0996897c0557e343"
ENV = {**os.environ, "OFFICECLI_SKIP_UPDATE": "1"}


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(args: list[str], src: Path, monitor: bool = True) -> dict:
    """원본의 임시 복사본에 officecli를 실행. 반환: stdout JSON, 시간, 피크 RSS, 외부 연결, 원본 해시 변화.
    monitor=False: 외부 연결 감시(net_connections 폴링)를 끈다 — 폴링 비용이 시간에 섞이지 않게 성능 측정에서 사용."""
    h0 = sha(src)
    td = Path(tempfile.mkdtemp(prefix="e12_"))
    cp = td / src.name
    shutil.copy2(src, cp)
    cmd = [str(EXE)] + [str(cp) if a == "{file}" else a for a in args]
    t0 = time.perf_counter()
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        p = subprocess.Popen(cmd, stdout=fo, stderr=fe, env=ENV)
        proc, peak, remote = psutil.Process(p.pid), 0, set()
        while p.poll() is None:
            try:
                peak = max(peak, proc.memory_info().rss)
                for c in (proc.net_connections(kind="inet") if monitor else ()):
                    if c.raddr:
                        remote.add(f"{c.raddr.ip}:{c.raddr.port}")
            except psutil.Error:
                pass
            time.sleep(0.003)
        wall = time.perf_counter() - t0
        fo.seek(0)
        fe.seek(0)
        out, err = fo.read().decode("utf-8", "replace"), fe.read().decode("utf-8", "replace")
    copy_changed = sha(cp) != h0
    shutil.rmtree(td, ignore_errors=True)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {"success": False, "error": {"error": "JSON 아님", "code": "not_json"}, "stdout_head": out[:200]}
    return {"data": data, "wall_s": wall, "peak_rss_mb": round(peak / 1048576, 1), "returncode": p.returncode, "remote_connections": sorted(remote) if monitor else "미측정",
            "source_unchanged": sha(src) == h0, "copy_changed": copy_changed, "stderr_lines": len(err.splitlines())}


def batch(src: Path, cmds: list[dict], monitor: bool = True) -> dict:
    """조회 명령만 담은 batch 1회. batch 결과 파일(사용자 임시 폴더)은 읽고 바로 지운다 (경로는 기록하지 않음)."""
    td = Path(tempfile.mkdtemp(prefix="e12c_"))
    f = td / "cmds.json"
    f.write_text(json.dumps(cmds, ensure_ascii=False), encoding="utf-8")
    assert all(c["command"] in ("get", "query") for c in cmds), "조회 명령만 허용"
    r = run(["batch", "{file}", "--input", str(f), "--json"], src, monitor)
    shutil.rmtree(td, ignore_errors=True)
    outs = []
    d = r["data"]
    if d.get("success") and d.get("data", {}).get("outputFile"):
        of = Path(d["data"]["outputFile"])
        try:
            outs = json.loads(of.read_text(encoding="utf-8"))["results"]
        finally:
            of.unlink(missing_ok=True)
    elif d.get("success") and isinstance(d.get("data", {}).get("results"), list):
        outs = d["data"]["results"]                  # 결과가 작으면 파일 대신 stdout에 바로 담김
    r["batch_output"] = "file" if d.get("data", {}).get("outputFile") else ("inline" if outs else "none")
    if len(outs) != len(cmds):
        r["ok"] = False
    r["outputs"] = [o.get("output") if o.get("success") else {"error": o.get("error")} for o in outs]
    r.pop("data")
    return r


def results(out) -> list[dict]:
    return (out or {}).get("results", []) if isinstance(out, dict) else []


def extract(src: Path, monitor: bool = True) -> dict:
    """문서 1개 추출 = officecli 2회 실행 (① 루트 구조 ② 필요한 부분 batch). 실행 기록과 원시 노드를 돌려준다."""
    fmt = src.suffix.lower().lstrip(".")
    r1 = run(["get", "{file}", "/", "--json"], src, monitor)
    calls = [r1]
    root = results(r1["data"].get("data"))[0] if r1["data"].get("success") else None
    parts = {}
    if root is not None:
        kids = [c["path"] for c in root.get("children", [])]
        if fmt == "docx":
            want = [p for p in kids if p == "/body" or p.startswith("/header") or p.startswith("/footer")]
            # get은 블록 sdt 안으로 내려가지 않음(children 빈 목록) → query paragraph로 sdt 안 문단을 보완
            cmds = [{"command": "get", "path": p, "depth": 30} for p in want] + [{"command": "query", "selector": s} for s in ("footnote", "endnote", "paragraph")]
        elif fmt == "pptx":
            want = [p for p in kids if p.startswith("/slide[")]
            cmds = [{"command": "get", "path": p, "depth": 30} for p in want] + [{"command": "query", "selector": "notes"}]
        else:
            want = [p for p in kids if p.count("/") == 1 and not p.startswith("/workbook")]
            cmds = [{"command": "get", "path": p, "depth": 3} for p in want] + [{"command": "query", "selector": "column"}]
        r2 = batch(src, cmds, monitor)
        calls.append(r2)
        for c, o in zip(cmds, r2["outputs"]):
            parts[c.get("path") or ("query:" + c["selector"])] = o
    return {"format": fmt, "root": root, "parts": parts, "calls": [{k: v for k, v in c.items() if k not in ("data", "outputs")} for c in calls]}


# ------------------------------------------------------------------ DOCX → IR
def _grid(rows, span_key="colspan", mode="docx"):
    """OfficeCLI 표 행 → IR 셀 (1부터). docx: tc가 gridSpan 열을 차지, vmerge=continue는 위 앵커 rowspan 증가.
    pptx: colspan/rowspan이 앵커에 있고 hmerge/vmerge=true 셀은 덮인 셀."""
    cells, anchors, n_cols = [], {}, 0
    for r, row in enumerate(rows, 1):
        c = 1
        for tc in [x for x in row.get("children", []) if x["type"] in ("cell", "tc")]:
            f = tc.get("format", {})
            span = int(f.get(span_key) or 1)
            if mode == "pptx" and (str(f.get("hmerge")).lower() == "true" or str(f.get("vmerge")).lower() == "true"):
                c += 1
                continue
            if mode == "docx" and f.get("vmerge") == "continue":
                a = anchors.get(c)
                if a is not None:
                    a["rowspan"] += 1
                c += span
                continue
            paras = [p for p in tc.get("children", []) if p["type"] == "paragraph"]
            text = "\n".join(p.get("text") or "" for p in paras) if len(paras) > 1 else (tc.get("text") or "")   # 셀 text는 문단을 구분 없이 이어붙임
            cell = {"row": r, "col": c, "rowspan": int(f.get("rowspan") or 1) if mode == "pptx" else 1, "colspan": span, "text": text,
                    "raw": tc.get("text") or "", "is_header": False, "location": {"officecli_path": tc["path"]}}
            cells.append(cell)
            if mode == "docx":
                for k in range(c, c + span):
                    anchors[k] = cell if f.get("vmerge") == "restart" else None
            c += span if mode == "docx" else 1     # pptx: 덮인 셀도 tc로 남으므로 tc 하나 = 격자 1열
        n_cols = max(n_cols, c - 1)
    return cells, len(rows), n_cols


def docx_ir(rel: str, src: Path, ex: dict) -> dict:
    blocks, tables, seq = [], [], []
    nb = [0]

    def block(text, typ, loc):
        nb[0] += 1
        bid = f"b{nb[0]:04d}"
        blocks.append({"block_id": bid, "type": typ, "order": len(seq), "text": text, "location": {"format": "docx", **loc}, "level": None, "style": None})
        seq.append(bid)

    def table(node, loc):
        rows = [x for x in node.get("children", []) if x["type"] == "row"]
        cells, nr, nc = _grid(rows, mode="docx")
        tid = f"t{len(tables) + 1:03d}"
        for c in cells:
            c["location"] = {"format": "docx", **loc, "row": c["row"], "col": c["col"], "officecli_path": c["location"]["officecli_path"]}
        tables.append({"table_id": tid, "location": {"format": "docx", **loc, "officecli_path": node["path"]}, "n_rows": nr, "n_cols": nc, "header_rows": None,
                       "continuation": None, "caption_block_id": None, "detection": "native", "cells": cells})
        seq.append(tid)

    body = (results(ex["parts"].get("/body")) or [{}])[0]
    qpar = results(ex["parts"].get("query:paragraph"))
    diag = []
    bidx, tidx = 0, 0

    def walk_body(node, inside_sdt=False):
        nonlocal bidx, tidx
        t = node["type"]
        if t == "paragraph":
            style = (node.get("style") or "")
            block(node.get("text") or "", "heading" if style.lower().startswith(("heading", "title")) else "paragraph",
                  {"part": "body", "body_index": bidx, "officecli_path": node["path"]})
            if not inside_sdt:
                bidx += 1
        elif t == "table":
            table(node, {"part": "body", "body_index": bidx, "table_index": tidx})
            tidx += 1
            if not inside_sdt:
                bidx += 1
        elif t == "sdt":
            if node.get("children"):
                for c in node["children"]:
                    walk_body(c, True)
            else:
                sid = (node.get("format") or {}).get("id")
                pre = f"/body/sdt[@sdtId={sid}]/p[" if sid is not None else node["path"] + "/p["
                paras = [q for q in qpar if q["path"].startswith(pre)]
                for q in paras:
                    block(q.get("text") or "", "paragraph", {"part": "body", "body_index": bidx, "officecli_path": q["path"]})
                if not paras and (node.get("text") or "").strip():
                    block(node["text"], "paragraph", {"part": "body", "body_index": bidx, "officecli_path": node["path"]})
                    diag.append({"code": "EXT-SDT-TEXT-ONLY", "severity": "warning", "location": {"officecli_path": node["path"]}, "field": None,
                                 "message": "sdt 안 문단·표를 get/query paragraph로 받지 못해 sdt의 이어붙인 text로 대체", "raw": None})
            if not inside_sdt:
                bidx += 1

    for ch in body.get("children", []):
        walk_body(ch)
    for path, out in ex["parts"].items():
        m = re.match(r"/(header|footer)\[(\d+)\]", path)
        if m:
            node = (results(out) or [{}])[0]
            paras = [x for x in node.get("children", []) if x["type"] == "paragraph"]
            # 문단 text에는 fldSimple 필드 결과(쪽 번호 등)가 빠지고 part text에만 들어 있음 → 문단이 하나면 part text 사용
            one = len(paras) == 1 and (node.get("text") or "") != (paras[0].get("text") or "")
            for k, p in enumerate(paras):
                block(node["text"] if one else (p.get("text") or ""), m.group(1), {"part": m.group(1), "section_index": 0, "paragraph_index": k, "officecli_path": p["path"]})
    for sel, part in (("query:footnote", "footnotes"), ("query:endnote", "endnotes")):
        for k, n in enumerate(results(ex["parts"].get(sel))):
            block(n.get("text") or "", "footnote", {"part": part, "paragraph_index": k, "officecli_path": n["path"]})
    sections = sum(1 for c in body.get("children", []) if c["type"] == "section")
    return _ir(rel, src, "docx", {"sections": sections}, blocks, tables, seq, diag)


# ------------------------------------------------------------------ PPTX → IR
TEXT_TYPES = {"textbox", "title", "placeholder", "shape", "connector"}


def pptx_ir(rel: str, src: Path, ex: dict) -> dict:
    blocks, tables, seq, diag = [], [], [], []
    slides = sorted((p for p in ex["parts"] if p.startswith("/slide[")), key=lambda p: int(re.search(r"\d+", p).group()))

    def walk(node, si, names):
        f = node.get("format", {})
        name = f.get("name") or node["type"]
        loc = {"format": "pptx", "part": "slide", "slide_index": si, "shape_id": int(f["id"]) if str(f.get("id", "")).isdigit() else None, "shape_name": name,
               "nested_path": names + [name], "officecli_path": node["path"]}
        t = node["type"]
        if t == "group":
            for c in node.get("children", []):
                walk(c, si, names + [name])
        elif t in TEXT_TYPES and (node.get("text") or "").strip():
            bid = f"b{len(blocks) + 1:04d}"
            blocks.append({"block_id": bid, "type": "slide_title" if t == "title" or f.get("isTitle") is True else "slide_body", "order": len(seq),
                           "text": node.get("text") or "", "location": loc, "level": None, "style": None})
            seq.append(bid)
        elif t == "table":
            rows = [x for x in node.get("children", []) if x["type"] in ("tr", "row")]
            cells, nr, nc = _grid(rows, mode="pptx")
            for c in cells:
                c["location"] = {"format": "pptx", "part": "slide", "slide_index": si, "shape_id": loc["shape_id"], "row": c["row"], "col": c["col"],
                                 "officecli_path": c["location"]["officecli_path"]}
            tid = f"t{len(tables) + 1:03d}"
            tables.append({"table_id": tid, "location": loc, "n_rows": nr, "n_cols": nc, "header_rows": None, "continuation": None, "caption_block_id": None,
                           "detection": "native", "cells": cells})
            seq.append(tid)
        elif t == "chart":
            texts = [str(v) for k, v in f.items() if k == "title" or k == "categories" or re.fullmatch(r"dataLabel\d+\.text", k)]
            texts += [str(c.get("format", {}).get("name") or c.get("text") or "") for c in node.get("children", []) if c["type"] == "series"]
            if any(x.strip() for x in texts):
                bid = f"b{len(blocks) + 1:04d}"
                blocks.append({"block_id": bid, "type": "other", "order": len(seq), "text": " ".join(x for x in texts if x), "location": {**loc, "element": "chart"},
                               "level": None, "style": None})
                seq.append(bid)
        elif t == "smartart":
            diag.append({"code": "EXT-UNSUPPORTED", "severity": "warning", "location": loc, "field": None,
                         "message": "OfficeCLI get/view가 SmartArt 노드 텍스트를 주지 않음 (raw XML로만 접근)", "raw": None})
        for c in node.get("children", []) if t not in ("group", "table") else []:
            if c["type"] in TEXT_TYPES | {"group", "table", "chart", "smartart"}:
                walk(c, si, names + [name])

    for p in slides:
        si = int(re.search(r"\d+", p).group())
        node = (results(ex["parts"][p]) or [{}])[0]
        for c in node.get("children", []):
            walk(c, si, [])
    for n in results(ex["parts"].get("query:notes")):
        m = re.match(r"/slide\[(\d+)\]/notes", n["path"])
        if m and (n.get("text") or "").strip():
            bid = f"b{len(blocks) + 1:04d}"
            blocks.append({"block_id": bid, "type": "speaker_notes", "order": len(seq), "text": n["text"],
                           "location": {"format": "pptx", "part": "notes", "slide_index": int(m.group(1)), "officecli_path": n["path"]}, "level": None, "style": None})
            seq.append(bid)
    ir = _ir(rel, src, "pptx", {"slides": len(slides)}, blocks, tables, seq, diag)
    link_fragments(ir, "slide_index")          # E03 v2 pptx와 같은 공통 후처리 규칙 (OfficeCLI 기능 아님)
    return ir


def _ir(rel, src, fmt, units, blocks, tables, seq, diag):
    return {"schema": "chungpamo.parse_ir", "schema_version": "0.2",
            "document": {"source_file": rel, "format": fmt, "sha256": sha(src), "bytes": src.stat().st_size, "units_of_division": units},
            "parser": {"name": "officecli", "version": VERSION, "mode": "direct", "options": {"commands": "get/query/batch (read only)"}, "api_calls": 0},
            "blocks": blocks, "tables": tables, "extracted_values": [], "records": [], "diagnostics": diag,
            "format_specific": {"reading_sequence": seq, "location_index_base": {"slide_index": 1, "row": 1, "col": 1, "body_index": 0}}}


# ------------------------------------------------------------------ XLSX → 셀 사전
def xlsx_cells(ex: dict) -> dict:
    cells, merges, hidden_rows = {}, set(), set()
    for path, out in ex["parts"].items():
        if path.startswith("query:"):
            continue
        sheet = path.strip("/")
        node = (results(out) or [{}])[0]
        for row in node.get("children", []):
            rf = row.get("format", {})
            rn = int(re.search(r"\d+", row["path"].split("/")[-1]).group())
            if rf.get("hidden"):
                hidden_rows.add((sheet, rn))
            for c in row.get("children", []):
                f = c.get("format", {})
                ref = c["path"].split("/")[-1]
                cells[(sheet, ref)] = {"text": c.get("text"), "type": f.get("type"), "formula": f.get("formula"), "cached": f.get("cachedValue"),
                                       "computed": f.get("computedValue"), "numberformat": f.get("numberformat"), "merge": f.get("merge"), "anchor": f.get("mergeAnchor")}
                if f.get("merge") and f.get("mergeAnchor"):
                    merges.add((sheet, f["merge"]))
    hidden_cols = set()
    for n in results(ex["parts"].get("query:column")):
        if n.get("format", {}).get("hidden"):
            m = re.match(r"/([^/]+)/col\[([A-Z]+)\]", n["path"])
            if m:
                hidden_cols.add((m.group(1), m.group(2)))
    return {"cells": cells, "merges": merges, "hidden_rows": hidden_rows, "hidden_cols": hidden_cols}
