"""공개 후보 파일에 외부 문서 텍스트(정답의 문단·셀·도형·SmartArt·차트 문자열)가 들어 있는지 검사.

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_leak_scan.py [--report <경로>]

비교 단위: 정답 문자열 중 두 단어 이상·공백 제거 8자 이상(숫자·기호만인 것 제외). 일치한 문자열 자체는 기록하지 않고 파일·개수만 기록한다.
외부 정답(Git 제외)이 없으면 검사할 수 없으므로 NOT_MEASURED로 끝낸다.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json"
TEXT_EXT = {".py", ".md", ".json", ".csv", ".txt", ".toml", ".ini", ".cfg", ".xml", ".yml", ".yaml"}


def nows(s):
    return re.sub(r"\s+", "", s or "")


def truth_strings(t) -> set[str]:
    out = set()

    def add(s):
        k = nows(s)
        # 두 단어 이상인 구절만 (한 단어 일반어 'Reference' 등은 우연 일치가 많아 제외)
        if len(k) >= 8 and len((s or "").split()) >= 2 and re.search(r"[A-Za-z가-힣]{3,}", k):
            out.add(k)
    for d in t["documents"]:
        tr = d.get("truth") or {}
        for b in tr.get("blocks", []):
            add(b["text"])
        for x in tr.get("headers", []) + tr.get("footers", []) + tr.get("footnotes", []) + tr.get("endnotes", []):
            add(x["text"])
        for tb in tr.get("tables", []):
            for c in tb["cells"]:
                add(c["text"])
        for s in tr.get("slides", []):
            for x in s["shapes"]:
                add(x["text"])
            for tb in s["tables"]:
                for c in tb["cells"]:
                    add(c["text"])
            for sa in s["smartart"]:
                for n in sa.get("node_texts_official") or sa["node_texts"]:
                    add(n)
            for ch in s["charts"]:
                for x in ch["texts"]:
                    add(x)
            add(s["notes"])
    return out


def main() -> int:
    report = Path(sys.argv[sys.argv.index("--report") + 1]) if "--report" in sys.argv else None
    if not TRUTH.exists():
        print(json.dumps({"status": "NOT_MEASURED", "reason": "외부 정답 없음"}, ensure_ascii=False))
        return 0
    strings = truth_strings(json.loads(TRUTH.read_text(encoding="utf-8")))
    files = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    hits = {}
    for f in files:
        p = ROOT / f
        if p.suffix.lower() not in TEXT_EXT or not p.exists():
            continue
        body = nows(p.read_text(encoding="utf-8", errors="replace"))
        n = sum(1 for s in strings if s in body)
        if n:
            hits[f] = n
    res = {"status": "MEASURED", "truth_strings_checked": len(strings), "candidate_files_scanned": len(files),
           "files_with_external_text": hits, "ok": not hits}
    if report:
        report.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
