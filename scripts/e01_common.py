"""E01 공통 입출력 도구 (계산 로직 없음).

정답 생성(e01_expected)과 검증(e01_verify)은 이 모듈의 입출력 함수만 공유하고,
업무 계산 함수는 공유하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_ID = "e01_manufacturing"
DATASET_VERSION = "v1"  # record_uid 네임스페이스 (엔터티 레코드 식별은 v1 그대로 유지)
GT_VERSION = "v2"       # 정답셋 버전: v2 = 계획안 비교 로직·UCI 날짜 표시 수정 (2026-10-20). v1은 보존 파일
SEED = 20261020
# xlsx 내부 zip 항목과 문서 속성에 넣는 고정 시각 (재현성)
FIXED_ZIP_TIME = (2026, 10, 20, 0, 0, 0)


class Paths:
    """출력 루트 기준 경로. 재현성 검사 시 임시 루트를 넘긴다."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else PROJECT_ROOT
        self.canonical = self.root / "data" / "canonical"
        self.vendor_a = self.root / "data" / "vendor_a"
        self.vendor_b = self.root / "data" / "vendor_b"
        self.invalid = self.root / "data" / "invalid"
        self.results = self.root / "results" / "E01_dataset"
        self.ground_truth = self.canonical / f"ground_truth_{GT_VERSION}.json"
        self.ground_truth_v1 = self.canonical / "ground_truth_v1.json"  # 이전 버전 (보존, 재생성하지 않음)
        self.injected = self.canonical / "injected_errors_v1.json"
        self.column_map = self.canonical / "vendor_column_map_v1.json"
        self.id_map = self.canonical / "vendor_id_map_v1.csv"
        self.row_map = self.canonical / "vendor_row_map_v1.csv"
        # 공개 원본은 항상 프로젝트 루트의 Git 미추적 경로에서 읽는다
        self.uci_dir = PROJECT_ROOT / "data" / "raw" / "public" / "uci_daily_demand"
        self.uci_csv = self.uci_dir / "extracted" / "Daily_Demand_Forecasting_Orders.csv"


def D(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError("float는 사용하지 않는다 (Decimal 문자열 사용)")
    return Decimal(str(value))


def fmt(value: Decimal | None) -> str | None:
    """Decimal → 지수 표기 없는 최소 문자열 ('1.20' → '1.2', '1E+3' → '1000')."""
    if value is None:
        return None
    s = format(D(value).normalize(), "f")
    return "0" if s in ("-0", "") else s


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record_uid(*parts: str) -> str:
    return "rec_" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_xlsx(path: Path) -> None:
    """openpyxl이 쓴 zip 항목 시각을 고정해 같은 내용이면 같은 바이트가 되게 한다."""
    path = Path(path)
    with zipfile.ZipFile(path) as zin:
        items = [(info, zin.read(info.filename)) for info in zin.infolist()]
    fixed = "%04d-%02d-%02dT%02d:%02d:%02dZ" % FIXED_ZIP_TIME
    for n, (info, data) in enumerate(items):
        if info.filename == "docProps/core.xml":
            text = data.decode("utf-8")
            for tag in ("dcterms:created", "dcterms:modified"):
                text = re.sub(rf"(<{tag}[^>]*>)[^<]*(</{tag}>)", rf"\g<1>{fixed}\g<2>", text)
            items[n] = (info, text.encode("utf-8"))
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for info, data in items:
            zi = zipfile.ZipInfo(info.filename, date_time=FIXED_ZIP_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            zout.writestr(zi, data)
    tmp.replace(path)
