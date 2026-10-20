# 새 클론 환경 검증 (2026-10-20)

> 임시 경로에서 수행하고 검증 후 삭제함. 사용자 이름·홈 경로는 기록하지 않음.

## 1. 기준 커밋 `1946c139a38819d88feef7b6f6d9230a12548d7a` 새 클론

| 단계 | 결과 |
|---|---|
| 가상환경 | 새 클론 안에 `py -3.11 -m venv .venv` (기존 프로젝트 `.venv` 재사용 안 함) — Python 3.11.9, pip 24.0 |
| `pip install -r requirements.lock` | **실패** — `UnicodeDecodeError: 'cp949' codec can't decode byte 0xec` (한국어 주석이 있는 UTF-8 파일을 pip이 시스템 코드 페이지로 읽음). 최초 커밋부터 있던 결함으로, CLAUDE.md의 설치 명령이 새 Windows 클론에서 동작하지 않았음 |
| 원인 확인·수정 | lock 첫 줄에 `# -*- coding: utf-8 -*-` 추가 (pip은 첫 두 줄의 coding 선언을 따름). 클론 사본에 같은 수정 후 재설치 |
| 재설치 | 성공, 설치 26개 = lock 26개 버전 완전 일치, `pip check` 이상 없음 |
| pytest | **70 passed, 13 skipped, 0 failed** — 이전에 다른 경로의 가상환경을 빌려 써서 생긴 환경 테스트 실패 3건 해소 |
| 스킵 13건 | UCI 원본 없음 8 (`data/raw/` Git 제외), PDF 없음 3 (P-01·P-02 공개 보류), `.env` 없음 2 |

## 2. 직접 파서 Baseline 작업 후 커밋 후보 사본 (2026-10-20)

`git ls-files -co --exclude-standard`(추적 + 제외되지 않은 미추적 파일)만 임시 경로에 복사 → 커밋 후 새 클론과 같은 파일 구성 (PDF·`.env`·`data/raw/` 없음).

| 환경 | 결과 |
|---|---|
| 새 가상환경 + 갱신한 lock(pypdf·pdfplumber 포함) 설치 | 성공, `pip check` 이상 없음 |
| 전체 pytest | **87 passed, 16 skipped, 0 failed** |
| 스킵 16건 | UCI 원본 없음 8, PDF 없음 6 (E03 샘플 3 + E03 파서 3), `.env` 없음 2 — 통과로 세지 않음 |
| `scripts/e03_run_parsers.py` (같은 구성의 별도 사본, 프로젝트 가상환경으로 실행) | DOCX·PPTX 4개 조합 측정, PDF 4개 조합은 `NOT_MEASURED`(입력 문서 없음, 재생성하지 않음), Upstage 비교는 `비교 불가` 기록 |
