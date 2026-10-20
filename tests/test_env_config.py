"""로컬 비밀 설정(.env) 테스트 — 키 값은 출력·저장하지 않고, 실제 API 요청도 보내지 않는다.

실패 메시지에는 파일명·변수명만 나오게 한다 (키 값이 assert 출력에 섞이지 않도록 값 자체를 비교식에 넣지 않음).
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from config import settings

ROOT = Path(__file__).resolve().parents[1]
needs_env = pytest.mark.skipif(not (ROOT / ".env").exists(), reason=".env 없음 (로컬 전용 파일)")


def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def test_env_is_gitignored():
    assert git("check-ignore", "-q", ".env").returncode == 0


def test_env_not_tracked_or_staged_or_in_history():
    assert git("ls-files", "--error-unmatch", ".env").returncode != 0
    assert ".env" not in git("diff", "--cached", "--name-only").stdout.split()
    assert git("log", "--all", "--oneline", "--", ".env").stdout.strip() == ""


def test_env_example_has_names_only():
    entries = [l.split("=", 1) for l in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.lstrip().startswith("#")]
    assert entries and all(len(e) == 2 and e[1].strip() == "" for e in entries)
    assert "UPSTAGE_API_KEY" in [e[0].strip() for e in entries]


@needs_env
def test_upstage_key_is_configured():
    status = settings.upstage_key_status()
    assert status["configured"] is True and status["env_file_present"] is True
    assert set(status) == {"variable", "env_file_present", "configured"}   # 상태에 값이 섞이지 않음


@needs_env
def test_key_value_not_in_commit_candidates_or_results():
    secret = settings.get_upstage_api_key()
    assert secret is not None
    needle = secret.encode("utf-8")
    files = set(git("ls-files").stdout.splitlines()) | set(git("ls-files", "--others", "--exclude-standard").stdout.splitlines())
    files |= {str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "results").rglob("*") if p.is_file()}
    leaked = sorted(f for f in files if (ROOT / f).is_file() and needle in (ROOT / f).read_bytes())
    del secret, needle
    assert leaked == [], f"키 값이 들어 있는 파일: {leaked}"


def test_settings_module_has_no_print_or_network():
    tree = ast.parse((ROOT / "src" / "config" / "settings.py").read_text(encoding="utf-8"))
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "print" not in calls
    assert not any(m.split(".")[0] in ("requests", "urllib", "http", "httpx", "socket") for m in mods)
