"""E04 예비 실험 분석: Upstage 응답(data/raw/upstage_test/P-02_response.json, Git 제외)을 E03 정답 명세와 대조.

    .\\.venv\\Scripts\\python.exe scripts\\e04_preflight_analyze.py

API를 호출하지 않는다. 공개 가능한 요약(수치·판정)만 results/E04_upstage_preflight/에 쓴다.
P-02 1개 문서·1회 호출 결과이며 전체 문서 정확도로 일반화하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "upstage_test"
OUT = ROOT / "results" / "E04_upstage_preflight"
PAGE_W, PAGE_H = 595.2756, 841.8898   # P-02 MediaBox (pt), 좌표는 top-left 원점으로 환산
IOU_TABLE = 0.5
PRICE_STANDARD_USD = 0.01             # upstage.ai/pricing (2026-10-20 조회), VAT 10% 별도


class TableHTML(HTMLParser):
    """<table>을 앵커 셀 목록(행·열·rowspan·colspan·텍스트)으로 복원."""

    def __init__(self) -> None:
        super().__init__()
        self.rows, self.cur, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self.cur = []
        elif tag in ("td", "th"):
            self.cell = {"rowspan": int(a.get("rowspan", 1)), "colspan": int(a.get("colspan", 1)), "text": ""}

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = re.sub(r"\s+", " ", self.cell["text"]).strip()
            self.cur.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.cur is not None:
            self.rows.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def anchors(self) -> list[dict]:
        occupied, out = set(), []
        for r, row in enumerate(self.rows, start=1):
            c = 1
            for cell in row:
                while (r, c) in occupied:
                    c += 1
                out.append({"row": r, "col": c, **cell})
                for dr in range(cell["rowspan"]):
                    for dc in range(cell["colspan"]):
                        occupied.add((r + dr, c + dc))
                c += cell["colspan"]
        return out


def bbox_pt(coords) -> list[float]:
    xs, ys = [p["x"] * PAGE_W for p in coords], [p["y"] * PAGE_H for p in coords]
    return [min(xs), min(ys), max(xs), max(ys)]


def iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def rate(n: int, d: int) -> dict:
    return {"numerator": n, "denominator": d, "rate": None if d == 0 else round(n / d, 4),
            "status": "NOT_MEASURED" if d == 0 else ("PASS" if n == d else "PARTIAL" if n else "FAIL")}


def main() -> int:
    log = json.loads((RAW / "call_log.json").read_text(encoding="utf-8"))
    resp_path = RAW / "P-02_response.json"
    resp = json.loads(resp_path.read_text(encoding="utf-8"))
    truth = json.loads((ROOT / "data/canonical/e03_document_truth_v1.json").read_text(encoding="utf-8"))
    locs = json.loads((ROOT / "data/canonical/e03_document_locations_v1.json").read_text(encoding="utf-8"))["documents"]["P-02"]
    cs = truth["content_sets"]["CS2"]
    blocks = {b["block_id"]: b for b in cs["blocks"]}
    tables = {t["table_id"]: t for t in cs["tables"]}
    els = resp["elements"]
    texts = [e["content"].get("text", "") for e in els]

    # 1. 텍스트 블록 (정확 일치 / 공백 정규화 일치)
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    block_rows = []
    for bid, b in blocks.items():
        hits = [e for e in els if e["category"] != "table" and norm(e["content"]["text"]) == norm(b["text"])]
        expected_occ = len(locs["blocks"][bid])
        ious = []
        for l in locs["blocks"][bid]:
            same_page = [e for e in hits if e["page"] == l["page"]]
            if same_page:
                ious.append(round(max(iou(bbox_pt(e["coordinates"]), l["bbox"]) for e in same_page), 3))
        block_rows.append({"block_id": bid, "truth_type": b["type"], "found_occurrences": len(hits), "expected_occurrences": expected_occ,
                           "api_categories": sorted({e["category"] for e in hits}), "bbox_iou_per_occurrence": ious})
    captions = [{"table_id": t["table_id"], "found": any(norm(e["content"]["text"]) == norm(t["caption"]) for e in els if e["category"] != "table"),
                 "api_categories": sorted({e["category"] for e in els if norm(e["content"]["text"]) == norm(t["caption"])})} for t in cs["tables"]]
    # 2~6. 표
    api_tables = [e for e in els if e["category"] == "table"]
    frags = [(tid, f) for tid, e in locs["tables"].items() for f in e["fragments"]]
    table_rows, cell_hit, cell_tot, merge_hit, merge_tot = [], 0, 0, 0, 0
    header_hit = header_tot = 0
    value_cells = {}
    for tid, f in frags:
        t = tables[tid]
        truth_cells = {(c["row"], c["col"]): c for c in t["cells"]}
        cands = [e for e in api_tables if e["page"] == f["page"]]
        best = max(cands, key=lambda e: iou(bbox_pt(e["coordinates"]), f["bbox"]), default=None)
        row = {"table_id": tid, "fragment_index": f["fragment_index"], "page": f["page"], "matched_api_element": best["id"] if best else None}
        if best is None:
            row["status"] = "표 미검출"
            cell_tot += sum(1 for c in t["cells"] if c["row"] in f["logical_rows"])
            table_rows.append(row)
            continue
        p = TableHTML()
        p.feed(best["content"]["html"])
        got = {(a["row"], a["col"]): a for a in p.anchors()}
        logical = {i + 1: lr for i, lr in enumerate(f["logical_rows"])}     # API 표 행 → 논리 행
        n_rows_api = len(p.rows)
        ok = tot = 0
        for (r_api, c), a in got.items():
            lr = logical.get(r_api)
            tc = truth_cells.get((lr, c)) if lr else None
            if tc is None:
                continue
            value_cells.setdefault((tid, lr, c), a["text"])
        for lr in f["logical_rows"]:
            for c in range(1, t["n_cols"] + 1):
                tc = truth_cells.get((lr, c))
                if tc is None:
                    continue
                r_api = f["logical_rows"].index(lr) + 1
                a = got.get((r_api, c))
                tot += 1
                hit = a is not None and a["text"] == tc["text"]
                ok += hit
                if tc["is_header"]:
                    header_tot += 1
                    header_hit += hit
                if tc["rowspan"] > 1 or tc["colspan"] > 1:
                    merge_tot += 1
                    merge_hit += a is not None and (a["rowspan"], a["colspan"]) == (tc["rowspan"], tc["colspan"])
        cell_hit += ok
        cell_tot += tot
        row.update({"api_rows": n_rows_api, "expected_rows": len(f["logical_rows"]), "api_cols": max((a["col"] + a["colspan"] - 1 for a in got.values()), default=0),
                    "expected_cols": t["n_cols"], "cells": rate(ok, tot), "table_bbox_iou": round(iou(bbox_pt(best["coordinates"]), f["bbox"]), 3)})
        table_rows.append(row)
    # 5. 값 (코드·수량·단위·날짜·금액)
    kinds = Counter()
    kinds_ok = Counter()
    for v in cs["extracted_values"]:
        s = v["source"]
        got = value_cells.get((s["table_id"], s["row"], s["col"]))
        k = v["field"]
        kinds[k] += 1
        kinds_ok[k] += got == v["raw"]
    codes_tot = codes_ok = 0
    for t in cs["tables"]:
        for c in t["cells"]:
            if c["col"] == 2 and not c["is_header"]:   # 제품·자재 코드 열
                codes_tot += 1
                codes_ok += value_cells.get((t["table_id"], c["row"], 2)) == c["text"]
    # 7. 페이지 넘김 연결
    t1 = [r for r in table_rows if r["table_id"] == "CS2-T1"]
    link = {"truth": "CS2-T1이 1쪽(데이터 12행)과 2쪽(데이터 8행)으로 나뉘고 2쪽에서 헤더 2행 반복",
            "api_elements_for_fragments": [r["matched_api_element"] for r in t1],
            "api_merged_into_one_table": len({r["matched_api_element"] for r in t1}) == 1,
            "explicit_continuation_field": any(k for e in api_tables for k in e if k not in ("category", "content", "coordinates", "id", "page")),
            "repeated_header_recognized_in_fragment2": t1[1]["cells"]["status"] in ("PASS",) if len(t1) > 1 and "cells" in t1[1] else False,
            "request_option": "merge_multipage_tables 기본값(false)으로 요청 — 병합 기능(베타)은 시험하지 않음"}
    # 보안: 응답 안에 키·사용자 경로·이메일이 있는가 (값은 기록하지 않음)
    sys.path.insert(0, str(ROOT / "src"))
    from config.settings import get_upstage_api_key
    raw_bytes = resp_path.read_bytes()
    key = get_upstage_api_key()
    sec = {"api_key_in_response": bool(key) and key.encode() in raw_bytes,
           "home_path_in_response": str(Path.home()).lower().encode() in raw_bytes.lower(),
           "email_like_in_response": bool(re.search(rb"[\w.+-]+@[\w-]+\.[\w.]+", raw_bytes)),
           "extra_top_level_fields": sorted(set(resp) - {"api", "content", "elements", "model", "ocr", "usage"})}
    del key
    pages = resp["usage"]["pages"]
    summary = {
        "experiment": "E04 예비 (preflight) — E04 본 실험 아님",
        "scope_note": "P-02 1개 문서·1회 호출. 전체 문서 정확도로 일반화하지 않는다. 직접 파서 비교는 미측정",
        "input": {"doc_id": "P-02", "sha256": log["sha256"], "bytes": log["bytes"], "origin_class": "SYNTHETIC", "pages": 3},
        "call": {"count": 1, "retries": 0, "status": log["status"], "http_status": log.get("http_status"), "elapsed_seconds": log.get("elapsed_seconds"),
                 "requested_at": log["requested_at"], "request_form": log["form"], "endpoint": log["endpoint"]},
        "response": {"api": resp.get("api"), "model": resp.get("model"), "ocr": resp.get("ocr"), "usage": resp.get("usage"),
                     "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(), "raw_stored_at": "data/raw/upstage_test/ (Git 제외)",
                     "element_count": len(els), "category_counts": dict(Counter(e["category"] for e in els)),
                     "table_elements": len(api_tables),
                     "content_formats": {k: bool(v) for k, v in resp["content"].items()},
                     "element_content_formats": dict(Counter(k for e in els for k, v in e["content"].items() if v)),
                     "coordinates_provided": all(len(e.get("coordinates") or []) == 4 for e in els),
                     "coordinates_format": "요소별 4점(x, y), 페이지 크기 대비 비율 (0~1), 좌상단 원점으로 보임 — 공식 문서에 단위 명시 없음"},
        "cost_estimate": {"billed_pages": pages, "mode": "standard", "unit_price_usd": PRICE_STANDARD_USD,
                          "estimated_usd_excl_vat": round(pages * PRICE_STANDARD_USD, 4), "estimated_usd_incl_vat_10pct": round(pages * PRICE_STANDARD_USD * 1.1, 4),
                          "basis": "upstage.ai/pricing 공개 단가 (2026-10-20 조회). 실제 청구 금액은 콘솔 확인 전 미확인"},
        "comparison_vs_e03_truth": {
            "text_blocks": block_rows,
            "table_captions": captions,
            "tables": table_rows,
            "cells_all_fragments": rate(cell_hit, cell_tot),
            "header_cells": rate(header_hit, header_tot),
            "merged_cells_spans": rate(merge_hit, merge_tot),
            "product_material_codes": rate(codes_ok, codes_tot),
            "values_by_field": {k: rate(kinds_ok[k], kinds[k]) for k in sorted(kinds)},
            "multipage_table_link": link,
            "source_location": {"coordinates": "제공됨 (요소 단위 bbox)", "cell_level_coordinates": "제공 안 됨 (표 HTML에 셀 좌표 없음)",
                                "table_bbox_iou_threshold": IOU_TABLE,
                                "table_bbox_iou": {f"{r['table_id']}#{r['fragment_index']}": r.get("table_bbox_iou") for r in table_rows}},
        },
        "not_compared": {"direct_parser_comparison": "직접 파서(pypdf·pdfplumber 등) 실측 없음 → 미측정",
                         "accuracy_generalization": "1개 문서 결과로 일반화하지 않음",
                         "enhanced_mode": "호출하지 않음"},
        "security": sec,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "preflight_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (OUT / "summary.md").write_text(to_md(summary), encoding="utf-8", newline="\n")
    print(json.dumps({"cells": summary["comparison_vs_e03_truth"]["cells_all_fragments"], "merges": summary["comparison_vs_e03_truth"]["merged_cells_spans"],
                      "codes": summary["comparison_vs_e03_truth"]["product_material_codes"], "link": link, "security": sec}, ensure_ascii=False))
    return 0


def to_md(s: dict) -> str:
    c = s["comparison_vs_e03_truth"]
    L = ["# E04 예비 실험 — Upstage Document Parse 첫 호출 (P-02)", "",
         f"> {s['experiment']}. {s['scope_note']}", "",
         "## 1. 호출", "",
         f"- 입력: {s['input']['doc_id']} (합성 문서, {s['input']['pages']}쪽, SHA-256 `{s['input']['sha256'][:16]}…`)",
         f"- 결과: {s['call']['status']}, HTTP {s['call']['http_status']}, 처리시간 {s['call']['elapsed_seconds']}s (네트워크 포함), 호출 {s['call']['count']}회, 재시도 {s['call']['retries']}회",
         f"- 요청 옵션: `{json.dumps(s['call']['request_form'], ensure_ascii=False)}`",
         f"- 응답 모델: `{s['response']['model']}`, api {s['response']['api']}, 과금 페이지 {s['response']['usage']}",
         f"- 추정 비용: ${s['cost_estimate']['estimated_usd_excl_vat']} (VAT 별도), VAT 포함 ${s['cost_estimate']['estimated_usd_incl_vat_10pct']} — {s['cost_estimate']['basis']}", "",
         "## 2. 응답 구조", "",
         f"- 요소 {s['response']['element_count']}개: {s['response']['category_counts']}",
         f"- 표 요소: {s['response']['table_elements']}개 / 문서 전체 형식: {s['response']['content_formats']} / 요소별 형식: {s['response']['element_content_formats']}",
         f"- 좌표: {s['response']['coordinates_format']} (모든 요소 제공 = {s['response']['coordinates_provided']})", "",
         "## 3. E03 정답 대조", "",
         "| 블록 | 정답 유형 | 기대 출현 | 검출 | API 분류 | bbox IoU |", "|---|---|---|---|---|---|"]
    L += [f"| {b['block_id']} | {b['truth_type']} | {b['expected_occurrences']} | {b['found_occurrences']} | {b['api_categories']} | {b['bbox_iou_per_occurrence']} |"
          for b in c["text_blocks"]]
    L += ["", "| 표 캡션 | 검출 | API 분류 |", "|---|---|---|"] + [f"| {x['table_id']} | {x['found']} | {x['api_categories']} |" for x in c["table_captions"]]
    L += ["", "| 표 조각 | 쪽 | API 요소 | 행(API/정답) | 열(API/정답) | 셀 일치 | 표 bbox IoU |", "|---|---|---|---|---|---|---|"]
    for r in c["tables"]:
        cells = r.get("cells", {})
        L.append(f"| {r['table_id']}#{r['fragment_index']} | {r['page']} | {r['matched_api_element']} | {r.get('api_rows')}/{r.get('expected_rows')} | "
                 f"{r.get('api_cols')}/{r.get('expected_cols')} | {cells.get('numerator')}/{cells.get('denominator')} | {r.get('table_bbox_iou')} |")
    L += ["", f"- 전체 셀: {c['cells_all_fragments']}", f"- 헤더 셀: {c['header_cells']}", f"- 병합 셀(span): {c['merged_cells_spans']}",
          f"- 제품·자재 코드: {c['product_material_codes']}"]
    L += [f"- 값 `{k}`: {v['numerator']}/{v['denominator']} ({v['status']})" for k, v in c["values_by_field"].items()]
    L += ["", f"- 페이지 넘김 표: {c['multipage_table_link']}", f"- 원본 위치: {c['source_location']}", "",
          "## 4. 미비교", ""] + [f"- {k}: {v}" for k, v in s["not_compared"].items()]
    L += ["", "## 5. 응답 보안 검사", "", f"- {s['security']}", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
