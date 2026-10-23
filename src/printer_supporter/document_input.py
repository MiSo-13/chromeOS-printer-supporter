"""문서 드롭/클립보드 입력에서 안전하게 로컬 파일을 선택합니다."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit

from .backend import SUPPORTED_EXTENSIONS


def supported_document(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def local_document_from_text(text: str) -> Path | None:
    value = text.strip().strip('"').strip("'")
    if not value or "\\n" in value or "\\r" in value:
        return None
    if value.startswith("file://"):
        parsed = urlsplit(value)
        if parsed.netloc not in ("", "localhost"):
            return None
        value = unquote(parsed.path)
    elif "://" in value:
        return None
    path = Path(value).expanduser()
    return path if supported_document(path) else None


def local_document_from_mime(mime) -> Path | None:
    if mime.hasUrls():
        for url in mime.urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if supported_document(path):
                    return path
    if mime.hasText():
        return local_document_from_text(mime.text())
    return None
