"""검증된 Samsung ULD 인쇄 필터·PPD만 승인 후 설치합니다.

제조사 설치 스크립트는 실행하지 않습니다. 공식 ZIP의 SHA-256을 검증하고
x86_64 CUPS filter / 해당 모델용 PPD 두 파일만 꺼냅니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from subprocess import CompletedProcess, run
from tempfile import TemporaryDirectory
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import os
import platform
import zipfile
import tarfile

from .identification import PrinterIdentity

SAMSUNG_ULD_URL = (
    "https://downloadcenter.samsung.com/content/DR/201911/"
    "20191101152153376/ULDLINUX_V1.00.39.07_01.24.zip"
)
SAMSUNG_ULD_SHA256 = "cc112359d77793ba8cd645030b365884103bdba0bcc0df8a9dd199328639d74b"
INNER_ARCHIVE = "ULDLINUX_V1.00.39.07_01.24/uld-samsung.tar.gz"
SOURCE_PPD = "uld/noarch/share/ppd/Samsung_M203x_Series.ppd"
SOURCE_FILTER = "uld/x86_64/rastertospl"
FILTER_SHA256 = "8d67279ae201fce442490797597c01a02bc39d9f3d84016e3aa59d0284121288"
PPD_SHA256 = "cbce159e8f885b17ef90cb1fb5198c0f736185a709b34f0fade6d9a28632f491"
FILTER_NAME = "chromeos-printer-samsung-uld-rastertospl"
FILTER_TARGET = Path("/usr/lib/cups/filter") / FILTER_NAME
ZIP_SIZE_LIMIT = 24_000_000
TAR_SIZE_LIMIT = 26_000_000
SUPPORTED_MODELS = frozenset({"Samsung SL-M2030W", "Samsung M203x Series"})


class VendorDriverError(RuntimeError):
    """공식 파일 검증, 설치 또는 환경 점검 실패."""


@dataclass(frozen=True)
class SamsungInstallResult:
    message: str
    ppd_path: str


def supports_samsung_uld(identity: PrinterIdentity) -> bool:
    return (
        identity.source == "IPP 장치 응답"
        and identity.manufacturer == "Samsung"
        and identity.name in SUPPORTED_MODELS
        and identity.name == f"{identity.manufacturer} {identity.model}"
    )


def vendor_architecture_ok() -> bool:
    return platform.machine().lower() in {"x86_64", "amd64"}


def _download_official() -> bytes:
    url = urlparse(SAMSUNG_ULD_URL)
    if url.scheme != "https" or url.hostname != "downloadcenter.samsung.com":
        raise VendorDriverError("삼성 공식 다운로드 주소가 아닙니다.")
    request = Request(SAMSUNG_ULD_URL, headers={"User-Agent": "ChromeOS-Printer-Supporter/0.1"})
    try:
        with urlopen(request, timeout=40) as response:
            actual = urlparse(response.url)
            if actual.scheme != "https" or actual.hostname != url.hostname:
                raise VendorDriverError("공식 다운로드 서버에서 다른 서버로 이동했습니다.")
            data = response.read(ZIP_SIZE_LIMIT + 1)
    except (OSError, TimeoutError) as exc:
        raise VendorDriverError("삼성 공식 드라이버 다운로드에 실패했습니다.") from exc
    if len(data) > ZIP_SIZE_LIMIT:
        raise VendorDriverError("예상보다 큰 드라이버 파일입니다.")
    return data


def _read_one(archive: tarfile.TarFile, name: str, limit: int) -> bytes:
    try:
        entry = archive.getmember(name)
        if not entry.isfile() or entry.size > limit or entry.size <= 0:
            raise VendorDriverError("공식 압축파일의 구성에 문제가 있습니다.")
        file = archive.extractfile(entry)
        if file is None:
            raise VendorDriverError("드라이버 파일을 읽을 수 없습니다.")
        with file:
            data = file.read(limit + 1)
        if len(data) != entry.size:
            raise VendorDriverError("드라이버 파일 크기가 일치하지 않습니다.")
        return data
    except KeyError as exc:
        raise VendorDriverError("공식 압축파일에 필요한 드라이버가 없습니다.") from exc


def extract_verified_files(raw: bytes) -> tuple[bytes, bytes]:
    """임의 경로를 풀지 않고 고정된 파일 두 개만 추출합니다."""
    if sha256(raw).hexdigest() != SAMSUNG_ULD_SHA256:
        raise VendorDriverError("공식 드라이버 SHA-256 검증에 실패했습니다.")
    try:
        with zipfile.ZipFile(BytesIO(raw)) as zipped:
            entry = zipped.getinfo(INNER_ARCHIVE)
            if entry.file_size > TAR_SIZE_LIMIT or entry.file_size <= 0:
                raise VendorDriverError("압축파일 크기가 예상 범위를 벗어납니다.")
            tar_bytes = zipped.read(entry)
        with tarfile.open(fileobj=BytesIO(tar_bytes), mode="r:gz") as nested:
            filter_data = _read_one(nested, SOURCE_FILTER, 200_000)
            ppd_data = _read_one(nested, SOURCE_PPD, 200_000)
    except (zipfile.BadZipFile, tarfile.TarError, KeyError, RuntimeError, OSError) as exc:
        raise VendorDriverError("공식 드라이버 압축파일을 읽지 못했습니다.") from exc
    if sha256(filter_data).hexdigest() != FILTER_SHA256:
        raise VendorDriverError("CUPS 필터 SHA-256이 일치하지 않습니다.")
    if sha256(ppd_data).hexdigest() != PPD_SHA256:
        raise VendorDriverError("Samsung M203x PPD SHA-256이 일치하지 않습니다.")
    if (
        b'*ModelName: "Samsung M203x Series"' not in ppd_data
        or b'*cupsFilter:  "application/vnd.cups-raster 0 rastertospl"' not in ppd_data
    ):
        raise VendorDriverError("Samsung M203x PPD 내용이 예상과 다릅니다.")
    if not filter_data.startswith(b"\x7fELF\x02\x01") or filter_data[18:20] != b"\x3e\x00":
        raise VendorDriverError("x86_64 인쇄 필터가 아닙니다.")
    replacement = b'*cupsFilter:  "application/vnd.cups-raster 0 ' + FILTER_NAME.encode() + b'"'
    updated_ppd = ppd_data.replace(
        b'*cupsFilter:  "application/vnd.cups-raster 0 rastertospl"',
        replacement,
        1,
    )
    return filter_data, updated_ppd


def install_samsung_uld(
    identity: PrinterIdentity,
    *,
    approved: bool,
    runner: Callable[..., CompletedProcess[str]] = run,
    downloader: Callable[[], bytes] = _download_official,
    filter_target: Path = FILTER_TARGET,
    data_dir: Path | None = None,
) -> SamsungInstallResult:
    if not approved:
        raise VendorDriverError("사용자 승인 없이 드라이버를 설치할 수 없습니다.")
    if not supports_samsung_uld(identity):
        raise VendorDriverError("Samsung SL-M2030W/M203x 모델 정보가 확인되지 않았습니다.")
    if not vendor_architecture_ok():
        raise VendorDriverError("삼성 ULD는 x86_64 Chromebook에서만 지원합니다.")
    raw = downloader()
    filter_data, ppd_data = extract_verified_files(raw)
    dest_dir = (data_dir if data_dir is not None else (
        Path.home() / ".local/share/chromeos-printer-supporter/drivers"
    ))
    ppd_path = dest_dir / "Samsung_M203x_Series.ppd"
    # 변경된 파일이 이미 존재할 경우 덮어쓰지 않습니다.
    if filter_target.exists() and sha256(filter_target.read_bytes()).digest() != sha256(filter_data).digest():
        raise VendorDriverError("기존 CUPS 필터가 달라서 덮어쓰지 않습니다.")
    if ppd_path.exists() and ppd_path.read_bytes() != ppd_data:
        raise VendorDriverError("기존 PPD 파일이 달라서 덮어쓰지 않습니다.")
    # 필터의 ELF DT_NEEDED에 libcupsimage.so.2가 명시되어 있습니다.
    # 설치 전 이미 확인한 명령을 실행합니다 (sudo 비대화식, 스크립트 실행 없음).
    try:
        dependency = runner(
            ["sudo", "-n", "apt-get", "install", "-y", "--no-install-recommends", "libcupsimage2"],
            capture_output=True, text=True, check=False, timeout=240,
        )
    except OSError as exc:
        raise VendorDriverError("필터 의존성(libcupsimage2) 설치를 시작할 수 없습니다.") from exc
    if dependency.returncode:
        raise VendorDriverError(
            "필터 의존성(libcupsimage2) 설치 실패: "
            + (dependency.stderr or dependency.stdout or "권한 확인 필요")[-400:]
        )
    # 실제 CUPS가 로드하는 filter 경로만 sudo 설치. 제조사 쉘 파일은 실행하지 않음.
    with TemporaryDirectory(prefix="samsung-uld-") as temp:
        source = Path(temp) / FILTER_NAME
        source.write_bytes(filter_data)
        source.chmod(0o644)
        if not filter_target.exists():
            try:
                result = runner(
                    ["sudo", "-n", "install", "-m", "0755", str(source), str(filter_target)],
                    capture_output=True, text=True, check=False, timeout=40,
                )
            except OSError as exc:
                raise VendorDriverError("CUPS 필터를 설치할 수 없습니다.") from exc
            if result.returncode:
                raise VendorDriverError(
                    "CUPS 필터 설치 실패: " + (result.stderr or result.stdout or "권한 확인 필요")[-400:]
                )
        if not filter_target.is_file() or sha256(filter_target.read_bytes()).hexdigest() != FILTER_SHA256:
            raise VendorDriverError("설치된 CUPS 필터 검증에 실패했습니다.")
        dest_dir.mkdir(parents=True, exist_ok=True)
        if not ppd_path.exists():
            # 실패 시 임시 PPD가 남지 않도록 파일 교체는 마지막 단계에서 수행.
            tmp_ppd = dest_dir / (ppd_path.name + ".tmp")
            try:
                with open(tmp_ppd, "xb") as file:
                    file.write(ppd_data)
                os.replace(tmp_ppd, ppd_path)
            finally:
                tmp_ppd.unlink(missing_ok=True)
    if ppd_path.read_bytes() != ppd_data:
        raise VendorDriverError("설치된 PPD 검증에 실패했습니다.")
    return SamsungInstallResult(
        "삼성 공식 M203x 드라이버의 PPD와 x86_64 CUPS 필터를 설치했습니다. "
        "등록 전 프린터 모델을 확인해 주세요.",
        str(ppd_path),
    )
