"""로컬 비밀 설정 읽기 (.env).

- 프로젝트 루트의 `.env`를 `load_dotenv()`로 읽고 `os.getenv("UPSTAGE_API_KEY")`로 값을 얻는다.
- 키 값은 반환만 하고 출력·로그·결과 파일에 쓰지 않는다. 상태 확인에는 `upstage_key_status()`를 쓴다(값 미포함).
- `.env`는 .gitignore 대상이며 Git에 추적하지 않는다. 변수명 목록은 `.env.example` 참고.
- 이 모듈은 외부 API를 호출하지 않는다.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
UPSTAGE_KEY_NAME = "UPSTAGE_API_KEY"


def load_env(path: Path | None = None) -> bool:
    """`.env`를 읽어 환경변수로 등록한다. 이미 설정된 환경변수는 덮어쓰지 않는다. 파일이 있으면 True."""
    p = Path(path) if path else ENV_FILE
    return load_dotenv(p, override=False) if p.exists() else False


def get_upstage_api_key() -> str | None:
    """Upstage API 키. 없거나 비어 있으면 None. 반환값을 출력하거나 저장하지 말 것."""
    load_env()
    value = os.getenv(UPSTAGE_KEY_NAME)
    return value.strip() if value and value.strip() else None


def upstage_key_status() -> dict:
    """키 값 없이 설정 여부만 알려 준다 (로그·보고용)."""
    return {"variable": UPSTAGE_KEY_NAME, "env_file_present": ENV_FILE.exists(), "configured": get_upstage_api_key() is not None}
