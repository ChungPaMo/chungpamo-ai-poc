"""외부 문서 평가용 자식 프로세스: 파서 1개로 문서 1개를 파싱하고 시간·힙 피크·출력 해시를 JSON으로 출력.

    python scripts/e03_ext_parse_doc.py <v1|v2> <parser> <문서 상대경로> [--trace-mem] [--save <IR 저장 경로>]

실패해도 예외를 JSON으로 돌려준다 (성공 처리하지 않음). 경로·사용자 이름은 마스킹한다.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import traceback
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
LIB_MODULE = {"python-docx": "docx", "python-pptx": "pptx", "pypdf": "pypdf", "pdfplumber": "pdfplumber"}


def ir_digest(ir: dict) -> str:
    return hashlib.sha256(json.dumps(ir, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def main() -> int:
    ver, name, rel = sys.argv[1], sys.argv[2], sys.argv[3]
    trace = "--trace-mem" in sys.argv
    save = Path(sys.argv[sys.argv.index("--save") + 1]) if "--save" in sys.argv else None
    import check_environment as ce
    t0 = time.perf_counter()
    if ver == "v1":
        from parsers.doc_registry import PARSERS
    else:
        from parsers.v2.registry import PARSERS
    __import__(LIB_MODULE[name])
    _, fn = PARSERS[name]
    imp = time.perf_counter() - t0
    if trace:
        tracemalloc.start()
    t1 = time.perf_counter()
    out = {"version": ver, "parser": name, "file": rel, "trace_mem": trace, "import_seconds": imp}
    try:
        ir = fn(ROOT / rel, rel)
        out.update({"ok": True, "parse_seconds": time.perf_counter() - t1, "ir_sha256": ir_digest(ir)})
        if save:
            save.parent.mkdir(parents=True, exist_ok=True)
            save.write_text(json.dumps(ir, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    except Exception as e:  # 실패 기록
        tb = traceback.extract_tb(e.__traceback__)
        out.update({"ok": False, "parse_seconds": time.perf_counter() - t1, "error_type": type(e).__name__,
                    "error": ce.mask_sensitive(str(e))[:400],
                    "where": [f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in tb[-4:]]})
    if trace:
        out["py_heap_peak_bytes"] = tracemalloc.get_traced_memory()[1]
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
