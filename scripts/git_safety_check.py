"""GitHub 업로드 전 추적·제외 상태와 커밋 후보 내용 점검 → results/E01_dataset/git_safety_report.md

    .\\.venv\\Scripts\\python.exe scripts\\git_safety_check.py

- git status --ignored / check-ignore -v / ls-files / diff --cached 결과로 실제 상태를 확인한다.
- 커밋 후보(추적 중 + 미추적이지만 제외되지 않은 파일)의 내용을 검사한다. XLSX는 내부 XML까지 연다.
- 보고서에는 사용자 이름·PC 이름·홈 경로·로컬 검사어·비공개 원본 파일명을 쓰지 않는다 (건수·분류만).
- 커밋·스테이징은 하지 않는다.
"""

from __future__ import annotations

import csv
import io
import re
import socket
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "E01_dataset" / "git_safety_report.md"
UCI_CSV = ROOT / "data" / "raw" / "public" / "uci_daily_demand" / "extracted" / "Daily_Demand_Forecasting_Orders.csv"
SCANNER_FILES = {"scripts/run_e01.py", "scripts/git_safety_check.py"}  # 검사 규칙(정규식)을 정의하는 파일


def git(*args: str) -> list[str]:
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return [l for l in r.stdout.splitlines() if l.strip()]


def is_ignored(rel: str) -> str | None:
    r = subprocess.run(["git", "-c", "core.quotepath=false", "check-ignore", "-v", "--no-index", rel], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        return None
    rule = r.stdout.strip().split("\t")[0]          # "<소스>:<줄>:<패턴>"
    pattern = rule.split(":", 2)[2] if rule.count(":") >= 2 else rule
    return None if pattern.startswith("!") else rule  # `!` 예외 규칙에 걸린 것은 추적 허용


def texts_of(path: Path) -> list[str]:
    data = path.read_bytes()
    if path.suffix.lower() == ".xlsx":
        with zipfile.ZipFile(path) as z:
            return [z.read(n).decode("utf-8", "replace") for n in z.namelist()]
    for enc in ("utf-8", "cp949"):
        try:
            return [data.decode(enc)]
        except UnicodeDecodeError:
            continue
    return [data.decode("utf-8", "replace")]


def main() -> int:
    home = str(Path.home())
    user = Path.home().name
    host = socket.gethostname()
    patterns = {
        "사용자 홈 경로": re.compile("|".join(map(re.escape, {home, home.replace("\\", "\\\\"), home.replace("\\", "/")})), re.I),
        "사용자 폴더 경로": re.compile(rf"(?i)users[\\/]+{re.escape(user)}\b"),
        "PC 이름": re.compile(rf"(?i)\b{re.escape(host)}\b"),
        "개인 이메일": re.compile(r"[A-Za-z0-9._%+-]+@(gmail|naver|daum|hanmail|kakao)\.(com|net)"),
        "API 키·토큰 형태": re.compile(r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|"
                                    r"(?i:(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}))"),
        "개인키 블록": re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
        "비공개 자료 용어": re.compile("위원회 평가|평가결과|참가신청서|업무분장\\.docx"),
    }
    local = ROOT / "configs" / "sensitive_terms.local.txt"
    terms = [t.strip() for t in local.read_text(encoding="utf-8").splitlines() if t.strip()] if local.exists() else []
    if terms:
        patterns["로컬 검사어(팀원 실명 등)"] = re.compile("|".join(map(re.escape, terms)))

    tracked = git("ls-files")
    untracked = git("ls-files", "--others", "--exclude-standard")
    staged = git("diff", "--cached", "--name-only")
    tracked_but_ignored = git("ls-files", "-ci", "--exclude-standard")
    ignored_status = [l[3:] for l in git("status", "--ignored", "--short") if l.startswith("!! ")]
    deleted = [l[3:] for l in git("status", "--short") if l[:2].strip() == "D"]
    candidates = sorted({p for p in tracked + untracked if (ROOT / p).is_file()})

    must_ignore = {
        "data/raw/ (UCI 원본 zip)": "data/raw/public/uci_daily_demand/daily+demand+forecasting+orders.zip",
        "data/raw/ (UCI 원본 CSV)": "data/raw/public/uci_daily_demand/extracted/Daily_Demand_Forecasting_Orders.csv",
        "data/raw/ (UCI 스테이징)": "data/raw/public/uci_daily_demand/staging_uci_daily_orders_v1.json",
        "data/raw/ (다운로드 기록)": "data/raw/public/uci_daily_demand/download_record.json",
        "data/raw/ (실제 기업 데이터 예시 경로)": "data/raw/company/sample.xlsx",
        "로컬 검사어 파일": "configs/sensitive_terms.local.txt",
        ".env": ".env",
        ".venv/": ".venv/pyvenv.cfg",
        "__pycache__/": "scripts/__pycache__/x.cpython-311.pyc",
        ".pytest_cache/": ".pytest_cache/README.md",
        "로그": "results/run.log",
        "임시파일": "data/tmp.tmp",
        "Kaggle 인증": "kaggle.json",
        "인증서·키": "secrets/id.pem",
    }
    ignore_rows = [(label, rel, is_ignored(rel)) for label, rel in must_ignore.items()]
    # -z 출력은 공백·괄호가 있는 파일명도 따옴표 없이 준다
    zr = subprocess.run(["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "docs/"], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8")
    private_docs = [p for p in zr.stdout.split("\0") if p.lower().endswith((".pdf", ".docx"))]
    priv_ok = all(is_ignored(p) for p in private_docs)

    groups = {
        "정답셋·대응표 (data/canonical)": [p for p in candidates if p.startswith("data/canonical/")],
        "합성 업체 파일 (data/vendor_a, vendor_b)": [p for p in candidates if p.startswith(("data/vendor_a/", "data/vendor_b/"))],
        "오류 주입본 (data/invalid)": [p for p in candidates if p.startswith("data/invalid/")],
        "실험 코드 (scripts)": [p for p in candidates if p.startswith("scripts/")],
        "테스트 (tests)": [p for p in candidates if p.startswith("tests/")],
        "비식별 결과 (results)": [p for p in candidates if p.startswith("results/")],
        "문서 (docs, CLAUDE.md 등)": [p for p in candidates if p.startswith("docs/") or "/" not in p],
        "빈 폴더 유지 (.gitkeep)": [p for p in candidates if p.endswith(".gitkeep")],
    }
    candidate_ignored = [p for p in candidates if is_ignored(p)]

    hits = []
    for rel in candidates:
        for t in texts_of(ROOT / rel):
            for name, rx in patterns.items():
                if rx.search(t):
                    allowed = rel in SCANNER_FILES and name == "비공개 자료 용어"
                    hits.append((rel, name, allowed))
    hits = sorted(set(hits))
    blocking = [h for h in hits if not h[2]]

    # 공개 데이터 원본 복제 여부
    raw_lines, header = [], None
    if UCI_CSV.exists():
        lines = UCI_CSV.read_text(encoding="ascii").splitlines()
        header, raw_lines = lines[0], lines[1:]
    copies = []
    for rel in candidates:
        blob = "\n".join(texts_of(ROOT / rel))
        n = sum(1 for l in raw_lines if l in blob)
        if n:
            copies.append((rel, n))
    header_files = [rel for rel in candidates if header and any(header.split(";")[0] in t for t in texts_of(ROOT / rel))]

    sizes = sorted(((rel, (ROOT / rel).stat().st_size) for rel in candidates), key=lambda x: -x[1])
    total_bytes = sum(s for _, s in sizes)
    large = [(r, s) for r, s in sizes if s >= 1024 * 1024]
    too_large = [(r, s) for r, s in sizes if s >= 10 * 1024 * 1024]
    ok = (not staged and not tracked_but_ignored and all(r[2] for r in ignore_rows) and priv_ok and not candidate_ignored
          and not blocking and not copies and not too_large)
    L = ["# Git 업로드 전 안전 점검 — E01", "",
         "> scripts/git_safety_check.py 실행 결과. 사용자 이름·PC 이름·홈 경로·로컬 검사어·비공개 원본 파일명은 기록하지 않는다.", "",
         f"- 종합: **{'통과' if ok else '문제 있음'}**",
         f"- 커밋 후보 {len(candidates)}개 (추적 중 {len(tracked)} + 미추적·비제외 {len(untracked)}), 스테이징 {len(staged)}개, 작업트리 삭제 {len(deleted)}개", "",
         "## 1. 제외되어야 하는 항목 (`git check-ignore -v`)", "", "| 항목 | 검사 경로 | 적용 규칙 |", "|---|---|---|"]
    L += [f"| {label} | `{rel}` | {('`' + rule + '`') if rule else '**제외 안 됨**'} |"
          for label, rel, rule in ignore_rows]
    L += [f"| 비공개 원본 문서 (docs/ PDF·DOCX) | {len(private_docs)}개 (파일명 미기재) | {'모두 제외' if priv_ok else '**일부 제외 안 됨**'} |", "",
          f"- `git status --ignored`의 제외 항목 {len(ignored_status)}건 (최상위 단위)", "",
          "## 2. 이미 추적 중인데 제외 규칙에 걸리는 파일 (`git ls-files -ci --exclude-standard`)", "",
          f"- {len(tracked_but_ignored)}건" + ("" if not tracked_but_ignored else ": " + ", ".join(tracked_but_ignored)), "",
          "## 3. 스테이징 상태 (`git diff --cached --name-only`)", "", f"- {len(staged)}건 (커밋 승인 전이므로 스테이징하지 않음)", "",
          "## 4. 추적되어야 하는 공개 가능 항목", "", "| 분류 | 파일 수 |", "|---|---|"]
    L += [f"| {g} | {len(v)} |" for g, v in groups.items()]
    L += ["", f"- 커밋 후보 중 제외 규칙에 걸린 파일: {len(candidate_ignored)}건", "",
          "## 5. 내용 검사 (텍스트·JSON·CSV는 UTF-8/CP949 해독, XLSX는 내부 XML 전체)", "",
          f"- 검사 패턴: {', '.join(patterns)}", f"- 차단 대상 검출: **{len(blocking)}건**"]
    L += [f"  - `{rel}`: {name}" for rel, name, _ in blocking]
    allowed = [h for h in hits if h[2]]
    if allowed:
        L.append(f"- 허용 검출 {len(allowed)}건: 검사 규칙을 정의하는 스크립트의 정규식 문자열 (실제 비공개 내용 아님)")
        L += [f"  - `{rel}`: {name}" for rel, name, _ in allowed]
    L += ["", "## 6. 공개 데이터 원본 복제 여부·라이선스", "",
          f"- UCI 원본 데이터 행({len(raw_lines)}행)이 그대로 들어 있는 커밋 후보: {len(copies)}건" + ("" if not copies else " — " + ", ".join(f"{r}({n}행)" for r, n in copies)),
          f"- 원본 헤더 문자열을 포함한 커밋 후보: {len(header_files)}건 ({', '.join(header_files) or '없음'}) — 구조 검증 기록용 헤더·요약 통계",
          "- 원본 zip·CSV·스테이징(원본 값 전체)은 `data/raw/`에만 있고 Git 제외",
          "- SalesHistory는 원본 총주문을 가상 제품에 나눈 합성값(SYNTHETIC/ALLOCATED)이며 원본 행이 아니다",
          "- 라이선스: UCI Daily Demand Forecasting Orders = CC BY 4.0 (재배포·가공 허용, 출처 표기 필요). 정답셋 `dataset.public_sources`와 "
          "`uci_source_verification.json`에 출처·인용·DOI 기재",
          "- Kaggle M5: 다운로드하지 않음 (라이선스 미확인)", "",
          "## 6-1. 파일 크기", "",
          f"- 커밋 후보 전체 {total_bytes:,} bytes, 최대 파일 `{sizes[0][0]}` {sizes[0][1]:,} bytes",
          f"- 1 MB 이상: {len(large)}건 / 10 MB 이상(차단): {len(too_large)}건", "",
          "## 7. 커밋 대상과 제외 대상", "",
          "- 커밋 대상(승인 시): 위 4절의 공개 가능 파일 전부 (정답셋 v1·v2, 합성 업체 파일, 오류 주입본, 코드, 테스트, 비식별 결과, 문서)",
          "- 제외 대상: data/raw/ 전체(UCI 원본·스테이징), 로컬 검사어 파일, 비공개 원본 문서, .env, .venv/, 캐시, 로그·임시파일",
          "- 커밋·푸시: 하지 않음 (사용자 승인 대기)", ""]
    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print({"ok": ok, "candidates": len(candidates), "blocking": len(blocking), "allowed": len(allowed),
           "tracked_but_ignored": len(tracked_but_ignored), "staged": len(staged), "raw_copies": len(copies),
           "not_ignored": [l for l, _, r in ignore_rows if not r], "candidate_ignored": candidate_ignored})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
