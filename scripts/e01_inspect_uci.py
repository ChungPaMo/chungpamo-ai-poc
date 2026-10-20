"""E01: UCI 원본 구조 검증 (네트워크 사용 안 함, 원본 수정 안 함).

    .\\.venv\\Scripts\\python.exe scripts\\e01_inspect_uci.py

실제 헤더·구분자·인코딩·행 수·자료형·결측을 원본 바이트에서 확인하고,
총주문(Target)과 세부 열의 관계를 Decimal 정확 비교로 검증해
results/E01_dataset/uci_source_verification.json에 기록한다.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "public" / "uci_daily_demand"
CSV_PATH = RAW_DIR / "extracted" / "Daily_Demand_Forecasting_Orders.csv"
OUT = ROOT / "results" / "E01_dataset" / "uci_source_verification.json"

# 페이지에서 확인한 메타데이터 (data_source_research.md S5, 2026-10-20 조회)
SOURCE_META = {
    "dataset": "Daily Demand Forecasting Orders",
    "dataset_page": "https://archive.ics.uci.edu/dataset/409/daily+demand+forecasting+orders",
    "license": "CC BY 4.0 (Creative Commons Attribution 4.0 International)",
    "citation": "Ferreira, R., Martiniano, A., Ferreira, A., Ferreira, A., & Sassi, R. (2016). Daily Demand Forecasting Orders [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BC8T",
    "origin_class": "PUBLIC_REAL",
    "page_description": "real database of a brazilian logistics company, collected during 60 days",
}

COL = {  # 원본 헤더 순서 기준 짧은 이름 (원본 문자열은 header_raw에 그대로 기록)
    0: "week_of_month", 1: "day_of_week", 2: "non_urgent", 3: "urgent", 4: "type_a", 5: "type_b",
    6: "type_c", 7: "fiscal", 8: "traffic_controller", 9: "banking_1", 10: "banking_2", 11: "banking_3",
    12: "target_total",
}


def _infer(values: list[str]) -> dict:
    kinds, missing, parsed = set(), 0, []
    for v in values:
        s = v.strip()
        if s == "":
            missing += 1
            continue
        try:
            d = Decimal(s)
        except InvalidOperation:
            kinds.add("text")
            continue
        parsed.append(d)
        kinds.add("integer" if "." not in s else "decimal")
    info = {"inferred_type": "/".join(sorted(kinds)) or "empty", "missing": missing}
    if parsed:
        info.update(min=str(min(parsed)), max=str(max(parsed)),
                    max_decimal_places=max((-d.as_tuple().exponent if d.as_tuple().exponent < 0 else 0) for d in parsed))
    return info


def main() -> int:
    raw = CSV_PATH.read_bytes()
    report: dict = {"source": SOURCE_META}
    dl = RAW_DIR / "download_record.json"
    report["download_record"] = json.loads(dl.read_text(encoding="utf-8")) if dl.exists() else None
    report["file"] = {"path": "data/raw/public/uci_daily_demand/extracted/Daily_Demand_Forecasting_Orders.csv",
                      "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    try:
        text = raw.decode("ascii")
        encoding = "ascii (UTF-8 호환, BOM 없음)"
    except UnicodeDecodeError:
        text = raw.decode("utf-8")
        encoding = "utf-8"
    report["encoding"] = encoding
    report["bom"] = raw.startswith(b"\xef\xbb\xbf")
    report["line_ending"] = "CRLF" if b"\r\n" in raw else "LF"
    # csv.Sniffer는 헤더 안의 쉼표 때문에 ','를 고르므로 쓰지 않는다.
    # 모든 행에서 같은 열 수(>1)로 나뉘는 후보만 구분자로 인정한다.
    consistent = {}
    for cand in (";", ",", "\t", "|"):
        counts = {len(r) for r in csv.reader(io.StringIO(text), delimiter=cand)}
        if len(counts) == 1 and counts.pop() > 1:
            consistent[cand] = True
    report["delimiter_candidates_consistent"] = sorted(consistent)
    if len(consistent) != 1:
        raise SystemExit(f"구분자 판별 실패: {sorted(consistent)}")
    delimiter = next(iter(consistent))
    report["delimiter"] = delimiter
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header, data = rows[0], rows[1:]
    report["header_raw"] = header
    report["column_count"] = len(header)
    report["row_count"] = len(data)
    report["ragged_rows"] = [i + 2 for i, r in enumerate(data) if len(r) != len(header)]
    report["header_notes"] = [
        f"열 {i}: 괄호가 닫히지 않음 (원본 그대로)" for i, h in enumerate(header) if h.count("(") != h.count(")")
    ]
    report["columns"] = {COL[i]: {"header": header[i], **_infer([r[i] for r in data])} for i in range(len(header))}

    D = [[Decimal(c) for c in r] for r in data]
    idx = {v: k for k, v in COL.items()}

    def check(name: str, parts: list[str]) -> dict:
        exact, diffs = 0, []
        for n, r in enumerate(D):
            s = sum((r[idx[p]] for p in parts), Decimal(0))
            if s == r[idx["target_total"]]:
                exact += 1
            else:
                diffs.append({"data_row": n + 1, "sum": str(s), "target": str(r[idx["target_total"]]),
                              "diff": str(r[idx["target_total"]] - s)})
        return {"relation": f"target_total == {' + '.join(parts)}", "exact_match_rows": exact,
                "rows": len(D), "mismatches": diffs[:10], "mismatch_count": len(diffs)}

    report["relationship_checks"] = [
        check("priority", ["non_urgent", "urgent"]),
        check("priority+fiscal", ["non_urgent", "urgent", "fiscal"]),
        check("types", ["type_a", "type_b", "type_c"]),
    ]
    # 요일 코드: 원본에 코드표가 없어 숫자 값의 의미(예: 2=월요일)는 확인할 수 없다. 숫자 패턴만 기록한다.
    dows = [int(r[idx["day_of_week"]]) for r in D]
    lo, hi = min(dows), max(dows)
    breaks = [n + 2 for n in range(1, len(dows)) if not (dows[n] == dows[n - 1] + 1 or (dows[n - 1] == hi and dows[n] == lo))]
    report["day_sequence"] = {
        "day_of_week_values": sorted(set(dows)),
        "code_meaning": "미확인 — 원본 파일과 데이터셋 페이지에 코드표가 없다. 페이지 설명 'Monday to Friday'와 값 5종(2~6)이 대응할 "
                        "가능성은 있으나 검증된 사실로 쓰지 않는다. 생성 데이터는 코드를 숫자 그대로 보존한다.",
        "code_sequence_pattern": "행이 바뀔 때 코드가 1씩 증가하거나 최대값에서 최소값으로 돌아가는지 검사 (요일 의미 가정 없이 숫자 패턴만)",
        "pattern_breaks_at_file_lines": breaks,
    }
    report["interpretation"] = (
        "일별 집계 주문 자료로만 취급한다. 제품별 주문이 아니며 Order type A/B/C를 제품으로 대응시키지 않는다. "
        "원본에 날짜 열이 없으므로 생성 데이터의 달력 날짜는 합성값이며 원본 요일 코드와 관계없다."
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: report[k] for k in ("encoding", "delimiter", "row_count", "column_count", "header_notes")}, ensure_ascii=False))
    for c in report["relationship_checks"]:
        print(c["relation"], c["exact_match_rows"], "/", c["rows"])
    print("code pattern breaks:", report["day_sequence"]["pattern_breaks_at_file_lines"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
