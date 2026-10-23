"""문서 페이지 범위 검증과 PDF 미리보기 유틸리티."""
from __future__ import annotations
import re
from pathlib import Path


def normalize_page_ranges(value: str, page_count: int | None = None) -> str:
    """CUPS page-ranges 형식(1-3,5)을 검증하고 정규화합니다."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("인쇄할 페이지를 입력해 주세요.")
    segments = []
    for part in value.split(","):
        match = re.fullmatch(r"\s*([1-9]\d*)(?:\s*-\s*([1-9]\d*))?\s*", part)
        if not match:
            raise ValueError("페이지 범위는 1-3, 5 형식으로 입력해 주세요.")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if end < start or (page_count is not None and end > page_count):
            raise ValueError("페이지 범위가 문서 페이지 수를 벗어났습니다.")
        segments.append(f"{start}-{end}" if match.group(2) else str(start))
    return ",".join(segments)


def pdf_page_count(path: Path) -> int:
    import fitz
    with fitz.open(str(path)) as document:
        return len(document)


def render_pdf_page(path: Path, index: int, *, scale: float = 1.15) -> bytes:
    import fitz
    with fitz.open(str(path)) as document:
        if not 0 <= index < len(document):
            raise ValueError("페이지 번호가 올바르지 않습니다.")
        pixmap = document[index].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png")
