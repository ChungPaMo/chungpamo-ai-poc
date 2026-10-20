"""E00 개발환경 점검.

가상환경을 활성화하지 않고 명시적 경로로 실행한다.

    .\\.venv\\Scripts\\python.exe scripts\\check_environment.py [--output PATH]

수집에 실패한 항목은 값을 null로 두고 `errors`에 필드·명령·오류를 기록한다(조용히 생략하지 않음).
출력 문자열의 사용자 홈 경로·사용자 이름은 마스킹한다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata as md
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "results" / "E00_environment" / "env_check.json"
SCHEMA_VERSION = 1

# 출력 JSON에 반드시 존재해야 하는 필드 (값이 null이면 errors에 사유가 있어야 함)
REQUIRED_FIELDS = (
    "experiment_id",
    "run_timestamp",
    "python.executable",
    "python.version",
    "os.system",
    "os.version",
    "cpu.model",
    "cpu.physical_cores",
    "cpu.logical_cores",
    "memory.total_bytes",
    "memory.available_bytes",
    "venv.in_venv",
    "venv.is_project_venv",
    "packages.pytest",
    "packages.psutil",
    "git.installed",
    "git.version",
    "project_root.path",
    "errors",
)

# 재현성 비교 대상: 실행마다 바뀌지 않아야 하는 필드
STABLE_FIELDS = (
    "python.executable",
    "python.version",
    "python.implementation",
    "python.bits",
    "os.system",
    "os.release",
    "os.version",
    "os.edition",
    "os.display_version",
    "os.machine",
    "cpu.model",
    "cpu.physical_cores",
    "cpu.logical_cores",
    "memory.total_bytes",
    "venv.in_venv",
    "venv.is_project_venv",
    "venv.include_system_site_packages",
    "packages.pytest",
    "packages.psutil",
    "packages.installed",
    "git.installed",
    "git.version",
    "project_root.path",
    "project_root.name",
    "project_root.is_git_repo",
)

# 비교에서 제외하는 변동 필드 (기록용)
VOLATILE_FIELDS = (
    "run_timestamp",
    "elapsed_seconds",
    "memory.available_bytes",
    "memory.available_percent",
    "errors",
)

_MISSING = "<missing>"
_USER_DIR_RE = re.compile(r"(?i)([a-z]:[\\/]+users[\\/]+)([^\\/\"'\s]+)")


def mask_sensitive(value: Any) -> Any:
    """문자열 안의 사용자 홈 경로를 <HOME>으로, 그 밖의 C:\\Users\\<이름>을 <USER>로 바꾼다."""
    if isinstance(value, str):
        home = str(Path.home())
        for variant in sorted({home, home.replace("\\", "/")}, key=len, reverse=True):
            value = re.sub(re.escape(variant), "<HOME>", value, flags=re.IGNORECASE)
        return _USER_DIR_RE.sub(r"\1<USER>", value)
    if isinstance(value, dict):
        return {k: mask_sensitive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_sensitive(v) for v in value]
    return value


class Collector:
    """항목별 수집 함수를 실행하고 실패를 errors에 남긴다."""

    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []

    def get(self, field: str, fn: Callable[[], Any], command: str | None = None) -> Any:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - 어떤 실패든 기록 후 계속 수집
            self.record(field, f"{type(exc).__name__}: {exc}", command)
            return None

    def record(self, field: str, error: str, command: str | None = None, status: str = "미측정") -> None:
        self.errors.append({"field": field, "status": status, "command": command, "error": error})


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
    )


def _run_ok(args: list[str], cwd: Path | None = None) -> str:
    proc = _run(args, cwd)
    if proc.returncode != 0:
        raise RuntimeError(f"exit {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _winreg_value(key_path: str, name: str) -> Any:
    import winreg

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
        return winreg.QueryValueEx(key, name)[0]


_WIN_CURRENT_VERSION = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
_WIN_CPU0 = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"


def _python_info(c: Collector) -> dict[str, Any]:
    return {
        "executable": sys.executable,
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "bits": 64 if sys.maxsize > 2**32 else 32,
    }


def _os_info(c: Collector) -> dict[str, Any]:
    is_windows = sys.platform == "win32"
    info: dict[str, Any] = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "edition": None,
        "display_version": None,
        "build": None,
    }
    if is_windows:
        info["edition"] = c.get("os.edition", platform.win32_edition, "platform.win32_edition()")
        info["display_version"] = c.get(
            "os.display_version",
            lambda: _winreg_value(_WIN_CURRENT_VERSION, "DisplayVersion"),
            rf"HKLM\{_WIN_CURRENT_VERSION}\DisplayVersion",
        )
        build = c.get(
            "os.build",
            lambda: f"{_winreg_value(_WIN_CURRENT_VERSION, 'CurrentBuildNumber')}."
            f"{_winreg_value(_WIN_CURRENT_VERSION, 'UBR')}",
            rf"HKLM\{_WIN_CURRENT_VERSION}\CurrentBuildNumber,UBR",
        )
        info["build"] = build
    else:
        for field in ("os.edition", "os.display_version", "os.build"):
            c.record(field, "Windows 전용 항목", status="해당없음")
    return info


def _cpu_info(c: Collector) -> dict[str, Any]:
    import psutil

    if sys.platform == "win32":
        model = c.get(
            "cpu.model",
            lambda: str(_winreg_value(_WIN_CPU0, "ProcessorNameString")).strip(),
            rf"HKLM\{_WIN_CPU0}\ProcessorNameString",
        )
    else:
        model = platform.processor() or None
        if model is None:
            c.record("cpu.model", "platform.processor()가 빈 값을 반환", "platform.processor()")
    physical = c.get("cpu.physical_cores", lambda: psutil.cpu_count(logical=False), "psutil.cpu_count(logical=False)")
    if physical is None and not any(e["field"] == "cpu.physical_cores" for e in c.errors):
        c.record("cpu.physical_cores", "psutil이 None을 반환", "psutil.cpu_count(logical=False)")
    logical = os.cpu_count()
    if logical is None:
        c.record("cpu.logical_cores", "os.cpu_count()가 None을 반환", "os.cpu_count()")
    return {"model": model, "physical_cores": physical, "logical_cores": logical}


def _memory_info(c: Collector) -> dict[str, Any]:
    vm = c.get("memory", lambda: __import__("psutil").virtual_memory(), "psutil.virtual_memory()")
    if vm is None:
        return {"total_bytes": None, "available_bytes": None, "available_percent": None}
    return {
        "total_bytes": vm.total,
        "available_bytes": vm.available,
        "available_percent": round(vm.available / vm.total * 100, 1),
    }


def _venv_info(c: Collector) -> dict[str, Any]:
    prefix = Path(sys.prefix).resolve()
    base = Path(sys.base_prefix).resolve()
    expected = (PROJECT_ROOT / ".venv").resolve()
    include_system = None
    cfg = prefix / "pyvenv.cfg"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            key, sep, val = line.partition("=")
            if sep and key.strip() == "include-system-site-packages":
                include_system = val.strip().lower() == "true"
        if include_system is None:
            c.record("venv.include_system_site_packages", "pyvenv.cfg에 항목 없음", str(cfg))
    else:
        c.record("venv.include_system_site_packages", "pyvenv.cfg 없음 (가상환경 아님)", str(cfg))
    return {
        "in_venv": prefix != base,
        "is_project_venv": prefix == expected,
        "prefix": str(prefix),
        "base_prefix": str(base),
        "include_system_site_packages": include_system,
    }


def _normalize_dist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _packages_info(c: Collector) -> dict[str, Any]:
    info: dict[str, Any] = {}
    for name in ("pytest", "psutil"):
        info[name] = c.get(f"packages.{name}", lambda n=name: md.version(n), f"importlib.metadata.version({name!r})")
    info["installed"] = c.get(
        "packages.installed",
        lambda: dict(sorted({_normalize_dist_name(d.metadata["Name"]): d.version for d in md.distributions()}.items())),
        "importlib.metadata.distributions()",
    )
    return info


def _git_info(c: Collector) -> dict[str, Any]:
    if shutil.which("git") is None:
        c.record("git.version", "PATH에서 git을 찾을 수 없음", "git --version", status="미설치")
        return {"installed": False, "version": None}
    version = c.get("git.version", lambda: _run_ok(["git", "--version"]).removeprefix("git version ").strip(), "git --version")
    return {"installed": True, "version": version}


def _project_info(c: Collector, git_installed: bool) -> dict[str, Any]:
    is_repo = None
    if git_installed:
        # 저장소가 아니면 exit 128 → False (오류가 아님)
        is_repo = c.get(
            "project_root.is_git_repo",
            lambda: _run(["git", "rev-parse", "--is-inside-work-tree"], PROJECT_ROOT).stdout.strip() == "true",
            "git rev-parse --is-inside-work-tree",
        )
    else:
        c.record("project_root.is_git_repo", "git 미설치로 확인 불가", status="미측정")
    return {"path": str(PROJECT_ROOT), "name": PROJECT_ROOT.name, "is_git_repo": is_repo}


def collect() -> dict[str, Any]:
    start = time.perf_counter()
    c = Collector()
    data: dict[str, Any] = {
        "experiment_id": "E00",
        "experiment_name": "개발환경 및 재현성 확인",
        "schema_version": SCHEMA_VERSION,
        "run_timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    data["python"] = _python_info(c)
    data["os"] = _os_info(c)
    data["cpu"] = c.get("cpu", lambda: _cpu_info(c), "psutil import") or {
        "model": None, "physical_cores": None, "logical_cores": None
    }
    data["memory"] = _memory_info(c)
    data["venv"] = _venv_info(c)
    data["packages"] = _packages_info(c)
    data["git"] = _git_info(c)
    data["project_root"] = _project_info(c, data["git"]["installed"])
    data["elapsed_seconds"] = round(time.perf_counter() - start, 4)
    data["errors"] = c.errors
    return mask_sensitive(data)


def get_path(data: dict[str, Any], dotted: str) -> Any:
    """'a.b.c' 경로의 값을 반환한다. 없으면 KeyError."""
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted)
        node = node[part]
    return node


def compare_stable(run1: dict[str, Any], run2: dict[str, Any], fields: tuple[str, ...] = STABLE_FIELDS) -> list[dict[str, Any]]:
    """안정 필드 비교. 불일치·누락·미측정(null)을 모두 차이로 보고한다(빈 목록이어야 재현 성공)."""
    diffs = []
    for field in fields:
        values = []
        for run in (run1, run2):
            try:
                values.append(get_path(run, field))
            except KeyError:
                values.append(_MISSING)
        a, b = values
        if _MISSING in (a, b):
            diffs.append({"field": field, "run1": a, "run2": b, "reason": "필드 누락"})
        elif a is None or b is None:
            diffs.append({"field": field, "run1": a, "run2": b, "reason": "미측정 값은 일치로 인정하지 않음"})
        elif a != b:
            diffs.append({"field": field, "run1": a, "run2": b, "reason": "값 불일치"})
    return diffs


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E00 개발환경 점검")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="출력 JSON 경로 (UTF-8)")
    args = parser.parse_args(argv)
    data = collect()
    write_json(data, args.output)
    print(f"written: {mask_sensitive(str(args.output.resolve()))} (errors={len(data['errors'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
