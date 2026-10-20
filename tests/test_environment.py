"""E00 개발환경·재현성 테스트.

기대값(Python 버전, 가상환경 경로, lock 파일)은 pyproject.toml [tool.chungpamo.environment]에서 읽는다.
"""

from __future__ import annotations

import copy
import importlib.metadata as md
import json
import platform
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import pytest

import check_environment as ce

ROOT = ce.PROJECT_ROOT
SCRIPT = ROOT / "scripts" / "check_environment.py"
RESULTS_DIR = ROOT / "results" / "E00_environment"


def _config() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["chungpamo"]["environment"]


def _venv_dir() -> Path:
    return (ROOT / _config()["venv_dir"]).resolve()


def _read_lock() -> dict[str, str]:
    pins = {}
    for line in (ROOT / _config()["lock_file"]).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, version = line.partition("==")
        assert sep, f"lock 파일에 버전이 고정되지 않은 줄: {line!r}"
        pins[ce._normalize_dist_name(name)] = version
    return pins


def _run_check(output: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    assert proc.returncode == 0, f"check_environment 실패\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


@pytest.fixture(scope="module")
def two_runs():
    """같은 가상환경에서 별도 프로세스로 2회 실행한 결과 (임시 디렉터리, 종료 시 삭제)."""
    with tempfile.TemporaryDirectory(prefix="e00_runs_") as d:
        paths = [Path(d) / "env_check_run1.json", Path(d) / "env_check_run2.json"]
        for p in paths:
            _run_check(p)
        raws = [p.read_bytes() for p in paths]
        yield {
            "paths": paths,
            "raw": raws,
            "data": [json.loads(r.decode("utf-8")) for r in raws],
            "exists": [p.is_file() and p.stat().st_size > 0 for p in paths],
        }


# ---- 실행 환경 ----

def test_python_version_matches_expected():
    assert platform.python_version() == _config()["expected_python"]


def test_running_in_project_venv():
    assert sys.prefix != sys.base_prefix, "가상환경이 아닌 Python으로 실행됨"
    assert Path(sys.prefix).resolve() == _venv_dir(), f"프로젝트 가상환경이 아님: {ce.mask_sensitive(sys.prefix)}"


def test_venv_excludes_global_site_packages(two_runs):
    assert two_runs["data"][0]["venv"]["include_system_site_packages"] is False


@pytest.mark.parametrize("name", ["pytest", "psutil"])
def test_package_installed_in_venv_with_locked_version(name):
    dist = md.distribution(name)
    location = Path(dist.locate_file("")).resolve()
    assert location.is_relative_to(_venv_dir()), f"{name}이 가상환경 밖에서 로드됨: {ce.mask_sensitive(str(location))}"
    assert dist.version == _read_lock()[ce._normalize_dist_name(name)]


def test_lock_file_matches_installed_packages():
    installed = {ce._normalize_dist_name(d.metadata["Name"]): d.version for d in md.distributions()}
    mismatches = {n: (v, installed.get(n)) for n, v in _read_lock().items() if installed.get(n) != v}
    assert mismatches == {}, f"lock(기대) vs 설치(실제): {mismatches}"


# ---- 환경 JSON ----

def test_env_json_has_required_fields(two_runs):
    data = two_runs["data"][0]
    for field in ce.REQUIRED_FIELDS:
        value = ce.get_path(data, field)  # 없으면 KeyError로 실패
        if value is None:
            assert any(e["field"] == field for e in data["errors"]), f"{field}가 null인데 errors에 사유가 없음"


def test_env_json_utf8_roundtrip(two_runs):
    raw = two_runs["raw"][0]
    assert not raw.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM이 포함됨"
    text = raw.decode("utf-8")  # strict
    data = json.loads(text)
    assert data == two_runs["data"][0]
    assert data["experiment_name"] == "개발환경 및 재현성 확인"
    assert "개발환경".encode("utf-8") in raw, "한글이 UTF-8 바이트로 저장되지 않음"


def test_output_files_created(two_runs):
    assert all(two_runs["exists"])


def test_saved_e00_result_files_exist():
    for name in ("env_check.json", "env_check_run1.json", "env_check_run2.json"):
        path = RESULTS_DIR / name
        assert path.is_file(), f"{name} 없음 — scripts/run_e00.py 실행 필요"
        json.loads(path.read_text(encoding="utf-8"))


# ---- 재현성 ----

def test_stable_fields_match_across_two_runs(two_runs):
    run1, run2 = two_runs["data"]
    diffs = ce.compare_stable(run1, run2)
    assert diffs == [], f"안정 필드 불일치: {diffs}"


def test_compare_stable_detects_differences(two_runs):
    """비교 함수가 항상 성공하지 않는지 확인하는 음성 대조."""
    base = two_runs["data"][0]
    changed = copy.deepcopy(base)
    changed["python"]["version"] = "0.0.0"
    assert [d["field"] for d in ce.compare_stable(base, changed)] == ["python.version"]

    unmeasured = copy.deepcopy(base)
    unmeasured["cpu"]["model"] = None
    assert [d["reason"] for d in ce.compare_stable(unmeasured, unmeasured) if d["field"] == "cpu.model"] == [
        "미측정 값은 일치로 인정하지 않음"
    ]

    missing = copy.deepcopy(base)
    del missing["git"]["version"]
    assert any(d["field"] == "git.version" for d in ce.compare_stable(base, missing))


def test_volatile_fields_not_compared():
    assert not set(ce.VOLATILE_FIELDS) & set(ce.STABLE_FIELDS)


# ---- 경로·민감정보 ----

def test_korean_path_handling():
    with tempfile.TemporaryDirectory(prefix="e00_한글_") as d:
        tmp = Path(d)
        output = tmp / "한글 폴더" / "환경점검 결과.json"
        _run_check(output)
        assert output.is_file()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["experiment_id"] == "E00"
    assert not tmp.exists(), "임시 디렉터리가 정리되지 않음"


def test_no_home_path_in_output(two_runs):
    home = str(Path.home())
    user = Path.home().name
    user_dir = re.compile(rf"(?i)users(\\\\|\\|/)+{re.escape(user)}(\\|/|\"|$)")
    for raw in two_runs["raw"]:
        text = raw.decode("utf-8")
        lowered = text.lower()
        assert home.lower() not in lowered
        assert home.replace("\\", "\\\\").lower() not in lowered  # JSON 이스케이프 형태
        assert home.replace("\\", "/").lower() not in lowered
        assert not user_dir.search(text), "사용자 폴더 경로가 출력에 남아 있음"


def test_mask_sensitive_replaces_home_and_user_dirs():
    home = str(Path.home())
    assert ce.mask_sensitive(home + r"\AppData\x.exe") == r"<HOME>\AppData\x.exe"
    assert ce.mask_sensitive(home.replace("\\", "/").upper() + "/a") == "<HOME>/a"
    assert ce.mask_sensitive(r"D:\Users\someone\file") == r"D:\Users\<USER>\file"
    assert ce.mask_sensitive({"a": [home]}) == {"a": ["<HOME>"]}
