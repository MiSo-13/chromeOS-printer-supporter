"""LibreOffice 명령은 모의 실행하며 원본·임시 파일·오류 처리를 검사합니다."""
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

import fitz
import pytest

from printer_supporter.backend import OFFICE_EXTENSIONS
from printer_supporter.office_preview import OfficePreviewError, convert_office_preview


@pytest.mark.parametrize("suffix", sorted(OFFICE_EXTENSIONS))
def test_office_to_temporary_pdf_without_printing(tmp_path, suffix):
    source = tmp_path / f"한글 이름 파일{suffix}"
    source.write_bytes(b"keep original")
    commands = []

    def fake_runner(command, **kwargs):
        commands.append((command, kwargs))
        assert command[0] == "/usr/bin/libreoffice"
        assert command[1].startswith("-env:UserInstallation=file://")
        assert command[2:5] == ["--headless", "--convert-to", "pdf"]
        outdir = Path(command[command.index("--outdir") + 1])
        with fitz.open() as doc:
            doc.new_page()
            doc.new_page()
            doc.save(outdir / (source.stem + ".pdf"))
        return CompletedProcess(command, 0, "converted", "")

    converted = convert_office_preview(
        source, runner=fake_runner, which=lambda _: "/usr/bin/libreoffice"
    )
    path = converted.pdf_path
    directory = path.parent.parent
    assert converted.page_count == 2
    assert path.is_file()
    assert path.parent == directory / "pdf"
    assert source.read_bytes() == b"keep original"
    assert len(commands) == 1
    assert "lp" not in commands[0][0] and "lpadmin" not in commands[0][0]
    assert commands[0][1]["timeout"] == 90
    assert commands[0][1]["check"] is False
    converted.close()
    assert not directory.exists()
    assert source.read_bytes() == b"keep original"


def test_missing_libreoffice_does_not_launch_or_install(tmp_path):
    source = tmp_path / "document.docx"
    source.write_bytes(b"original")
    def forbidden(*args, **kwargs):
        raise AssertionError("subprocess should not run")
    with pytest.raises(OfficePreviewError, match="LibreOffice"):
        convert_office_preview(source, which=lambda _: None, runner=forbidden)
    assert source.read_bytes() == b"original"


@pytest.mark.parametrize("suffix", [".pdf", ".sh", ".exe"])
def test_unsupported_extension_is_rejected(tmp_path, suffix):
    source = tmp_path / ("document" + suffix)
    source.write_bytes(b"original")
    with pytest.raises(OfficePreviewError, match="Office"):
        convert_office_preview(source, runner=lambda *_a, **_kw: None)


@pytest.mark.parametrize("kind", ["nonzero", "timeout", "no_output", "corrupt_pdf"])
def test_conversion_error_cleans_up_temporary_directory(tmp_path, kind):
    source = tmp_path / "document.xlsx"
    source.write_bytes(b"original")
    temp_dirs = []

    def fake_runner(command, **kwargs):
        outdir = Path(command[command.index("--outdir") + 1])
        temp_dirs.append(outdir.parent)
        if kind == "timeout":
            raise TimeoutExpired(command, 90)
        if kind == "nonzero":
            return CompletedProcess(command, 1, "", "filter error")
        if kind == "corrupt_pdf":
            (outdir / "document.pdf").write_bytes(b"invalid pdf")
        return CompletedProcess(command, 0, "ok", "")

    with pytest.raises(OfficePreviewError):
        convert_office_preview(
            source, runner=fake_runner, which=lambda _: "/usr/bin/libreoffice",
        )
    assert len(temp_dirs) == 1
    assert not temp_dirs[0].exists()
    assert source.read_bytes() == b"original"
