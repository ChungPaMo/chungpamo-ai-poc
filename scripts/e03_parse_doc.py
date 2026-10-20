"""E03 성능 측정용 자식 프로세스: 파서 1개로 문서 1개를 파싱하고 시간(또는 Python 힙 피크)과 출력 해시를 JSON으로 출력.

    python scripts/e03_parse_doc.py <parser> <문서 상대경로> [--trace-mem]

--trace-mem 없이: import 시간과 파싱 시간 (time.perf_counter)
--trace-mem 있으면: tracemalloc으로 파싱 중 Python 힙 피크 (이때의 시간은 쓰지 않음)
출력 IR은 저장하지 않고 SHA-256만 낸다 (반복 실행 간 출력 동일성 확인용).
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LIB_MODULE = {"python-docx": "docx", "python-pptx": "pptx", "pypdf": "pypdf", "pdfplumber": "pdfplumber"}


def ir_digest(ir: dict) -> str:
    return hashlib.sha256(json.dumps(ir, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def main() -> int:
    name, rel = sys.argv[1], sys.argv[2]
    trace = "--trace-mem" in sys.argv
    t0 = time.perf_counter()
    from parsers.doc_registry import PARSERS
    __import__(LIB_MODULE[name])  # 파서 함수 안에서 늦게 import하는 라이브러리도 import 시간에 넣는다
    _, fn = PARSERS[name]
    fn_import = time.perf_counter() - t0
    if trace:
        tracemalloc.start()
    t1 = time.perf_counter()
    ir = fn(ROOT / rel, rel)
    parse = time.perf_counter() - t1
    out = {"parser": name, "file": rel, "trace_mem": trace, "import_seconds": fn_import, "parse_seconds": parse, "ir_sha256": ir_digest(ir)}
    if trace:
        out["py_heap_peak_bytes"] = tracemalloc.get_traced_memory()[1]
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
