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
    if mime is None:
        return None
    if mime.hasUrls():
        for url in mime.urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if supported_document(path):
                    return path
    # ChromeOS 파일 앱은 Qt hasUrls() 대신 원본 text/uri-list를
    # 제공하는 경우가 있으므로 MIME payload를 직접 확인합니다.
    for fmt in ("text/uri-list", "x-special/gnome-copied-files",
                "application/x-kde4-urilist"):
        if not mime.hasFormat(fmt):
            continue
        payload = bytes(mime.data(fmt)).decode("utf-8", errors="replace")
        for line in payload.splitlines():
            value = line.strip()
            if not value or value.startswith("#") or value in ("copy", "cut"):
                continue
            path = local_document_from_text(value)
            if path is not None:
                return path
    if mime.hasText():
        return local_document_from_text(mime.text())
    return None
