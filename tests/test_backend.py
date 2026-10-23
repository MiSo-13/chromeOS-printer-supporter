from pathlib import Path
from subprocess import CompletedProcess

import pytest

from printer_supporter.backend import CupsService, PrintError, PrintJob, parse_jobs, parse_printers


def result(command, *, stdout="", stderr="", returncode=0):
    return CompletedProcess(command, returncode, stdout, stderr)


def test_printers_parse():
    output = "printer Samsung_SL_M2030W is idle. enabled since Friday\nprinter old is idle. disabled since Friday"
    printers = parse_printers(output)
    assert [p.name for p in printers] == ["Samsung_SL_M2030W", "old"]
    assert printers[0].enabled is True
    assert printers[1].enabled is False


def test_jobs_parse():
    jobs = parse_jobs("Samsung_SL_M2030W-12 jhheo 2048 Fri Oct 23 09:24:49 2026\n")
    assert jobs == [PrintJob("Samsung_SL_M2030W-12", "jhheo", "2048", "Fri Oct 23 09:24:49 2026", "Samsung_SL_M2030W")]


def test_print_pdf_uses_explicit_printer_and_options(tmp_path):
    source = tmp_path / "보고서.pdf"
    source.write_bytes(b"%PDF-1.4")
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return result(command, stdout="request id is Samsung_SL_M2030W-1")

    service = CupsService(runner)
    service.print_file(source, "Samsung_SL_M2030W", copies=2)
    assert commands == [["lp", "-d", "Samsung_SL_M2030W", "-n", "2", "-o", "media=A4", "--", str(source)]]


def test_invalid_extension_never_prints(tmp_path):
    source = tmp_path / "script.sh"
    source.write_text("echo test")
    with pytest.raises(PrintError, match="지원하지 않는"):
        CupsService().print_file(source, "Samsung_SL_M2030W")


def test_cancel_only_own_job():
    job = PrintJob("printer-10", "other", "20", "date", "printer")
    with pytest.raises(PrintError, match="다른 사용자"):
        CupsService().cancel(job, "jhheo")


def test_office_requires_converter(tmp_path, monkeypatch):
    source = tmp_path / "문서.docx"
    source.write_bytes(b"test")
    monkeypatch.setattr("printer_supporter.backend.shutil.which", lambda name: None)
    with pytest.raises(PrintError, match="LibreOffice"):
        CupsService().print_file(source, "Samsung_SL_M2030W")


def test_office_converts_in_temporary_directory(tmp_path, monkeypatch):
    source = tmp_path / "문서.docx"
    source.write_bytes(b"test")
    monkeypatch.setattr("printer_supporter.backend.shutil.which", lambda name: "/usr/bin/libreoffice")
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        if command[0] == "libreoffice":
            output_path = Path(command[command.index("--outdir") + 1]) / "문서.pdf"
            output_path.write_bytes(b"%PDF-1.4")
        return result(command, stdout="request id is printer-1")

    CupsService(runner).print_file(source, "printer")
    assert commands[0][0] == "libreoffice"
    assert commands[1][0] == "lp"
    assert commands[1][-1].endswith("문서.pdf")
    assert not Path(commands[1][-1]).exists()
