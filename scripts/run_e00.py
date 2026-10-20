"""E00 실행: 환경 점검(기본 + 2회) → 안정 필드 비교 → pytest → run_meta.json / summary.md 작성.

    .\\.venv\\Scripts\\python.exe scripts\\run_e00.py

실험 상태 판정 (evaluation_protocol.md §7):
- BLOCKED: 환경 점검 스크립트 또는 pytest가 실행되지 못함
- INVALID: 테스트 실패/오류, 안정 필드 불일치, 필수 필드 미측정
- COMPLETED: 위 문제가 모두 없음
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import check_environment as ce

ROOT = ce.PROJECT_ROOT
OUT = ROOT / "results" / "E00_environment"
LOCK = ROOT / "requirements.lock"


def _run(args: list[str], timeout: int = 600) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
        return {"command": " ".join(args), "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": " ".join(args), "returncode": None, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


def _git(failed: list[dict[str, Any]]) -> dict[str, Any]:
    def git(*args: str) -> str | None:
        r = _run(["git", "-c", "core.quotepath=false", *args], timeout=30)
        if r["returncode"] != 0:
            failed.append({"command": r["command"], "returncode": r["returncode"], "error": r["stderr"].strip()})
            return None
        return r["stdout"]

    status = git("status", "--short")
    remotes = git("remote", "-v")
    head = _run(["git", "rev-parse", "--verify", "HEAD"], timeout=30)
    commit = head["stdout"].strip() if head["returncode"] == 0 else None  # 커밋 없음 → null (오류 아님)
    return {
        "branch": (git("branch", "--show-current") or "").strip() or None,
        "commit": commit,
        "commit_note": None if commit else "커밋 없음 (최초 커밋은 사용자 승인 대기)",
        "status_short": status.splitlines() if status is not None else None,
        "remotes": remotes.splitlines() if remotes is not None else None,
    }


def _pytest_counts(xml_path: Path) -> dict[str, int] | None:
    if not xml_path.exists():
        return None
    root = ET.parse(xml_path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    tests, failures, errors, skipped = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    return {
        "total": tests,
        "passed": tests - failures - errors - skipped,
        "failed": failures,
        "errors": errors,
        "skipped": skipped,
    }


def _gb(n: int | None) -> str:
    return "미측정" if n is None else f"{n / 1024**3:.2f} GB"


def _v(x: Any) -> str:
    return "미측정" if x is None else str(x)


def main() -> int:
    if sys.prefix == sys.base_prefix or Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        print("ERROR: run with .venv\\Scripts\\python.exe")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    failed: list[dict[str, Any]] = []

    # 1) 환경 점검: 기본 출력 + 재현성 비교용 2회 (각각 별도 프로세스)
    check_runs = {}
    for name in ("env_check.json", "env_check_run1.json", "env_check_run2.json"):
        r = _run([sys.executable, str(ROOT / "scripts" / "check_environment.py"), "--output", str(OUT / name)], 120)
        check_runs[name] = r["returncode"]
        if r["returncode"] != 0:
            failed.append({"command": ce.mask_sensitive(r["command"]), "returncode": r["returncode"],
                           "error": ce.mask_sensitive(r["stderr"].strip())})
    checks_ok = all(rc == 0 for rc in check_runs.values())

    env = runs = diffs = None
    if checks_ok:
        env = json.loads((OUT / "env_check.json").read_text(encoding="utf-8"))
        runs = [json.loads((OUT / f"env_check_run{i}.json").read_text(encoding="utf-8")) for i in (1, 2)]
        diffs = ce.compare_stable(*runs)

    # 2) pytest (출력 로그와 junit xml 보존)
    xml_path = OUT / "pytest_report.xml"
    xml_path.unlink(missing_ok=True)
    py = _run([sys.executable, "-m", "pytest", "-v", f"--junitxml={xml_path}"])
    (OUT / "pytest_output.txt").write_text(
        ce.mask_sensitive(py["stdout"] + ("\n--- stderr ---\n" + py["stderr"] if py["stderr"] else "")),
        encoding="utf-8", newline="\n",
    )
    counts = _pytest_counts(xml_path)
    if xml_path.exists():
        # junit xml의 hostname 속성(PC 이름)과 홈 경로를 XML 구조를 유지한 채 마스킹 (2026-10-20 보정)
        xml_path.write_text(ce.sanitize_junit_xml(xml_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if py["returncode"] != 0:
        failed.append({"command": "python -m pytest -v", "returncode": py["returncode"],
                       "error": "테스트 실패 또는 실행 오류 — pytest_output.txt 참고"})

    # 3) 상태 판정
    reasons = []
    if not checks_ok:
        reasons.append("환경 점검 스크립트 실행 실패")
    if counts is None:
        reasons.append("pytest 결과(junit xml) 없음")
    blocked = bool(reasons)
    unmeasured_required = []
    if env is not None:
        unmeasured_required = [f for f in ce.REQUIRED_FIELDS if ce.get_path(env, f) is None]
    if counts and (counts["failed"] or counts["errors"]):
        reasons.append(f"테스트 실패 {counts['failed']}건, 오류 {counts['errors']}건")
    if diffs:
        reasons.append(f"안정 필드 불일치 {len(diffs)}건")
    if unmeasured_required:
        reasons.append(f"필수 필드 미측정: {unmeasured_required}")
    status = "BLOCKED" if blocked else ("INVALID" if reasons else "COMPLETED")

    git = _git(failed)
    meta = {
        "experiment_id": "E00",
        "experiment_name": "개발환경 및 재현성 확인",
        "run_timestamp": started,
        "status": status,
        "status_reasons": reasons,
        "os": None if env is None else {k: env["os"].get(k) for k in ("system", "edition", "display_version", "build", "machine")},
        "python_version": None if env is None else env["python"]["version"],
        "python_executable": None if env is None else env["python"]["executable"],
        "dependency_lock": {
            "file": LOCK.name,
            "sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest() if LOCK.exists() else None,
        },
        "git": git,
        "tests": counts,
        "reproducibility": {
            "method": "check_environment.py를 같은 가상환경에서 별도 프로세스로 2회 실행 후 STABLE_FIELDS 비교",
            "compared_files": ["env_check_run1.json", "env_check_run2.json"],
            "stable_fields": list(ce.STABLE_FIELDS),
            "excluded_volatile_fields": list(ce.VOLATILE_FIELDS),
            "match": None if diffs is None else diffs == [],
            "differences": diffs,
        },
        "collection_errors": None if env is None else env["errors"],
        "failed_commands": ce.mask_sensitive(failed),
        "artifacts": ["env_check.json", "env_check_run1.json", "env_check_run2.json",
                      "pytest_output.txt", "pytest_report.xml", "run_meta.json", "summary.md"],
    }
    ce.write_json(meta, OUT / "run_meta.json")
    (OUT / "summary.md").write_text(_summary(meta, env), encoding="utf-8", newline="\n")
    print(f"E00 status={status} tests={counts} reproducible={meta['reproducibility']['match']}")
    return 0 if status == "COMPLETED" else 1


def _summary(meta: dict[str, Any], env: dict[str, Any] | None) -> str:
    t = meta["tests"] or {}
    rep = meta["reproducibility"]
    lines = [
        "# E00 결과 요약 — 개발환경 및 재현성 확인",
        "",
        "> scripts/run_e00.py가 측정값으로 자동 생성한 문서다. 측정하지 못한 값은 `미측정`으로 표기한다.",
        "",
        f"- 실행 일시: {meta['run_timestamp']}",
        f"- 실험 상태: **{meta['status']}**" + (f" — {'; '.join(meta['status_reasons'])}" if meta["status_reasons"] else ""),
        "",
        "## 환경 (env_check.json)",
        "",
        "| 항목 | 값 |",
        "|---|---|",
    ]
    if env is None:
        lines.append("| 전체 | 미측정 (환경 점검 실행 실패) |")
    else:
        mem = env["memory"]
        rows = [
            ("Python", f"{_v(env['python']['version'])} ({_v(env['python']['implementation'])}, {_v(env['python']['bits'])}bit)"),
            ("Python 실행 경로", f"`{_v(env['python']['executable'])}`"),
            ("가상환경 사용 / 프로젝트 .venv", f"{_v(env['venv']['in_venv'])} / {_v(env['venv']['is_project_venv'])}"),
            ("전역 site-packages 포함", _v(env["venv"]["include_system_site_packages"])),
            ("OS", f"{_v(env['os']['system'])} {_v(env['os']['release'])} {_v(env['os']['edition'])} {_v(env['os']['display_version'])} (빌드 {_v(env['os']['build'])}, {_v(env['os']['machine'])})"),
            ("CPU", _v(env["cpu"]["model"])),
            ("물리 / 논리 코어", f"{_v(env['cpu']['physical_cores'])} / {_v(env['cpu']['logical_cores'])}"),
            ("전체 RAM", _gb(mem["total_bytes"])),
            ("실행 시점 가용 RAM", f"{_gb(mem['available_bytes'])} ({_v(mem['available_percent'])}%)"),
            ("pytest / psutil", f"{_v(env['packages']['pytest'])} / {_v(env['packages']['psutil'])}"),
            ("Git", _v(env["git"]["version"]) if env["git"]["installed"] else "미설치"),
            ("프로젝트 루트", f"`{_v(env['project_root']['path'])}` (Git 저장소: {_v(env['project_root']['is_git_repo'])})"),
            ("수집 오류 건수", str(len(env["errors"]))),
        ]
        lines += [f"| {k} | {v} |" for k, v in rows]
        lines += [
            "",
            f"> 가용 RAM: 측정 시점 전체의 {_v(mem['available_percent'])}%. 메모리 확보를 위한 프로세스 종료·시스템 설정 변경은 하지 않았다. "
            "이후 성능 측정 실험에서는 측정 당시 가용 RAM을 함께 기록한다.",
        ]
    lines += [
        "",
        "## 재현성",
        "",
        f"- 방법: {rep['method']}",
        f"- 비교 필드 수: {len(rep['stable_fields'])} / 제외(변동) 필드: {', '.join(rep['excluded_volatile_fields'])}",
        f"- 결과: {'미측정' if rep['match'] is None else ('일치' if rep['match'] else '불일치')}",
    ]
    for d in rep["differences"] or []:
        lines.append(f"  - `{d['field']}`: {d['reason']} (run1={d['run1']!r}, run2={d['run2']!r})")
    lines += [
        "",
        "## 테스트 (pytest)",
        "",
        f"- 전체 {_v(t.get('total'))} / 통과 {_v(t.get('passed'))} / 실패 {_v(t.get('failed'))} / 오류 {_v(t.get('errors'))} / 스킵 {_v(t.get('skipped'))}",
        "- 상세 로그: `pytest_output.txt`, `pytest_report.xml`",
        "",
        "## Git",
        "",
        f"- 브랜치: {_v(meta['git']['branch'])} / 커밋: {meta['git']['commit'] or meta['git']['commit_note']}",
        f"- 원격 저장소: {'없음' if meta['git']['remotes'] == [] else _v(meta['git']['remotes'])}",
        "",
        "## 실패 명령",
        "",
    ]
    lines += [f"- `{f['command']}` (exit {f['returncode']}): {f['error']}" for f in meta["failed_commands"]] or ["- 없음"]
    lines += ["", "## 의존성 잠금", "", f"- `{meta['dependency_lock']['file']}` sha256 `{_v(meta['dependency_lock']['sha256'])}`", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
