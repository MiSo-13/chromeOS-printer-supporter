"""CUPS 명령 실행과 문서 변환을 분리한 인쇄 서비스."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, run
from tempfile import TemporaryDirectory
from typing import Callable, Sequence
import re
import shutil


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
        return parse_jobs(_execute(["lpstat", "-o", printer], self.runner))

    def printer_reasons(self, printer: str) -> str:
        # 장치 상태는 백엔드 프로토콜에 따라 노출 수준이 다릅니다.
        return _execute(["lpstat", "-p", printer, "-l"], self.runner).strip()

    def cancel(self, job: PrintJob, current_user: str) -> None:
        if job.owner != current_user:
            raise PrintError("다른 사용자의 인쇄 작업은 취소할 수 없습니다.")
        _execute(["cancel", job.job_id], self.runner)

    def print_file(self, source: Path, printer: str, *, copies: int = 1, media: str = "A4") -> str:
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
                return self._submit(converted, printer, copies, media)
        return self._submit(source, printer, copies, media)

    def _submit(self, path: Path, printer: str, copies: int, media: str) -> str:
        return _execute(
            ["lp", "-d", printer, "-n", str(copies), "-o", f"media={media}", "--", str(path)],
            self.runner,
        ).strip()
