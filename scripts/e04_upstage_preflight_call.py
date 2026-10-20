"""E04 예비 실험: Upstage Document Parse API 1회 호출 (P-02 텍스트형 PDF).

    .\\.venv\\Scripts\\python.exe scripts\\e04_upstage_preflight_call.py

안전장치
- 호출 기록(data/raw/upstage_test/call_log.json)이 이미 있으면 호출하지 않고 종료한다 (정확히 1회).
- 자동 재시도 없음, 동시 요청 없음. 타임아웃 120초.
- API 키는 요청 헤더에만 쓰고 출력·로그·파일에 기록하지 않는다. 오류 메시지에 키가 섞이면 가린다.
- 오류 시 응답 본문 전체를 저장·출력하지 않고 상태 코드와 오류 분류만 남긴다.
- 응답 원문은 data/raw/upstage_test/ (Git 제외)에만 저장한다.
요청 필드는 공식 API Reference(https://console.upstage.ai/api/parse/document-parsing, 2026-10-20 조회) 기준.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from config.settings import get_upstage_api_key  # noqa: E402

ENDPOINT = "https://api.upstage.ai/v1/document-digitization"
DOC_ID = "P-02"
DOC_PATH = ROOT / "data" / "documents" / "P-02_order_inventory.pdf"
DOC_SHA256 = "cf9de77765ddf04ac01b6023d7af1e51a73cf0edc355b9768f272fe3d4b66349"   # E03 sample_manifest.csv
OUT_DIR = ROOT / "data" / "raw" / "upstage_test"
LOG = OUT_DIR / "call_log.json"
FORM = {  # 공식 문서의 필드명·허용값. mode=standard, ocr=auto(이미지 문서에만 OCR), merge_multipage_tables는 기본(false)
    "model": "document-parse",
    "mode": "standard",
    "ocr": "auto",
    "output_formats": '["html", "markdown", "text"]',
    "coordinates": "true",
}
SAFE_HEADERS = ("content-type", "content-length", "date", "x-request-id", "x-upstage-request-id")


def main() -> int:
    if LOG.exists():
        print("이미 호출 기록이 있음 → 재호출하지 않음 (사용자 승인 필요)")
        return 2
    data = DOC_PATH.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != DOC_SHA256:
        print("P-02 해시 불일치 → 호출 중단")
        return 3
    key = get_upstage_api_key()
    if not key:
        print("UPSTAGE_API_KEY 미설정 → 호출 중단")
        return 4
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    record = {"call_index": 1, "doc_id": DOC_ID, "file": str(DOC_PATH.relative_to(ROOT)).replace("\\", "/"), "sha256": sha,
              "bytes": len(data), "endpoint": ENDPOINT, "form": FORM, "retries": 0, "concurrency": 1,
              "requested_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    # 호출 전에 기록을 먼저 남겨, 어떤 경우에도 두 번째 호출이 일어나지 않게 한다
    LOG.write_text(json.dumps({**record, "status": "IN_PROGRESS"}, ensure_ascii=False, indent=2), encoding="utf-8")
    t0 = time.perf_counter()
    try:
        resp = requests.post(ENDPOINT, headers={"Authorization": f"Bearer {key}"},
                             files={"document": (DOC_PATH.name, data, "application/pdf")}, data=FORM, timeout=120)
        elapsed = time.perf_counter() - t0
        record.update({"elapsed_seconds": round(elapsed, 3), "http_status": resp.status_code,
                       "response_headers": {k: v for k, v in resp.headers.items() if k.lower() in SAFE_HEADERS}})
        if resp.ok:
            body = resp.json()
            (OUT_DIR / "P-02_response.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
            record.update({"status": "SUCCESS", "response_file": "data/raw/upstage_test/P-02_response.json",
                           "response_sha256": hashlib.sha256((OUT_DIR / "P-02_response.json").read_bytes()).hexdigest(),
                           "model": body.get("model"), "api": body.get("api"), "usage": body.get("usage")})
        else:
            err_type = None
            try:
                j = resp.json()
                e = j.get("error", j) if isinstance(j, dict) else {}
                err_type = {k: e.get(k) for k in ("code", "type") if isinstance(e, dict) and k in e}
            except ValueError:
                err_type = "응답 본문이 JSON 아님"
            record.update({"status": "HTTP_ERROR", "error_classification": err_type})
    except requests.RequestException as exc:
        record.update({"status": "REQUEST_EXCEPTION", "elapsed_seconds": round(time.perf_counter() - t0, 3),
                       "error_classification": type(exc).__name__,
                       "error_message": str(exc).replace(key, "***")[:300]})
    finally:
        del key
    LOG.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: record.get(k) for k in ("status", "http_status", "elapsed_seconds", "model", "usage", "error_classification")},
                     ensure_ascii=False))
    return 0 if record["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
