"""E00 pytest_report.xml 보정 (원본 보존, 보정본 별도 저장).

    .\\.venv\\Scripts\\python.exe scripts\\fix_e00_xml.py

E00 v1 실행(2026-10-20 10:02)의 pytest_report.xml은 hostname을 문자열 치환으로 `<HOST>`로 바꾸면서
XML이 깨졌다. 원본 파일은 그대로 두고, 복구·재마스킹한 결과를 pytest_report.repaired.xml로,
보정 기록을 xml_repair_record.json으로 남긴다. 테스트 결과 수치는 바꾸지 않는다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import check_environment as ce

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "results" / "E00_environment"
SRC = DIR / "pytest_report.xml"
DST = DIR / "pytest_report.repaired.xml"
REC = DIR / "xml_repair_record.json"


def _parse_error(text: str) -> str | None:
    try:
        ET.fromstring(text)
        return None
    except ET.ParseError as exc:
        return str(exc)


def main() -> int:
    raw = SRC.read_text(encoding="utf-8")
    original_error = _parse_error(raw)
    repaired = ce.repair_masked_junit_xml(raw) if original_error else ce.sanitize_junit_xml(raw)
    DST.write_text(repaired, encoding="utf-8", newline="\n")
    a, b = ET.fromstring(raw if not original_error else ce.repair_masked_junit_xml(raw)), ET.fromstring(repaired)
    suite = b if b.tag == "testsuite" else b.find("testsuite")
    record = {
        "experiment_id": "E00",
        "repaired_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {"file": SRC.name, "sha256": hashlib.sha256(SRC.read_bytes()).hexdigest(), "xml_parse_error": original_error,
                   "status": "보존 (수정하지 않음)"},
        "repaired": {"file": DST.name, "sha256": hashlib.sha256(DST.read_bytes()).hexdigest(), "xml_parse_error": _parse_error(repaired)},
        "method": "hostname 속성을 MASKED-HOST로, 날것의 <HOME>/<USER>/<HOST>를 이스케이프한 뒤 ElementTree로 파싱·재마스킹·직렬화 "
                  "(check_environment.repair_masked_junit_xml)",
        "test_counts_in_repaired": {k: suite.get(k) for k in ("tests", "failures", "errors", "skipped")},
        "testcase_count": len(list(b.iter("testcase"))),
        "cause": "run_e00.py(v1)가 hostname 값을 문자열 치환으로 '<HOST>'로 바꿔 XML 속성값에 '<'가 들어감",
        "fix_in_code": "run_e00.py, run_e01.py가 check_environment.sanitize_junit_xml 사용 (이후 실행분부터 적용)",
    }
    REC.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: record[k] for k in ("source", "repaired", "test_counts_in_repaired")}, ensure_ascii=False))
    return 0 if record["repaired"]["xml_parse_error"] is None else 1


if __name__ == "__main__":
    sys.exit(main())
