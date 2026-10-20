"""E03 실패 사례 진단용 Upstage Document Parse 제한 호출 (E04 본 실험 아님, D-021 조건부 승인 범위).

    .\\.venv\\Scripts\\python.exe scripts\\e03_upstage_diag_call.py <문서 ID>

안전장치
- Standard 모드만, Enhanced·OCR 전용 모델 없음. 자동 재시도·동시 요청 없음. 타임아웃 120초.
- 전체 과금 상한 4쪽: 호출 전 문서 전체 쪽 수를 세고, 지금까지 보낸 쪽 수 + 이 문서 쪽 수가 4를 넘으면 호출하지 않는다.
  쪽 범위 지정은 공식 요청 필드에 없으므로(2026-10-20 API Reference 조회) 문서를 자르지 않고 전체 파일만 보낸다.
- 문서마다 1회: 호출 기록이 있으면 다시 호출하지 않는다. 기록은 호출 전에 먼저 쓴다.
- 대상은 공식 정답이 있고 CC BY 등 제3자 전송이 허용되는 공개 문서만 (configs/e03_external_sources.json의 license 확인).
- API 키는 요청 헤더에만 쓰고 출력·로그·파일에 남기지 않는다. 응답 원문은 data/raw/upstage_e03_diag/ (Git 제외).
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
OUT_DIR = ROOT / "data" / "raw" / "upstage_e03_diag"
BUDGET_PAGES = 4
FORM = {"model": "document-parse", "mode": "standard", "ocr": "auto", "output_formats": '["html", "markdown", "text"]', "coordinates": "true"}
SAFE_HEADERS = ("content-type", "content-length", "date", "x-request-id", "x-upstage-request-id")
ALLOWED_LICENSE_PREFIX = ("CC BY",)


def main() -> int:
    import pypdfium2 as pdfium
    doc_id = sys.argv[1]
    src = {s["id"]: s for s in json.loads((ROOT / "configs" / "e03_external_sources.json").read_text(encoding="utf-8"))["sources"]}[doc_id]
    truth = {d["doc_id"]: d for d in json.loads((ROOT / "data" / "canonical" / "external" / "e03_external_truth_v1.json").read_text(encoding="utf-8"))["documents"]}[doc_id]
    if src["format"] != "pdf" or not truth.get("truth"):
        print("PDF 공식 정답 문서가 아님 → 호출 안 함")
        return 3
    if not src["license"].startswith(ALLOWED_LICENSE_PREFIX):
        print("제3자 전송 허용 라이선스 확인 불가 → 호출 안 함")
        return 3
    path = ROOT / "data" / "raw" / "external_documents" / "pdf" / src["file"]
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != truth["sha256"]:
        print("입력 해시가 정답 기록과 다름 → 호출 안 함")
        return 3
    pages = len(pdfium.PdfDocument(str(path)))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUT_DIR / f"{doc_id}_call_log.json"
    if log_path.exists():
        print("이 문서는 이미 호출 기록이 있음 → 재호출 안 함")
        return 2
    used = sum(json.loads(p.read_text(encoding="utf-8")).get("pages_sent", 0) for p in OUT_DIR.glob("*_call_log.json"))
    if used + pages > BUDGET_PAGES:
        print(f"과금 상한 초과 예상 (이미 {used}쪽 + 이 문서 {pages}쪽 > {BUDGET_PAGES}쪽) → 호출 안 함")
        return 3
    key = get_upstage_api_key()
    if not key:
        print("UPSTAGE_API_KEY 미설정 → 호출 안 함")
        return 4
    record = {"purpose": "E03 실패 사례 진단 (E04 본 실험 아님)", "doc_id": doc_id, "file": src["file"], "sha256": truth["sha256"], "bytes": len(data),
              "pages_sent": pages, "license": src["license"], "endpoint": ENDPOINT, "form": FORM, "retries": 0, "concurrency": 1,
              "requested_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    log_path.write_text(json.dumps({**record, "status": "IN_PROGRESS"}, ensure_ascii=False, indent=2), encoding="utf-8")
    t0 = time.perf_counter()
    try:
        resp = requests.post(ENDPOINT, headers={"Authorization": f"Bearer {key}"},
                             files={"document": (src["file"], data, "application/pdf")}, data=FORM, timeout=120)
        record.update({"elapsed_seconds": round(time.perf_counter() - t0, 3), "http_status": resp.status_code,
                       "response_headers": {k: v for k, v in resp.headers.items() if k.lower() in SAFE_HEADERS}})
        if resp.ok:
            body = resp.json()
            rp = OUT_DIR / f"{doc_id}_response.json"
            rp.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
            record.update({"status": "SUCCESS", "response_file": rp.relative_to(ROOT).as_posix(), "response_sha256": hashlib.sha256(rp.read_bytes()).hexdigest(),
                           "model": body.get("model"), "api": body.get("api"), "usage": body.get("usage")})
        else:
            try:
                j = resp.json()
                e = j.get("error", j) if isinstance(j, dict) else {}
                cls = {k: e.get(k) for k in ("code", "type") if isinstance(e, dict) and k in e}
            except ValueError:
                cls = "응답 본문이 JSON 아님"
            record.update({"status": "HTTP_ERROR", "error_classification": cls})
    except requests.RequestException as exc:
        record.update({"status": "REQUEST_EXCEPTION", "elapsed_seconds": round(time.perf_counter() - t0, 3),
                       "error_classification": type(exc).__name__, "error_message": str(exc).replace(key, "***")[:300]})
    finally:
        del key
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: record.get(k) for k in ("status", "http_status", "elapsed_seconds", "pages_sent", "model", "usage", "error_classification")}, ensure_ascii=False))
    return 0 if record["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
