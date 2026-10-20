"""E03 외부 제작 문서 후보 내려받기 (configs/e03_external_sources.json).

    .\\.venv\\Scripts\\python.exe scripts\\e03_external_fetch.py [--pubtables-stream N]

- 원본은 data/raw/external_documents/<형식>/ 에만 저장 (Git 제외). 이미 있으면 다시 받지 않는다.
- GitHub 파일은 커밋 SHA로 고정한 raw URL에서 받는다. 저장소가 공개한 SHA-256이 있으면 대조한다.
- PubTables-1M PDF 주석: 3.7GB 아카이브의 앞부분만 스트리밍해 N개 JSON을 저장하고 중단 (기본 40, 전체 다운로드 안 함).
- 파일을 열거나 실행하지 않는다 (매크로·OLE·외부 링크 미실행). 내용 검사는 e03_external_inspect.py.
기록: data/raw/external_documents/fetch_log.json (Git 제외)
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import tarfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "configs" / "e03_external_sources.json"
RAW = ROOT / "data" / "raw" / "external_documents"
PUBTABLES_URL = "https://huggingface.co/datasets/bsmock/pubtables-1m/resolve/main/PubTables-1M-PDF_Annotations.tar.gz"
UA = {"User-Agent": "chungpamo-poc-research"}


def source_url(s: dict) -> str:
    if "url" in s:
        return s["url"]
    return f"https://raw.githubusercontent.com/{s['repo']}/{s['commit']}/{s['path']}"


def stream_pubtables(n_max: int) -> dict:
    out = RAW / "pubtables1m" / "pdf_annotations_sample"
    out.mkdir(parents=True, exist_ok=True)
    have = sorted(p.name for p in out.glob("*.json"))
    if len(have) >= n_max:
        return {"skipped": "이미 있음", "count": len(have)}

    class Counting:
        def __init__(self, raw):
            self.raw, self.n = raw, 0

        def read(self, size=-1):
            b = self.raw.read(size)
            self.n += len(b)
            return b

    names = []
    with requests.get(PUBTABLES_URL, stream=True, timeout=60, headers=UA) as r:
        r.raise_for_status()
        src = Counting(r.raw)
        with tarfile.open(fileobj=src, mode="r|gz") as tf:
            for m in tf:
                if m.isfile() and m.name.endswith(".json"):
                    (out / Path(m.name).name).write_bytes(tf.extractfile(m).read())
                    names.append(Path(m.name).name)
                    if len(names) >= n_max:
                        break
    return {"compressed_bytes_read": src.n, "count": len(names)}


def main() -> int:
    n_stream = int(sys.argv[sys.argv.index("--pubtables-stream") + 1]) if "--pubtables-stream" in sys.argv else 40
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    log = {"run": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "files": [], "pubtables": stream_pubtables(n_stream)}
    for s in cfg["sources"]:
        dst = RAW / s["format"] / s["file"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        rec = {"id": s["id"], "url": source_url(s), "path": dst.relative_to(ROOT).as_posix()}
        try:
            if not dst.exists():
                r = requests.get(rec["url"], timeout=120, headers=UA)
                r.raise_for_status()
                dst.write_bytes(r.content)
                rec["downloaded"] = True
            else:
                rec["downloaded"] = "이미 있음"
            data = dst.read_bytes()
            rec["sha256"] = hashlib.sha256(data).hexdigest()
            rec["bytes"] = len(data)
            if s.get("expected_sha256"):
                rec["matches_published_sha256"] = rec["sha256"] == s["expected_sha256"]
            if s.get("metadata_url"):
                meta_dst = dst.with_suffix(".meta.json")
                if not meta_dst.exists():
                    meta_dst.write_bytes(requests.get(s["metadata_url"], timeout=60, headers=UA).content)
                m = json.loads(meta_dst.read_text(encoding="utf-8"))
                rec["pmc_license_code"] = m.get("license_code")
                rec["pmc_is_retracted"] = m.get("is_retracted")
                rec["pmc_pdf_md5_matches"] = (m.get("pdf_url") or "").endswith("md5=" + hashlib.md5(data).hexdigest())
        except Exception as e:  # 실패는 기록 (성공 처리하지 않음)
            rec["downloaded"] = False
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        log["files"].append(rec)
    (RAW / "fetch_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": sum(1 for f in log["files"] if f.get("downloaded")), "total": len(log["files"]),
                      "failed": [f["id"] for f in log["files"] if not f.get("downloaded")],
                      "published_sha_mismatch": [f["id"] for f in log["files"] if f.get("matches_published_sha256") is False],
                      "pubtables": log["pubtables"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
