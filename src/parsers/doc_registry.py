"""E03 직접 문서 파서 목록: 파서 이름 → (처리 형식, 함수). 형식 값은 E03 샘플 매니페스트의 format 열과 같다."""

from __future__ import annotations

from .doc_docx import parse_docx
from .doc_pdf import parse_pdf_pdfplumber, parse_pdf_pypdf
from .doc_pptx import parse_pptx

PARSERS = {
    "python-docx": ("docx", parse_docx),
    "python-pptx": ("pptx", parse_pptx),
    "pypdf": ("pdf_text", parse_pdf_pypdf),
    "pdfplumber": ("pdf_text", parse_pdf_pdfplumber),
}
