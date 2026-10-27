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


def test_queue_queries_distinguish_pending_and_completed():
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return result(command, stdout="printer-11 jhheo 123 Fri Oct 23 09:20:00 2026\\n")

    service = CupsService(runner)
    assert service.jobs("printer")[0].job_id == "printer-11"
    assert service.completed_jobs("printer")[0].job_id == "printer-11"
    assert commands == [
        ["lpstat", "-W", "not-completed", "-o", "printer"],
        ["lpstat", "-W", "completed", "-o", "printer"],
    ]


@pytest.mark.parametrize("operation,expected", [
    ("hold", ["lp", "-i", "printer-10", "-H", "hold"]),
    ("resume", ["lp", "-i", "printer-10", "-H", "resume"]),
    ("cancel", ["cancel", "printer-10"]),
])
def test_only_owner_can_mutate_job(operation, expected):
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return result(command)

    service = CupsService(runner)
    job = PrintJob("printer-10", "jhheo", "20", "date", "printer")
    getattr(service, operation)(job, "jhheo")
    assert commands == [expected]

    with pytest.raises(PrintError, match="다른 사용자"):
        getattr(service, operation)(job, "someone_else")
    assert commands == [expected]


@pytest.mark.parametrize("bad_id", ["--help", "printer-abc", "other-10"])
def test_invalid_job_id_is_not_submitted(bad_id):
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return result(command)

    job = PrintJob(bad_id, "jhheo", "20", "date", "printer")
    with pytest.raises(PrintError, match="올바르지 않은"):
        CupsService(runner).hold(job, "jhheo")
    assert commands == []


def test_test_page_prints_once_and_cleans_up():
    commands = []
    page_contents = []

    def runner(command, **kwargs):
        commands.append(command)
        if command[0] == "lp":
            path = Path(command[-1])
            assert path.is_file()
            page_contents.append(path.read_text(encoding="ascii"))
        return result(command, stdout="request id is Samsung_SL_M2030W-21")

    response = CupsService(runner).print_test_page("Samsung_SL_M2030W", media="A4")
    assert "Samsung_SL_M2030W-21" in response
    assert len(commands) == 1
    assert commands[0][:7] == [
        "lp", "-d", "Samsung_SL_M2030W", "-n", "1", "-o", "media=A4",
    ]
    assert page_contents[0].startswith("PrintHub - Printer Test Page\n")
    assert "Printer : Samsung_SL_M2030W\n" in page_contents[0]
    assert not Path(commands[0][-1]).exists()


@pytest.mark.parametrize("printer,media", [
    ("", "A4"), ("--help", "A4"), ("Samsung_SL_M2030W", "invalid"),
])
def test_test_page_rejects_bad_destination_without_printing(printer, media):
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return result(command)

    with pytest.raises(PrintError):
        CupsService(runner).print_test_page(printer, media=media)
    assert commands == []


def test_test_page_propagates_cups_error():
    def runner(command, **kwargs):
        return result(command, stderr="printer offline", returncode=1)

    with pytest.raises(PrintError, match="offline"):
        CupsService(runner).print_test_page("Samsung_SL_M2030W")


def test_service_fetches_supported_printer_options():
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return result(command, stdout="ColorModel/Mode: *Gray RGB\n")

    options = CupsService(runner).printer_options("Samsung_SL_M2030W")
    assert commands == [["lpoptions", "-p", "Samsung_SL_M2030W", "-l"]]
    assert options["ColorModel"].choices[0].value == "Gray"


def test_print_options_reach_only_selected_job(tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return result(command)

    service = CupsService(runner)
    service.print_file(
        source, "printer", copies=2, media="A4",
        options={"PageSize": "A4", "ColorModel": "Gray", "Duplex": "None"},
    )
    assert calls == [[
        "lp", "-d", "printer", "-n", "2",
        "-o", "PageSize=A4", "-o", "ColorModel=Gray",
        "-o", "Duplex=None", "--", str(source),
    ]]


def test_unknown_paper_keeps_printer_default(tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return result(command)

    CupsService(runner).print_file(source, "printer", media=None)
    assert calls[0] == ["lp", "-d", "printer", "-n", "1", "--", str(source)]


def test_invalid_option_never_submits_job(tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return result(command)

    with pytest.raises(PrintError, match="CUPS 옵션"):
        CupsService(runner).print_file(source, "printer", options={"ColorModel": ";bad"})
    assert calls == []


@pytest.mark.parametrize("orientation", ["3", "4"])
def test_orientation_is_applied_to_one_document_job_only(tmp_path, orientation):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4")
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return result(command, stdout="request id is printer-1")

    service = CupsService(runner)
    service.print_file(
        source, "printer", media=None,
        options={"orientation-requested": orientation},
    )
    service.print_file(source, "printer", media=None)

    assert commands == [
        ["lp", "-d", "printer", "-n", "1",
         "-o", f"orientation-requested={orientation}", "--", str(source)],
        ["lp", "-d", "printer", "-n", "1", "--", str(source)],
    ]


def test_test_page_uses_same_orientation_option():
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return result(command, stdout="request id is printer-2")

    CupsService(runner).print_test_page(
        "printer", media="A4", options={"orientation-requested": "3"},
    )
    assert commands[0][:-1] == [
        "lp", "-d", "printer", "-n", "1",
        "-o", "media=A4", "-o", "orientation-requested=3", "--",
    ]
