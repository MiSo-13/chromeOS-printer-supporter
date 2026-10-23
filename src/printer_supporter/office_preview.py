"""Office 문서를 임시 PDF로 변환하는 미리보기 전용 서비스.

CUPS 명령이나 인쇄 기능은 호출하지 않습니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run
from tempfile import TemporaryDirectory
from typing import Callable
import shutil

from .backend import OFFICE_EXTENSIONS
from .preview import pdf_page_count


class OfficePreviewError(RuntimeError):
    """Office 미리보기를 생성하지 못했을 때 사용자에게 표시하는 오류."""


@dataclass
class ConvertedOfficePreview:
    pdf_path: Path
    page_count: int
    temporary: TemporaryDirectory

    def close(self) -> None:
        """변환된 PDF와 임시 LibreOffice 프로필을 삭제합니다."""
        self.temporary.cleanup()


def convert_office_preview(
    source: Path,
    *,
    runner: Callable[..., CompletedProcess[str]] = run,
    which: Callable[[str], str | None] = shutil.which,
    timeout: int = 90,
) -> ConvertedOfficePreview:
    """원본을 수정하지 않고 임시 디렉터리 안에 PDF를 생성합니다.

    개별 LibreOffice 프로필을 사용하여 이미 실행 중인 LibreOffice와
    프로필 충돌을 피하고 변환이 끝나도 결과물을 미리보기 기간 동안 유지합니다.
    """
    source = Path(source).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in OFFICE_EXTENSIONS:
        raise OfficePreviewError("미리보기가 지원되는 Office 문서를 선택해 주세요.")
    executable = which("libreoffice")
    if not executable:
        raise OfficePreviewError(
            "Office 미리보기에는 LibreOffice가 필요합니다. "
            "환경 점검에서 설치한 뒤 '미리보기 다시 시도'를 누르세요."
        )

    temporary = TemporaryDirectory(prefix="chromeos-printer-preview-")
    try:
        root = Path(temporary.name)
        output_dir = root / "pdf"
        output_dir.mkdir()
        profile_uri = (root / "libreoffice-profile").as_uri()
        command = [
            executable, f"-env:UserInstallation={profile_uri}",
            "--headless", "--convert-to", "pdf",
            "--outdir", str(output_dir), str(source),
        ]
        try:
            result = runner(
                command, capture_output=True, text=True, check=False, timeout=timeout,
            )
        except TimeoutExpired as exc:
            raise OfficePreviewError(
                "Office 문서 변환 시간이 초과되었습니다. 문서 크기나 LibreOffice 상태를 확인하세요."
            ) from exc
        except OSError as exc:
            raise OfficePreviewError(f"LibreOffice 실행에 실패했습니다: {exc}") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "알 수 없는 오류").strip()[-600:]
            raise OfficePreviewError(f"Office 문서 PDF 변환에 실패했습니다: {detail}")

        converted = output_dir / f"{source.stem}.pdf"
        if not converted.is_file() or converted.stat().st_size == 0:
            raise OfficePreviewError(
                "LibreOffice 변환 결과에서 PDF 파일을 찾지 못했습니다."
            )
        try:
            count = pdf_page_count(converted)
        except Exception as exc:
            raise OfficePreviewError(f"변환된 PDF를 열 수 없습니다: {exc}") from exc
        if count < 1:
            raise OfficePreviewError("변환된 PDF에 페이지가 없습니다.")
        return ConvertedOfficePreview(converted, count, temporary)
    except BaseException:
        temporary.cleanup()
        raise
