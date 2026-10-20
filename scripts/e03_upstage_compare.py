"""E03 실패 사례 진단: Upstage Standard 응답(로컬, Git 제외)을 공통 IR 0.2로 바꿔 직접 파서 v1·v2와 같은 공식 정답·채점기로 비교.

    .\\.venv\\Scripts\\python.exe scripts\\e03_upstage_compare.py <문서 ID>

- API를 호출하지 않는다 (응답은 e03_upstage_diag_call.py가 저장한 것).
- HTML 표(rowspan·colspan 있음)와 Markdown 표(병합 정보 없음)를 따로 IR로 만들어 따로 채점한다.
- Upstage는 셀 단위 좌표를 주지 않으므로 셀 bbox 지표는 '미제공'으로 기록한다 (0점으로 해석하지 않음).
- 서로 다른 출력 중 어느 쪽도 정답으로 고르지 않는다. 정답은 PubTables-1M 공식 주석뿐이다.
출력: results/E03_document_parsers/upstage_diag/<문서 ID>_comparison.json, summary.md (텍스트 없음)
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import e03_grade_external as G
from e04_preflight_analyze import TableHTML

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "upstage_e03_diag"
OUT = ROOT / "results" / "E03_document_parsers" / "upstage_diag"
PRICE_STANDARD_USD = 0.01   # upstage.ai/pricing 공개 단가 (2026-10-20 조회), VAT 별도


def page_sizes(pdf_path):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(pdf_path))
    return [pdf[i].get_size() for i in range(len(pdf))]


def bbox_pt(coords, size):
    xs, ys = [p["x"] * size[0] for p in coords], [p["y"] * size[1] for p in coords]
    return [min(xs), min(ys), max(xs), max(ys)]


def md_rows(md: str):
    rows = []
    for line in md.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip() for c in s[1:-1].split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


def to_ir(resp, sizes, kind: str, rel: str) -> dict:
    tables, blocks, seq = [], [], []
    for i, e in enumerate(resp["elements"]):
        page = e["page"]
        bb = bbox_pt(e["coordinates"], sizes[page - 1]) if e.get("coordinates") else None
        loc = {"format": "pdf", "page": page, **({"bbox": bb, "bbox_unit": "pt", "bbox_origin": "top-left"} if bb else {})}
        if e["category"] == "table":
            if kind == "html":
                p = TableHTML()
                p.feed(e["content"].get("html") or "")
                anchors = p.anchors()
            else:
                rows = md_rows(e["content"].get("markdown") or "")
                anchors = [{"row": r, "col": c, "rowspan": 1, "colspan": 1, "text": t} for r, row in enumerate(rows, start=1) for c, t in enumerate(row, start=1)]
            if not anchors:
                continue
            tid = f"t{len(tables) + 1:03d}"
            n_rows = max(a["row"] + a["rowspan"] - 1 for a in anchors)
            n_cols = max(a["col"] + a["colspan"] - 1 for a in anchors)
            cells = [{"row": a["row"], "col": a["col"], "rowspan": a["rowspan"], "colspan": a["colspan"], "text": a["text"], "raw": a["text"],
                      "is_header": None, "location": {"format": "pdf", "page": page}} for a in anchors]
            tables.append({"table_id": tid, "location": loc, "n_rows": n_rows, "n_cols": n_cols, "cells": cells, "detection": "api"})
            seq.append(tid)
        else:
            bid = f"b{len(blocks) + 1:04d}"
            blocks.append({"block_id": bid, "type": "other", "order": len(seq), "text": e["content"].get("text") or "", "location": loc,
                           "format_specific": {"category": e["category"]}})
            seq.append(bid)
    return {"schema": "chungpamo.parse_ir", "schema_version": "0.2", "document": {"source_file": rel, "format": "pdf"},
            "parser": {"name": "upstage-document-parse", "version": resp.get("model"), "mode": "api", "options": {"output": kind}, "api_calls": 1},
            "blocks": blocks, "tables": tables, "extracted_values": [], "records": [], "diagnostics": [],
            "format_specific": {"reading_sequence": seq, "cell_coordinates": "미제공 (요소 단위 좌표만)"}}


KEYS = [("table_detection.recall", "표 재현율"), ("table_detection.precision", "표 정밀도"), ("structure.rows_cols_equal", "행·열 수 일치"),
        ("cells.text_loose_grid", "셀 텍스트(격자, 공백무시)"), ("cells.text_strict_grid", "셀 텍스트(엄격)"), ("cells.merge_spans", "병합 셀"),
        ("cells.false_merges", "잘못된 병합"), ("cells.column_header_text", "헤더 셀 텍스트"), ("cells.projected_row_header", "행 머리"),
        ("table_detection.table_bbox_iou_mean", "표 bbox IoU 평균"), ("cells.cell_bbox_iou_ge_0_5", "셀 bbox IoU≥0.5")]


def get(m, path):
    for k in path.split("."):
        m = m.get(k) if isinstance(m, dict) else None
    return m


def fmt(v):
    if isinstance(v, dict):
        return "미측정" if v["status"] == "NOT_MEASURED" else f"{v['numerator']}/{v['denominator']}"
    return "—" if v is None else str(v)


def main() -> int:
    doc_id = sys.argv[1]
    truth = {d["doc_id"]: d for d in json.loads((ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json").read_text(encoding="utf-8"))["documents"]}[doc_id]
    log = json.loads((RAW / f"{doc_id}_call_log.json").read_text(encoding="utf-8"))
    rp = RAW / f"{doc_id}_response.json"
    raw = rp.read_bytes()
    resp = json.loads(raw)
    rel = f"data/raw/external_documents/pdf/{truth['file']}"
    sizes = page_sizes(ROOT / rel)
    rows = {}
    for kind in ("html", "markdown"):
        rows[f"upstage_standard_{kind}"] = G.grade(to_ir(resp, sizes, kind, rel), truth)["metrics"]
    for ver, run in (("v1", "external_dev_v1"), ("v2", "external_dev_v2")):
        for r in json.loads((ROOT / "results" / "E03_document_parsers" / run / "grading.json").read_text(encoding="utf-8"))["results"]:
            if r["doc_id"] == doc_id and r["parser"] == "pdfplumber":
                rows[f"direct_{ver}_pdfplumber"] = r["grade"]["metrics"]
    sys.path.insert(0, str(ROOT / "src"))
    from config.settings import get_upstage_api_key
    key = get_upstage_api_key()
    sec = {"api_key_in_response": bool(key) and key.encode() in raw, "home_path_in_response": str(Path.home()).lower().encode() in raw.lower(),
           "email_like_in_response": bool(re.search(rb"[\w.+-]+@[\w-]+\.[\w.]+", raw))}
    del key
    pages = (resp.get("usage") or {}).get("pages")
    res = {"purpose": "E03 실패 사례 진단 예비 비교 (E04 본 실험 아님). 1개 문서·1회 호출 — 일반화하지 않는다",
           "doc_id": doc_id, "split": truth["split"], "truth": "PubTables-1M 공식 주석 (VERIFIED_OFFICIAL)",
           "call": {k: log.get(k) for k in ("status", "http_status", "elapsed_seconds", "pages_sent", "model", "usage", "requested_at", "form")},
           "cost": {"billed_pages": pages, "unit_price_usd": PRICE_STANDARD_USD, "estimated_usd_excl_vat": round((pages or 0) * PRICE_STANDARD_USD, 4),
                    "actual_charge": "콘솔 확인 전 미확인"},
           "response": {"sha256": hashlib.sha256(raw).hexdigest(), "stored_at": "data/raw/upstage_e03_diag/ (Git 제외)",
                        "elements": len(resp["elements"]), "tables": sum(1 for e in resp["elements"] if e["category"] == "table"),
                        "cell_coordinates": "미제공 → 셀 bbox 지표는 측정 불가 (0점 아님)"},
           "security": sec,
           "metrics": {name: {label: fmt(get(m, k)) for k, label in KEYS} for name, m in rows.items()},
           "table_rows": {name: m.get("tables") for name, m in rows.items()}}
    for name in ("upstage_standard_html", "upstage_standard_markdown"):
        res["metrics"][name]["셀 bbox IoU≥0.5"] = "미제공 (측정 불가)"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{doc_id}_comparison.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    cols = list(res["metrics"])
    L = [f"# E03 실패 사례 진단 — Upstage Standard vs 직접 파서 ({doc_id})", "",
         f"> {res['purpose']}. 정답: {res['truth']}. dev 묶음 문서(v2 개발에 사용) — v2 수치는 개발 참고값.", "",
         f"- 호출: {log['status']}, HTTP {log.get('http_status')}, {log.get('elapsed_seconds')}s(네트워크 포함), 보낸 쪽 {log.get('pages_sent')}, 과금 {res['call']['usage']}, 모델 `{log.get('model')}`",
         f"- 비용: 추정 ${res['cost']['estimated_usd_excl_vat']} (공개 단가, VAT 별도), 실제 청구 {res['cost']['actual_charge']}",
         f"- 응답 보안 검사: {sec}", "",
         "| 지표 | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for _, label in KEYS:
        L.append(f"| {label} | " + " | ".join(res["metrics"][c][label] for c in cols) + " |")
    L += ["", "- Markdown 출력은 병합 정보를 표현하지 못하므로 병합 셀 지표는 HTML과 구분해 본다.",
          "- 처리시간은 조건이 달라(API는 네트워크·서버 포함) 직접 파서와 비교하지 않는다.", ""]
    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
