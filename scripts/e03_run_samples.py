"""E03 문서 샘플 실행: 입력 해시 검증 → 6개 문서 생성 → 독립 검증 → 재현성(바이트·구조·내용) → 결과 기록 → pytest.

    .\\.venv\\Scripts\\python.exe scripts\\e03_run_samples.py

상태는 RUNNING으로 기록한다. 직접 파서 비교·OCR·외부 API는 이 단계에서 하지 않는다.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "E03_document_parsers"

import check_environment as ce  # noqa: E402
import e03_generate_docs as G  # noqa: E402
import e03_validate_docs as V  # noqa: E402

LOC_REL = "data/canonical/e03_document_locations_v1.json"
TRUTH_REL = "data/canonical/e03_document_truth_v1.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def doc_files(truth: dict) -> list[dict]:
    return [d for d in truth["documents"] if d["doc_id"] in G.TARGET_DOCS]


def repro_root(base: Path) -> Path:
    (base / "data" / "canonical").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / TRUTH_REL, base / TRUTH_REL)
    return base


def main() -> int:
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    truth = json.loads((ROOT / TRUTH_REL).read_text(encoding="utf-8"))
    gen = G.generate()
    report = V.validate()
    docs = doc_files(truth)
    # 재현성: 임시 루트 2곳에서 다시 생성 → 바이트 / 구조(검증 서명) / 내용(위치 메타데이터 JSON)
    rels = [d["file"] for d in docs] + [LOC_REL]
    with tempfile.TemporaryDirectory(prefix="e03_r1_") as t1, tempfile.TemporaryDirectory(prefix="e03_r2_") as t2:
        roots = [repro_root(Path(t1)), repro_root(Path(t2))]
        for r in roots:
            G.generate(r)
        h = {str(i): {rel: sha(r / rel) for rel in rels} for i, r in enumerate(roots)}
        h["project"] = {rel: sha(ROOT / rel) for rel in rels}
        sigs = [V.extract_signature(V.validate(r)) for r in roots]
        locs = [json.loads((r / LOC_REL).read_text(encoding="utf-8")) for r in roots]
    proj_sig = V.extract_signature(report)
    proj_loc = json.loads((ROOT / LOC_REL).read_text(encoding="utf-8"))
    repro = {
        "method": "같은 입력으로 임시 폴더 2곳에 다시 생성해 프로젝트 산출물과 비교",
        "byte_level": {rel: {"run1_eq_run2": h["0"][rel] == h["1"][rel], "project_eq_rerun": h["project"][rel] == h["0"][rel]} for rel in rels},
        "structure_level": {"run1_eq_run2": sigs[0] == sigs[1], "project_eq_rerun": proj_sig == sigs[0],
                            "basis": "독립 검증 결과(항목별 상태·분자·분모)"},
        "content_level": {"run1_eq_run2": locs[0] == locs[1], "project_eq_rerun": proj_loc == locs[0],
                          "basis": "생성 위치 메타데이터 전체(블록·표 조각·셀 위치·도형 ID) + 검증기의 텍스트·셀 대조"},
        "fixation": "OOXML: zip 항목 시각·core.xml 시각 고정(e01_common.normalize_xlsx), 문서 속성 고정 / PDF: reportlab invariant=1(생성 시각·문서 ID 고정)",
    }
    repro["byte_level_all_match"] = all(v["run1_eq_run2"] and v["project_eq_rerun"] for v in repro["byte_level"].values())
    (OUT / "sample_reproducibility.json").write_text(json.dumps(repro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (OUT / "sample_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    # 매니페스트
    rows = []
    for d in docs:
        p = ROOT / d["file"]
        counts = Counter(v["status"] for k, v in report[d["doc_id"]].items() if not k.startswith("_"))
        rows.append({"doc_id": d["doc_id"], "file": d["file"], "format": d["format"], "content_set": d["content_set"],
                     "bytes": p.stat().st_size, "sha256": sha(p), "generation_method": d["method"],
                     "generator": "scripts/e03_generate_docs.py", "truth_ref": f"{TRUTH_REL}#{d['content_set']}",
                     "locations_ref": f"{LOC_REL}#{d['doc_id']}", "generation_seconds": f"{gen['generation_seconds'][d['doc_id']]:.4f}",
                     "PASS": counts["PASS"], "FAIL": counts["FAIL"], "NOT_MEASURED": counts["NOT_MEASURED"],
                     "NEEDS_MANUAL_REVIEW": counts["NEEDS_MANUAL_REVIEW"], "viewer_review": "미검수", "origin_class": "SYNTHETIC"})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    (OUT / "sample_manifest.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    # pytest
    xml_path = OUT / "pytest_report.xml"
    xml_path.unlink(missing_ok=True)
    py = subprocess.run([sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider", f"--junitxml={xml_path}"], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / "pytest_output.txt").write_text(ce.mask_sensitive(py.stdout + ("\n--- stderr ---\n" + py.stderr if py.stderr else "")),
                                           encoding="utf-8", newline="\n")
    tests = None
    if xml_path.exists():
        suite = ET.parse(xml_path).getroot()
        suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
        t = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
        tests = {"total": t["tests"], "passed": t["tests"] - t["failures"] - t["errors"] - t["skipped"], "failed": t["failures"],
                 "errors": t["errors"], "skipped": t["skipped"]}
        xml_path.write_text(ce.sanitize_junit_xml(xml_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        ET.parse(xml_path)
    pkgs = {}
    for name in ("python-docx", "reportlab", "python-pptx", "lxml", "pillow", "xlsxwriter", "charset-normalizer"):
        from importlib.metadata import version
        pkgs[name] = version(name)
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    meta = {
        "experiment_id": "E03", "status": "RUNNING",
        "phase": "1단계-b: 문서 샘플 6개 생성·독립 검증 (DOCX 2, 텍스트형 PDF 2, PPTX 2)",
        "run_timestamp": started, "git": {"base_commit": git_head},
        "inputs": {"ground_truth_v2_sha256": G.GT_SHA256, "truth_v1_sha256": G.TRUTH_SHA256, "truth_v1_unchanged": sha(ROOT / TRUTH_REL) == G.TRUTH_SHA256,
                   "truth_counts": G.EXPECTED_COUNTS, "count_correction": "텍스트 블록 13→11 (1단계 보고 오기 정정, 명세 파일은 불변)"},
        "outputs": {"documents": {r["doc_id"]: {"sha256": r["sha256"], "bytes": r["bytes"]} for r in rows},
                    "locations": {"file": LOC_REL, "sha256": sha(ROOT / LOC_REL), "version": "v1"}},
        "packages": pkgs,
        "excluded_this_phase": {"scan_pdf": "S-01·S-02 생성 보류 (OCR 우선순위 제외, 설계·명세는 보존)", "hwp_hwpx": "생성·변환·파싱 안 함 (미측정)",
                                "ocr": "설치·실험 안 함", "upstage_api": "호출 안 함", "parser_comparison": "시작 안 함"},
        "pdf": {"font": "Malgun Gothic 서브셋 임베드 (OS/2 fsType 8 = 편집 가능 임베딩 허용, 폰트 파일 저장소 미포함, Microsoft EULA 세부 조건 미확인)",
                "text_layer_check": "자체 최소 디코더로 ToUnicode 해독 — 외부 PDF 파서 추출 결과 아님", "iou_threshold_table": V.IOU_TABLE},
        "validation_status_counts": dict(Counter(v["status"] for it in report.values() for k, v in it.items() if not k.startswith("_"))),
        "reproducibility": {"byte_level_all_match": repro["byte_level_all_match"], "structure_level": repro["structure_level"],
                            "content_level": repro["content_level"]},
        "viewer_review": "미검수 (Word·PowerPoint·PDF 뷰어로 열어 본 적 없음)",
        "tests": tests,
        "failed_tests": [l.split(" ")[1] for l in py.stdout.splitlines() if l.startswith("FAILED ")],
    }
    if any("test_regeneration_is_byte_identical" in t for t in meta["failed_tests"]):
        meta["regression_diagnosis"] = {
            "test": "tests/test_e01_dataset.py::test_regeneration_is_byte_identical",
            "cause": "이번 단계에서 설치한 lxml 때문에 openpyxl이 xlsx XML을 lxml로 기록하게 되어(openpyxl.xml.LXML=True), "
                     "E01 생성기가 다시 만든 xlsx 4개의 내부 XML 바이트가 커밋된 E01 파일과 달라짐",
            "evidence": "셀 값은 4개 파일 모두 동일. 환경변수 OPENPYXL_LXML=False로 실행하면 E01 재생성 산출물 31개가 커밋본과 바이트 일치",
            "e01_data_changed": False,
            "fix_options": ["E01 생성 코드에서 openpyxl import 전에 OPENPYXL_LXML=False 지정 (E01 코드 변경 — 승인 필요)",
                            "tests/conftest.py에서 테스트 환경 고정 (테스트 인프라 변경 — 승인 필요)",
                            "E01 바이트 기준을 lxml 기록 결과로 다시 만들기 (E01 산출물 변경 — 비권장)"],
            "action_taken": "수정하지 않음 (E00~E02 코드 변경 금지 지시)",
        }
    (OUT / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (OUT / "summary.md").write_text(summary_md(meta, rows, report, repro), encoding="utf-8", newline="\n")
    fails = [(d, k) for d, it in report.items() for k, v in it.items() if not k.startswith("_") and v["status"] == "FAIL"]
    print(json.dumps({"fails": fails, "tests": tests, "byte_repro": repro["byte_level_all_match"],
                      "structure_repro": repro["structure_level"], "content_repro": repro["content_level"]}, ensure_ascii=False))
    return 0 if not fails and tests and not tests["failed"] and not tests["errors"] else 1


def summary_md(meta, rows, report, repro) -> str:
    L = ["# E03 결과 요약 — 1단계-b 문서 샘플 생성·독립 검증", "",
         f"> 자동 생성. 상태 **{meta['status']}**. 실행 {meta['run_timestamp']}, 기준 커밋 `{meta['git']['base_commit']}`", "",
         "- 1단계(설계·정답 명세) 산출물은 보존: `data/canonical/e03_document_truth_v1.json` (SHA-256 `982af3be…`, 변경 없음)",
         f"- 텍스트 블록 수 정정: {meta['inputs']['count_correction']}",
         f"- 제외: {'; '.join(f'{k}: {v}' for k, v in meta['excluded_this_phase'].items())}", "",
         "## 1. 생성 문서", "", "| 문서 | 형식 | 내용 | 크기(byte) | SHA-256 | 생성(s) | PASS | FAIL | 미측정 | 수동검수 필요 | 뷰어 검수 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    L += [f"| {r['doc_id']} | {r['format']} | {r['content_set']} | {r['bytes']:,} | `{r['sha256'][:16]}…` | {r['generation_seconds']} | "
          f"{r['PASS']} | {r['FAIL']} | {r['NOT_MEASURED']} | {r['NEEDS_MANUAL_REVIEW']} | {r['viewer_review']} |" for r in rows]
    L += ["", "## 2. 검증 항목별 결과", "", "| 항목 | " + " | ".join(r["doc_id"] for r in rows) + " |", "|---|" + "---|" * len(rows)]
    for k in V.ITEMS:
        cells = []
        for r in rows:
            v = report[r["doc_id"]][k]
            frac = f" {v['numerator']}/{v['denominator']}" if v.get("denominator") is not None else ""
            cells.append(v["status"] + frac)
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L += ["", "- PDF 텍스트 레이어: 자체 최소 디코더(ToUnicode)로 모든 셀·블록 텍스트를 해독해 확인. **외부 PDF 파서의 추출 정확도는 아님** (E03 파서 비교 단계)",
          "- 원본 위치: 생성 기록 위치를 저장된 파일 내부(OOXML 요소 순번·도형 ID, PDF 콘텐츠 스트림 좌표)와 대조한 결과. **파서가 추출한 위치의 정확도는 미측정**",
          "- 13_visual_layout: 뷰어 미검수 → 모두 NEEDS_MANUAL_REVIEW", "",
          "## 3. 재현성", "",
          f"- 바이트 단위: {'전 파일 일치' if repro['byte_level_all_match'] else '불일치 있음'} ({len(repro['byte_level'])}개 파일)",
          f"- 구조 단위: {repro['structure_level']}", f"- 내용 단위: {repro['content_level']}", f"- 고정 방법: {repro['fixation']}", "",
          "## 4. 테스트", "", f"- pytest: {meta['tests']}", f"- 실패 테스트: {meta['failed_tests'] or '없음'}"]
    if meta.get("regression_diagnosis"):
        r = meta["regression_diagnosis"]
        L += [f"- **회귀(E01)**: {r['test']} — {r['cause']}", f"  - 근거: {r['evidence']}", f"  - 조치: {r['action_taken']}",
              *[f"  - 수정 방안: {x}" for x in r["fix_options"]]]
    L += ["",
          "## 5. 패키지", "", f"- {meta['packages']}", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
