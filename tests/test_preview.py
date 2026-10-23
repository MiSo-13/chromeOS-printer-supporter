from pathlib import Path
from subprocess import CompletedProcess
import pytest
from printer_supporter.preview import (normalize_page_ranges, pdf_page_count, render_pdf_page, read_text_preview, MAX_TEXT_PREVIEW_BYTES)
from printer_supporter.backend import CupsService, PrintError

@pytest.mark.parametrize("value,expected", [("1", "1"), ("1-3, 5,8-10", "1-3,5,8-10")])
def test_page_ranges(value, expected):
    assert normalize_page_ranges(value) == expected

@pytest.mark.parametrize("value", ["", "0", "3-1", "1,,2", "1;rm", "-1", "1-", "2-4"])
def test_invalid_page_ranges(value):
    with pytest.raises(ValueError):
        normalize_page_ranges(value, page_count=3)

def test_pdf_preview(tmp_path):
    import fitz
    path = tmp_path / "sample.pdf"
    with fitz.open() as document:
        document.new_page()
        document.new_page()
        document.save(path)
    assert pdf_page_count(path) == 2
    assert render_pdf_page(path, 0).startswith(b"\\x89PNG".decode("unicode_escape").encode("latin1"))

def test_print_range_only_applies_to_job(tmp_path):
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4")
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, "request id is printer-1", "")
    CupsService(runner).print_file(path, "printer", page_ranges="1-3,5")
    assert ["-o", "page-ranges=1-3,5"] == calls[0][calls[0].index("page-ranges=1-3,5") - 1:calls[0].index("page-ranges=1-3,5") + 1]
    with pytest.raises(PrintError):
        CupsService(runner).print_file(path, "printer", page_ranges="0-2")
    assert len(calls) == 1


def test_text_preview_and_size_limit(tmp_path):
    small = tmp_path / "small.txt"
    small.write_text("안녕하세요\\n인쇄 테스트", encoding="utf-8")
    assert read_text_preview(small) == "안녕하세요\\n인쇄 테스트"

    large = tmp_path / "large.txt"
    large.write_bytes(b"a" * (MAX_TEXT_PREVIEW_BYTES + 200))
    preview = read_text_preview(large)
    assert preview.startswith("a" * 100)
    assert "128KB" in preview
    assert len(preview) < MAX_TEXT_PREVIEW_BYTES + 100


def test_text_preview_rejects_binary(tmp_path):
    binary = tmp_path / "bad.txt"
    binary.write_bytes(bytes([0, 1, 2]))
    with pytest.raises(ValueError, match="텍스트"):
        read_text_preview(binary)
