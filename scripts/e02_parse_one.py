"""E02 성능 측정용 자식 프로세스: 업체 1곳·데이터셋 1개를 파싱하고 파일별 시간(또는 Python 힙 피크)을 JSON으로 출력.

    python scripts/e02_parse_one.py <A|B> <clean|invalid> [--trace-mem]

--trace-mem 없이: time.perf_counter로 파일별 처리시간 (tracemalloc 오버헤드 없음)
--trace-mem 있으면: tracemalloc으로 파일별 Python 힙 피크 (이때의 시간은 쓰지 않음)
"""

from __future__ import annotations

import contextlib
import json
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parsers.vendor_parser import VendorParser, load_config  # noqa: E402


def main() -> int:
    vendor, dataset = sys.argv[1], sys.argv[2]
    trace = "--trace-mem" in sys.argv
    cfg = load_config(ROOT / "configs" / "e02_vendor_mapping.json")
    per_file = {}

    @contextlib.contextmanager
    def timer(label):
        base = 0
        if trace:
            base = tracemalloc.get_traced_memory()[0]  # 앞 파일 결과가 남긴 메모리는 빼고 이 파일 처리 중 증가분만
            tracemalloc.reset_peak()
        t0 = time.perf_counter()
        yield
        per_file[label] = {"seconds": time.perf_counter() - t0}
        if trace:
            per_file[label]["py_heap_peak_bytes"] = tracemalloc.get_traced_memory()[1] - base

    if trace:
        tracemalloc.start()
    t0 = time.perf_counter()
    VendorParser(cfg, vendor, ROOT / "data", "invalid/" if dataset == "invalid" else "").run(timer=timer)
    total = time.perf_counter() - t0
    print(json.dumps({"vendor": vendor, "dataset": dataset, "trace_mem": trace, "total_seconds": total, "per_file": per_file}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
