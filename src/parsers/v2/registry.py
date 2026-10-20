"""E03 직접 파서 v2 목록. pypdf는 표·좌표 기능이 없어 v1 구현을 그대로 쓴다 (비교 기준 유지)."""

from __future__ import annotations

from ..doc_pdf import parse_pdf_pypdf
from .docx_v2 import parse_docx_v2
from .pdf_v2 import parse_pdf_pdfplumber_v2
from .pptx_v2 import parse_pptx_v2

PARSERS = {
    "python-docx": ("docx", parse_docx_v2),
    "python-pptx": ("pptx", parse_pptx_v2),
    "pypdf": ("pdf_text", parse_pdf_pypdf),
    "pdfplumber": ("pdf_text", parse_pdf_pdfplumber_v2),
}
