"""E01 실행: 생성 → 기대값(A) → 오류 주입 → 독립 검증(B) → 재현성 → 민감정보 검사 → pytest → 결과 기록.

    .\\.venv\\Scripts\\python.exe scripts\\run_e01.py

상태는 사용자 승인(DEC-20261020-07)에 따라 COMPLETED로 기록한다. 검증·테스트·재현성이 실패하면 종료코드 1.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import e01_expected
import e01_generate
import e01_inject_errors
import e01_verify
from e01_common import GT_VERSION, PROJECT_ROOT, SEED, Paths, read_json, sha256_file, write_json

ROOT = PROJECT_ROOT
OUT = ROOT / "results" / "E01_dataset"

# 생성 산출물 (재현성 비교 대상). 공개 원본 스테이징은 Git 미추적 경로이므로 별도 표기
GT_REL = f"data/canonical/ground_truth_{GT_VERSION}.json"
GENERATED = [
    GT_REL, "data/canonical/injected_errors_v1.json",
    "data/canonical/vendor_column_map_v1.json", "data/canonical/vendor_id_map_v1.csv", "data/canonical/vendor_row_map_v1.csv",
    *[f"data/vendor_a/{n}" for n in ("products.csv", "materials.csv", "suppliers.csv", "supplier_materials.csv", "bom.csv",
                                     "inventory.csv", "orders.csv", "resources.csv", "routing.csv", "vendor_a_master.xlsx")],
    *[f"data/vendor_b/{n}" for n in ("vendor_b_master.xlsx", "vendor_b_orders.csv", "vendor_b_inventory.csv")],
]
GENERATED_INVALID = [p.replace("data/vendor_", "data/invalid/vendor_") for p in GENERATED if p.startswith("data/vendor_")]
METHOD = {
    GT_REL: ("SYNTHETIC (+UCI 배분 SYNTHETIC/ALLOCATED)", "e01_generate.py + e01_expected.py"),
    "data/canonical/injected_errors_v1.json": ("SYNTHETIC_INJECTED 목록", "e01_inject_errors.py"),
    "data/canonical/vendor_column_map_v1.json": ("매핑 규칙", "e01_generate.py"),
    "data/canonical/vendor_id_map_v1.csv": ("매핑 규칙", "e01_generate.py"),
    "data/canonical/vendor_row_map_v1.csv": ("매핑 규칙", "e01_generate.py"),
}


def pipeline(paths: Paths) -> None:
    e01_generate.generate(paths)
    e01_expected.compute(paths)
    e01_inject_errors.inject(paths)


def hashes(root: Path, rels: list[str]) -> dict[str, str]:
    return {r: sha256_file(root / r) for r in rels}


def sensitive_scan(files: list[Path]) -> dict:
    home = str(Path.home())
    user = Path.home().name
    patterns = {
        "home_path": re.compile(re.escape(home), re.I),
        "home_path_json": re.compile(re.escape(home.replace("\\", "\\\\")), re.I),
        "user_dir": re.compile(rf"(?i)users[\\/]+{re.escape(user)}\b"),
        "api_key_like": re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
        "personal_email": re.compile(r"[A-Za-z0-9._%+-]+@(gmail|naver|daum|hanmail)\.(com|net)"),
        "private_doc_terms": re.compile("위원회 평가|평가결과|참가신청서|업무분장\\.docx"),
    }
    # 팀원 실명 등 공개하면 안 되는 검사어는 Git 미추적 로컬 파일에서만 읽는다 (configs/*.local.* 는 .gitignore 대상)
    local_terms = ROOT / "configs" / "sensitive_terms.local.txt"
    terms = [t.strip() for t in local_terms.read_text(encoding="utf-8").splitlines() if t.strip()] if local_terms.exists() else []
    if terms:
        patterns["local_sensitive_terms"] = re.compile("|".join(map(re.escape, terms)))
    import socket
    host = socket.gethostname()
    if host:
        patterns["hostname"] = re.compile(re.escape(host), re.I)
    hits = []
    for f in files:
        data = f.read_bytes()
        texts = []
        if f.suffix == ".xlsx":
            import zipfile
            with zipfile.ZipFile(f) as z:
                texts = [z.read(n).decode("utf-8", "replace") for n in z.namelist()]
        else:
            for enc in ("utf-8", "cp949"):
                try:
                    texts = [data.decode(enc)]
                    break
                except UnicodeDecodeError:
                    continue
        for name, rx in patterns.items():
            if any(rx.search(t) for t in texts):
                hits.append({"file": str(f.relative_to(ROOT)).replace("\\", "/"), "pattern": name})
    return {"scanned_files": len(files), "hits": hits, "patterns": sorted(patterns), "local_terms_loaded": len(terms)}


def main() -> int:
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    failed_commands = []
    paths = Paths()
    pipeline(paths)
    # 재현성: 임시 루트 2곳에서 다시 생성해 바이트 단위 해시 비교
    with tempfile.TemporaryDirectory(prefix="e01_repro_") as t1, tempfile.TemporaryDirectory(prefix="e01_repro_") as t2:
        pipeline(Paths(Path(t1)))
        pipeline(Paths(Path(t2)))
        rels = GENERATED + GENERATED_INVALID
        h_main, h1, h2 = hashes(ROOT, rels), hashes(Path(t1), rels), hashes(Path(t2), rels)
    repro = {"method": "같은 시드로 임시 폴더 2곳에 전체 파이프라인을 다시 실행해 산출물 SHA-256을 프로젝트 산출물과 비교",
             "files_compared": len(rels),
             "mismatch_run1_vs_run2": sorted(r for r in rels if h1[r] != h2[r]),
             "mismatch_project_vs_rerun": sorted(r for r in rels if h_main[r] != h1[r])}
    repro["match"] = not repro["mismatch_run1_vs_run2"] and not repro["mismatch_project_vs_rerun"]
    report = e01_verify.run(paths)
    # UCI 원본 검증 기록
    insp = subprocess.run([sys.executable, str(ROOT / "scripts" / "e01_inspect_uci.py")], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    if insp.returncode != 0:
        failed_commands.append({"command": "python scripts/e01_inspect_uci.py", "returncode": insp.returncode, "error": insp.stderr[-500:]})
    uci = read_json(OUT / "uci_source_verification.json")
    # pytest 전체 (E00 + E01)
    xml_path = OUT / "pytest_report.xml"
    xml_path.unlink(missing_ok=True)
    py = subprocess.run([sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider", f"--junitxml={xml_path}"], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    from e01_common import PROJECT_ROOT as _pr  # noqa: F401
    import check_environment as ce
    (OUT / "pytest_output.txt").write_text(ce.mask_sensitive(py.stdout + ("\n--- stderr ---\n" + py.stderr if py.stderr else "")),
                                           encoding="utf-8", newline="\n")
    if xml_path.exists():
        suite = ET.parse(xml_path).getroot()  # 마스킹 전에 개수 파싱
        suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
        t = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
        xml_path.write_text(ce.sanitize_junit_xml(xml_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        ET.parse(xml_path)  # 마스킹 후에도 올바른 XML인지 확인
        tests = {"total": t["tests"], "passed": t["tests"] - t["failures"] - t["errors"] - t["skipped"], "failed": t["failures"],
                 "errors": t["errors"], "skipped": t["skipped"]}
    else:
        tests = None
    if py.returncode != 0:
        failed_commands.append({"command": "python -m pytest -v", "returncode": py.returncode, "error": "pytest_output.txt 참고"})
    # 매니페스트
    rows = []
    for rel in GENERATED + GENERATED_INVALID:
        origin, method = METHOD.get(rel, ("SYNTHETIC_INJECTED" if "/invalid/" in rel else "SYNTHETIC (Vendor 표현)",
                                          "e01_inject_errors.py" if "/invalid/" in rel else "e01_generate.py"))
        rows.append([rel, (ROOT / rel).stat().st_size, sha256_file(ROOT / rel), origin, method, SEED, "예"])
    v1 = paths.ground_truth_v1
    if v1.exists():
        rows.append(["data/canonical/ground_truth_v1.json", v1.stat().st_size, sha256_file(v1), "이전 정답셋 v1 (보존)",
                     "v1 코드로 생성, 재생성 대상 아님", SEED, "예"])
    raw_dir = ROOT / "data" / "raw" / "public" / "uci_daily_demand"
    for rel in ("daily+demand+forecasting+orders.zip", "extracted/Daily_Demand_Forecasting_Orders.csv",
                "download_record.json", "staging_uci_daily_orders_v1.json"):
        p = raw_dir / rel
        if p.exists():
            origin = "PUBLIC_REAL (원본)" if not rel.endswith(".json") else ("다운로드 기록" if "download" in rel else "PUBLIC_REAL 스테이징")
            method = "e01_download_uci.py (UCI 공식 출처)" if "staging" not in rel else "e01_generate.py (원본 값 그대로)"
            rows.append([f"data/raw/public/uci_daily_demand/{rel}", p.stat().st_size, sha256_file(p), origin, method, "", "아니오 (Git 미추적)"])
    for rel in ("results/E01_dataset/uci_source_verification.json", "results/E01_dataset/validation_report.json"):
        rows.append([rel, (ROOT / rel).stat().st_size, sha256_file(ROOT / rel), "검증 기록",
                     "e01_inspect_uci.py" if "uci" in rel else "e01_verify.py", "", "예"])
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    w = _csv.writer(buf, lineterminator="\n")
    w.writerow(["path", "bytes", "sha256", "origin_class", "generation_method", "seed", "git_tracked"])
    w.writerows(rows)
    (OUT / "dataset_manifest.csv").write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    scan_targets = [ROOT / r[0] for r in rows if r[6] == "예"] + [OUT / "dataset_manifest.csv"]
    scan = sensitive_scan(scan_targets)
    gt = read_json(paths.ground_truth)
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    git_status = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--short"], cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8").stdout.splitlines()
    e00_fix = ROOT / "results" / "E00_environment" / "xml_repair_record.json"
    meta = {
        "experiment_id": "E01", "experiment_name": "제조업 공통 합성 데이터·정답셋 구성",
        "ground_truth": {"version": GT_VERSION, "file": GT_REL, "sha256": sha256_file(paths.ground_truth),
                         "previous": gt["dataset"]["previous_version"],
                         "previous_sha256_actual": sha256_file(paths.ground_truth_v1) if paths.ground_truth_v1.exists() else None},
        "e00_xml_repair": read_json(e00_fix) if e00_fix.exists() else None,
        "status": "COMPLETED",
        "status_note": "2026-10-20 사용자 승인 (decisions.md DEC-20261020-07). 승인 기준: 독립 검증 143/143, pytest 48/48, "
                       "재현성 31/31, Git 보안 점검 통과. 계획안 비교는 v2 규칙이 PoC 기준(v1 보존)",
        "limitations": ["반제품 생산능력 부족은 완제품 공급(납기) 계산에 반영하지 않는다 (합성 시나리오 단순화)",
                        "가상 외주처 조건(FG003만, 150 EA/주, 리드타임 7일, 자재 외주처 부담)은 합성 가정이다",
                        "모든 마스터·주문·재고·비용 값은 합성값이며 현장 성능을 나타내지 않는다"],
        "run_timestamp": started, "seed": SEED, "python": sys.version.split()[0],
        "dependency_lock": {"file": "requirements.lock", "sha256": sha256_file(ROOT / "requirements.lock")},
        "git": {"base_commit": git_head, "uncommitted_changes": git_status},
        "record_counts": gt["dataset"]["record_counts"],
        "uci_source": {"rows": uci["row_count"], "columns": uci["column_count"], "delimiter": uci["delimiter"],
                       "encoding": uci["encoding"], "zip_sha256": (uci.get("download_record") or {}).get("zip", {}).get("sha256"),
                       "csv_sha256": uci["file"]["sha256"],
                       "relationship_checks": [{k: c[k] for k in ("relation", "exact_match_rows", "rows")} for c in uci["relationship_checks"]]},
        "validation": report["summary"], "injection": report["injection"], "cq_status": report["cq_status"],
        "reproducibility": repro, "sensitive_scan": scan, "tests": tests, "failed_commands": failed_commands,
    }
    write_json(OUT / "run_meta.json", meta)
    (OUT / "summary.md").write_text(summary_md(meta, gt, uci), encoding="utf-8", newline="\n")
    print(json.dumps({"validation": report["summary"]["passed"], "failed": report["summary"]["failed"],
                      "repro": repro["match"], "tests": tests, "sensitive_hits": len(scan["hits"])}, ensure_ascii=False))
    return 0 if report["summary"]["failed"] == 0 and repro["match"] and tests and not tests["failed"] and not tests["errors"] else 1


def summary_md(meta: dict, gt: dict, uci: dict) -> str:
    X = gt["expected"]
    v = meta["validation"]
    L = ["# E01 결과 요약 — 제조업 공통 합성 데이터·정답셋", "",
         f"> scripts/run_e01.py가 실행 결과로 자동 생성한 문서다. 실험 상태: **{meta['status']}** — {meta['status_note']}", "",
         "**한계 (합성 시나리오)**", "", *[f"- {x}" for x in meta["limitations"]], "",
         f"- 실행 일시: {meta['run_timestamp']} / 시드: {meta['seed']} / 기준 커밋: {meta['git']['base_commit']}", "",
         "## 1. UCI 원본 (PUBLIC_REAL, Git 미추적)", "",
         f"- 행 {uci['row_count']} × 열 {uci['column_count']}, 구분자 `{uci['delimiter']}`, 인코딩 {uci['encoding']}, 줄바꿈 {uci['line_ending']}",
         f"- zip SHA-256 `{meta['uci_source']['zip_sha256']}` / CSV SHA-256 `{meta['uci_source']['csv_sha256']}`",
         f"- 헤더 주의: {'; '.join(uci['header_notes']) or '없음'}"]
    for c in uci["relationship_checks"]:
        L.append(f"- `{c['relation']}`: {c['exact_match_rows']}/{c['rows']}행 정확 일치")
    L += [f"- 요일 코드 의미: 미확인 (코드는 숫자 그대로 보존, 생성 날짜는 합성값). 코드 숫자 패턴 단절(파일 행): {uci['day_sequence']['pattern_breaks_at_file_lines']}", "",
          "## 2. 합성 데이터 레코드 수", "", "| 엔터티 | 레코드 |", "|---|---|"]
    L += [f"| {k} | {n} |" for k, n in meta["record_counts"].items()]
    L += ["", "## 3. 검증 결과 (구현 B, validation_report.json)", "",
          f"- 전체 {v['total']} / 통과 {v['passed']} / 실패 {v['failed']}", "", "| 영역 | 통과 | 실패 |", "|---|---|---|"]
    L += [f"| {s} | {x['passed']} | {x['failed']} |" for s, x in v["by_section"].items()]
    inj = meta["injection"]
    L += ["", f"- 오류 주입: {inj['injected']}건 주입 / {inj['confirmed']}건 독립 확인", "",
          "## 4. 주요 경영 의사결정 계산 (기대값, A=B 일치 여부는 3절)", "", "| 품목 | 생산 필요량 | 적용 BOM |", "|---|---|---|"]
    L += [f"| {p} | {r['net_requirement']} | {r['bom_id'] or '-'} |" for p, r in X["production_requirements"].items()]
    L += ["", "| 자재 | 총소요량 | 가용 | 안전재고 | 부족량 | 단위 |", "|---|---|---|---|---|---|"]
    L += [f"| {m} | {s['gross']} | {s['available']} | {s['safety_stock']} | {s['shortage']} | {s['unit']} |" for m, s in X["material_shortage"].items()]
    feas = X["order_feasibility"]
    L += ["", f"- 주문 납기 판정 (OPEN {len(feas)}건): 가능 {sum(r['feasible'] for r in feas)}건 / 불가 {sum(not r['feasible'] for r in feas)}건",
          "", f"### 계획안 비교 (정답셋 {meta['ground_truth']['version']})", "",
          "| 계획안 | 자재비 | 정규 생산비 | 잔업비 | 외주비 | 합계(참고) | 사내 필요(h) | 잔업(h) | 능력초과(h) | 외주량 | 미생산 | 납기지연 주문 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for pid, p in X["plan_evaluation"].items():
        c = p["costs_krw"]
        oq = sum(int(v) for v in p["outsourced_qty"].values())
        L.append(f"| {pid} | {c['material']} | {c['regular_production']} | {c['overtime']} | {c['outsourcing']} | "
                 f"{c['sum_of_computed_items_reference']} | {p['inhouse_required_h']} | {p['worked_overtime_h']} | "
                 f"{p['capacity_excess_total_h']} | {oq} | {p['unproduced_qty_total']} | {len(p['late_orders'])} |")
    v1 = Paths().ground_truth_v1
    if v1.exists():
        old = read_json(v1)["expected"]["plan_evaluation"]
        L += ["", "### 수정 전(v1, 보존) 계획안 결과 — 참고", "",
              "| 계획안 | 자재비 | 정규 | 잔업 | 외주 | 합계 | 능력초과(h) | 납기위험 주문(v1 정의) |", "|---|---|---|---|---|---|---|---|"]
        for pid, p in old.items():
            c = p["costs_krw"]
            L.append(f"| {pid} | {c['material']} | {c['regular_production']} | {c['overtime']} | {c['outsourcing']} | "
                     f"{c['sum_of_computed_items_reference']} | {p['capacity_excess_total_h']} | {len(p['orders_at_risk'])} |")
        L += ["", "- v1 결함: 잔업안에서 FG002 라인 전체를 잔업 버킷(주 10h)에만 넣어 정규시간을 쓰지 않았기 때문에 능력 초과가 정규안보다 커졌다 "
              "(36.5h → 45h). v2는 잔업을 '정규 + 추가 가용시간'으로 계산한다.",
              "- v2 외주안의 납기지연 증가 원인: 가상 외주처 리드타임 7일 때문에 주 시작일에 맡긴 외주 수량이 다음 주 월요일에 입고되어, "
              "그 주 안에 납기가 있는 주문을 맞추지 못한다 (능력 초과는 36.5h → 18h로 감소)."]
    L += ["", "- 재고 유지비·지연 페널티: 미산정 (기준 미확정)", "", "## 5. CQ 상태", ""]
    L += [f"- {k}: {s}" for k, s in sorted(meta["cq_status"].items())]
    r = meta["reproducibility"]
    t = meta["tests"] or {}
    L += ["", "## 6. 재현성·테스트·민감정보", "",
          f"- 재현성: {'일치' if r['match'] else '불일치'} ({r['files_compared']}개 파일, 불일치 {r['mismatch_run1_vs_run2'] + r['mismatch_project_vs_rerun']})",
          f"- pytest: 전체 {t.get('total', '미측정')} / 통과 {t.get('passed', '미측정')} / 실패 {t.get('failed', '미측정')} / 오류 {t.get('errors', '미측정')} / 스킵 {t.get('skipped', '미측정')}",
          f"- 민감정보 검사: {meta['sensitive_scan']['scanned_files']}개 파일, 검출 {len(meta['sensitive_scan']['hits'])}건",
          f"- 정답셋: {meta['ground_truth']['file']} sha256 `{meta['ground_truth']['sha256']}` / 이전 v1 sha256 `{meta['ground_truth']['previous_sha256_actual']}` (보존)",
          f"- E00 XML 보정: {('보정본 파싱 가능, 원본 보존' if meta['e00_xml_repair'] and meta['e00_xml_repair']['repaired']['xml_parse_error'] is None else '미실행 또는 실패')}",
          f"- 실패 명령: {meta['failed_commands'] or '없음'}", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
