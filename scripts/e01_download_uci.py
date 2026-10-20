"""E01: UCI Daily Demand Forecasting Orders 원본 다운로드 (공식 UCI 출처).

    .\\.venv\\Scripts\\python.exe scripts\\e01_download_uci.py

- 받은 zip은 수정하지 않는다. 같은 이름의 파일이 있으면 덮어쓰지 않고 중단한다.
- zip 안의 파일은 `extracted/`에 원래 이름 그대로 푼다(내용 변경 없음).
- 다운로드 기록(URL, 시각, HTTP 상태, 크기, SHA-256)을 download_record.json에 남긴다.
- 저장 위치 data/raw/public/ 는 .gitignore로 Git 추적에서 제외된다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "public" / "uci_daily_demand"
DATASET_PAGE = "https://archive.ics.uci.edu/dataset/409/daily+demand+forecasting+orders"
ZIP_URL = "https://archive.ics.uci.edu/static/public/409/daily+demand+forecasting+orders.zip"
ZIP_NAME = "daily+demand+forecasting+orders.zip"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    zip_path = DEST / ZIP_NAME
    if zip_path.exists():
        print(f"already exists, not overwriting: {zip_path.name}")
        return 1
    record: dict = {"dataset_page": DATASET_PAGE, "url": ZIP_URL,
                    "downloaded_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "chungpamo-poc/0.1 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            record["http_status"] = resp.status
            record["content_type"] = resp.headers.get("Content-Type")
            body = resp.read()
    except Exception as exc:  # noqa: BLE001 - 실패도 기록
        record["error"] = f"{type(exc).__name__}: {exc}"
        (DEST / "download_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"download failed: {record['error']}")
        return 2
    zip_path.write_bytes(body)
    record["zip"] = {"file": ZIP_NAME, "bytes": len(body), "sha256": sha256(zip_path)}
    members = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = DEST / "extracted" / Path(info.filename).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            members.append({"member": info.filename, "file": f"extracted/{target.name}",
                            "bytes": target.stat().st_size, "sha256": sha256(target)})
    record["members"] = members
    (DEST / "download_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
