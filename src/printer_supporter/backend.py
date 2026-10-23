"""CUPS 명령 실행과 문서 변환을 분리한 인쇄 서비스."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, run
from tempfile import TemporaryDirectory
from typing import Callable, Sequence
import re
import shutil

from .capabilities import PrinterOption, parse_printer_options, validate_job_options


PDF_EXTENSIONS = {".pdf"}
OFFICE_EXTENSIONS = {
    ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods",
    ".ppt", ".pptx", ".odp",
}
DIRECT_EXTENSIONS = {".txt", ".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | OFFICE_EXTENSIONS | DIRECT_EXTENSIONS


class PrintError(RuntimeError):
    """인쇄 요청 또는 환경 설정 오류."""


@dataclass(frozen=True)
class Printer:
    name: str
    state: str
    enabled: bool
    reason: str = ""


@dataclass(frozen=True)
class PrintJob:
    job_id: str
    owner: str
    size: str
    submitted: str
    printer: str


Runner = Callable[..., CompletedProcess[str]]


def _execute(command: Sequence[str], runner: Runner = run, *, timeout: int = 15) -> str:
    try:
        result = runner(list(command), capture_output=True, text=True, check=False, timeout=timeout)
    except FileNotFoundError as exc:
        raise PrintError(f"명령어를 찾지 못했습니다: {command[0]}") from exc
    except TimeoutError as exc:
        raise PrintError("명령 실행 시간이 초과되었습니다.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "알 수 없는 오류").strip()
        raise PrintError(detail)
    return result.stdout


def parse_printers(output: str) -> list[Printer]:
    printers = []
    for line in output.splitlines():
        match = re.match(r"^printer\s+(\S+)\s+(.*)$", line)
        if not match:
            continue
        name, detail = match.groups()
        enabled = "disabled" not in detail.lower()
        state = "중지됨" if not enabled else ("인쇄 중" if "printing" in detail.lower() else "대기")
        printers.append(Printer(name, state, enabled, detail))
    return printers


def parse_jobs(output: str) -> list[PrintJob]:
    jobs = []
    for line in output.splitlines():
        # lpstat -o: 요청 ID, 소유자, 바이트 수, 제출 시각
        parts = line.split(maxsplit=3)
        if len(parts) != 4 or not re.search(r"-\d+$", parts[0]):
            continue
        job_id, owner, size, submitted = parts
        printer = job_id.rsplit("-", 1)[0]
        jobs.append(PrintJob(job_id, owner, size, submitted, printer))
    return jobs


class CupsService:
    def __init__(self, runner: Runner = run):
        self.runner = runner

    def printers(self) -> list[Printer]:
        return parse_printers(_execute(["lpstat", "-p"], self.runner))

    def jobs(self, printer: str) -> list[PrintJob]:
        return parse_jobs(_execute(["lpstat", "-W", "not-completed", "-o", printer], self.runner))

    def completed_jobs(self, printer: str) -> list[PrintJob]:
        """CUPS 스케줄러가 종료 처리한 이력(실제 출력 성공 여부와 무관)."""
        return parse_jobs(_execute(["lpstat", "-W", "completed", "-o", printer], self.runner))

    def printer_options(self, printer: str) -> dict[str, PrinterOption]:
        if not printer or printer.startswith("-"):
            raise PrintError("올바른 프린터를 선택해 주세요.")
        return parse_printer_options(_execute(["lpoptions", "-p", printer, "-l"], self.runner))

    def printer_reasons(self, printer: str) -> str:
        # 장치 상태는 백엔드 프로토콜에 따라 노출 수준이 다릅니다.
        return _execute(["lpstat", "-p", printer, "-l"], self.runner).strip()

    def cancel(self, job: PrintJob, current_user: str) -> None:
        self._check_owner(job, current_user)
        _execute(["cancel", job.job_id], self.runner)

    def hold(self, job: PrintJob, current_user: str) -> None:
        self._check_owner(job, current_user)
        _execute(["lp", "-i", job.job_id, "-H", "hold"], self.runner)

    def resume(self, job: PrintJob, current_user: str) -> None:
        self._check_owner(job, current_user)
        _execute(["lp", "-i", job.job_id, "-H", "resume"], self.runner)

    @staticmethod
    def _check_owner(job: PrintJob, current_user: str) -> None:
        if job.owner != current_user:
            raise PrintError("다른 사용자의 인쇄 작업은 변경할 수 없습니다.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+-[0-9]+", job.job_id) or job.printer != job.job_id.rsplit("-", 1)[0]:
            raise PrintError("올바르지 않은 인쇄 작업 ID입니다.")

    def print_test_page(self, printer: str, *, media: str | None = "A4",
                        options: dict[str, str] | None = None) -> str:
        """선택한 CUPS 큐에 ASCII 텍스트 테스트 페이지를 한 장 전송합니다."""
        if not printer or printer.startswith("-"):
            raise PrintError("올바른 프린터를 선택해 주세요.")
        if media is not None and (not isinstance(media, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]+", media)):
            raise PrintError("지원하지 않는 테스트 용지 크기입니다.")

        with TemporaryDirectory(prefix="printhub-test-") as temp:
            page = Path(temp) / "PrintHub-test-page.txt"
            page.write_text(
                "PrintHub - Printer Test Page\n"
                "========================================\n"
                f"Printer : {printer}\n"
                f"Date    : {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
                f"Paper   : {media or 'printer default'}\n"
                "----------------------------------------\n"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ\n"
                "abcdefghijklmnopqrstuvwxyz\n"
                "0123456789 !@#$%^&*()\n"
                "----------------------------------------\n"
                "If you can read this page, the CUPS print path is working.\n",
                encoding="ascii",
            )
            return self._submit(page, printer, 1, media, options=options)

    def print_file(self, source: Path, printer: str, *, copies: int = 1,
                   media: str | None = "A4", options: dict[str, str] | None = None) -> str:
        source = Path(source).expanduser()
        if not source.is_file():
            raise PrintError("선택한 파일이 존재하지 않습니다.")
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise PrintError(f"지원하지 않는 파일 형식입니다: {source.suffix}")
        if not 1 <= copies <= 99:
            raise PrintError("인쇄 매수는 1~99 사이여야 합니다.")
        if not printer or printer.startswith("-"):
            raise PrintError("올바른 프린터를 선택해 주세요.")

        if source.suffix.lower() in OFFICE_EXTENSIONS:
            if not shutil.which("libreoffice"):
                raise PrintError("Office 문서 인쇄에는 LibreOffice가 필요합니다. sudo apt install libreoffice")
            with TemporaryDirectory(prefix="printhub-") as temp:
                output_dir = Path(temp)
                profile_uri = (output_dir / "profile").as_uri()
                _execute(
                    ["libreoffice", f"-env:UserInstallation={profile_uri}",
                     "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(source)],
                    self.runner,
                    timeout=90,
                )
                converted = output_dir / f"{source.stem}.pdf"
                if not converted.is_file():
                    raise PrintError("Office 문서를 PDF로 변환하지 못했습니다.")
                return self._submit(converted, printer, copies, media, options=options)
        return self._submit(source, printer, copies, media, options=options)

    def _submit(self, path: Path, printer: str, copies: int, media: str | None,
                *, options: dict[str, str] | None = None) -> str:
        selection = dict(options or {})
        try:
            validate_job_options(selection)
        except ValueError as exc:
            raise PrintError(str(exc)) from exc
        if media is not None and not re.fullmatch(r"[A-Za-z0-9_.+-]+", media):
            raise PrintError("올바르지 않은 용지 크기입니다.")

        command = ["lp", "-d", printer, "-n", str(copies)]
        # PageSize와 media를 동시에 지정하면 충돌할 수 있으므로 실제 지원 키를 우선합니다.
        has_paper = any(key.lower() in {"pagesize", "media", "media-size"} for key in selection)
        if media is not None and not has_paper:
            command.extend(["-o", f"media={media}"])
        for key, value in selection.items():
            command.extend(["-o", f"{key}={value}"])
        command.extend(["--", str(path)])
        return _execute(command, self.runner).strip()
