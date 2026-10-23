"""읽기 전용 IPP 속성으로 제조사·모델과 드라이버리스 가능성을 진단합니다.

스캔 이름만으로 IPP Everywhere 지원이나 드라이버 설치 필요 여부를 확정하지 않습니다.
이 모듈은 프린트 작업이나 패키지/드라이버 설치 명령을 실행하지 않습니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run
from tempfile import TemporaryDirectory
from typing import Callable
from urllib.parse import urlsplit
import re
import shutil

from .discovery import DiscoveredPrinter


# Get-Printer-Attributes 외 다른 IPP 작업은 실행하지 않습니다.
IPP_IDENTITY_TEST = """{
NAME "Read printer identity"
OPERATION Get-Printer-Attributes
GROUP operation-attributes-tag
ATTR charset attributes-charset utf-8
ATTR language attributes-natural-language en
ATTR uri printer-uri $uri
ATTR keyword requested-attributes printer-make-and-model,printer-name,ipp-versions-supported,ipp-features-supported,document-format-supported
STATUS successful-ok
}
"""

_RECOGNIZED_VENDORS = (
    ("Hewlett-Packard", "HP"), ("Hewlett Packard", "HP"), ("HP", "HP"),
    ("Fuji Xerox", "Fuji Xerox"), ("Samsung", "Samsung"),
    ("Canon", "Canon"), ("Brother", "Brother"), ("Epson", "Epson"),
    ("Kyocera", "Kyocera"), ("Ricoh", "Ricoh"), ("Xerox", "Xerox"),
    ("Lexmark", "Lexmark"), ("OKI", "OKI"), ("Sharp", "Sharp"),
    ("Pantum", "Pantum"), ("Konica Minolta", "Konica Minolta"),
)
_ATTRIBUTE_LINE = re.compile(
    r"^\s*(printer-make-and-model|printer-name|ipp-versions-supported|"
    r"ipp-features-supported|document-format-supported)\s+\([^)]*\)\s*=\s*(.*?)\s*$",
    re.IGNORECASE,
)
_IPP_VERSION = re.compile(r"^\d+\.\d+$")


@dataclass(frozen=True)
class PrinterIdentity:
    name: str
    manufacturer: str | None
    model: str | None
    protocol: str
    source: str
    driverless: str             # reported | candidate | unknown
    recommendation: str
    ipp_versions: tuple[str, ...] = ()
    document_formats: tuple[str, ...] = ()


def parse_ipp_attributes(output: str) -> dict[str, tuple[str, ...]]:
    """ipptool -tv의 속성 줄만 추출합니다 (제어 문자열/기타 로그는 무시)."""
    attributes: dict[str, tuple[str, ...]] = {}
    for line in output.splitlines():
        match = _ATTRIBUTE_LINE.fullmatch(line)
        if not match:
            continue
        key = match.group(1).lower()
        values = tuple(
            value.strip().strip('"').strip("'")
            for value in match.group(2).split(",")
            if value.strip()
        )
        if values:
            attributes[key] = values
    return attributes


def _vendor_and_model(name: str) -> tuple[str | None, str | None]:
    for prefix, vendor in _RECOGNIZED_VENDORS:
        if name.casefold() == prefix.casefold():
            return vendor, None
        if name.casefold().startswith(prefix.casefold() + " "):
            return vendor, name[len(prefix):].strip() or None
    return None, None


def identity_from_attributes(
    device: DiscoveredPrinter, attributes: dict[str, tuple[str, ...]]
) -> PrinterIdentity:
    reported = attributes.get("printer-make-and-model", ())
    verified_name = (reported[0] if reported else "").strip()[:160]
    service_name = device.name.strip()[:160] or "모델 미확인"
    name = verified_name or service_name
    vendor, model = _vendor_and_model(name)
    if not verified_name and service_name == device.uri:
        name = "모델 미확인"
        vendor, model = None, None

    versions = tuple(v for v in attributes.get("ipp-versions-supported", ()) if _IPP_VERSION.fullmatch(v))
    formats = tuple(v.lower() for v in attributes.get("document-format-supported", ()))
    features = tuple(v.lower() for v in attributes.get("ipp-features-supported", ()))
    has_v2 = any(int(v.split(".", 1)[0]) >= 2 for v in versions)
    has_pwg = "image/pwg-raster" in formats
    if "ipp-everywhere" in features:
        driverless = "reported"
        advice = (
            "프린터가 IPP Everywhere 기능을 보고했습니다. "
            "실제 인쇄 호환성 및 인증 여부는 아직 검증되지 않았습니다."
        )
    elif has_v2 and has_pwg:
        driverless = "candidate"
        advice = (
            "IPP 2.x와 PWG Raster 지원이 확인되어 드라이버리스 후보입니다. "
            "IPP Everywhere 인증이나 실제 인쇄 성공을 보장하지 않습니다."
        )
    else:
        driverless = "unknown"
        advice = (
            "IPP Everywhere 지원을 확인할 근거가 부족합니다. "
            "등록 전 호환성을 확인하거나 제조사 드라이버(PPD)를 선택하세요."
        )
    return PrinterIdentity(
        name=name,
        manufacturer=vendor,
        model=model,
        protocol=device.scheme.upper(),
        source="IPP 장치 응답" if verified_name else "검색된 이름(추정) / IPP 기능 조회",
        driverless=driverless,
        recommendation=advice,
        ipp_versions=versions,
        document_formats=formats,
    )


def unknown_identity(device: DiscoveredPrinter, reason: str = "") -> PrinterIdentity:
    name = device.name.strip()[:160]
    # IP 직접 입력은 모델 추정에 사용하지 않습니다.
    parsed = urlsplit(device.uri)
    if name == parsed.hostname or not name:
        name = "모델 미확인"
    vendor, model = _vendor_and_model(name)
    if device.scheme == "socket":
        guidance = "Socket/JetDirect 연결은 모델을 식별할 IPP 속성이 없습니다. 제조사 PPD 정보를 확인하세요."
    elif device.scheme == "dnssd":
        guidance = (
            "mDNS 서비스 이름만 확인되었습니다. 모델/드라이버리스 여부는 미검증입니다. "
            "프린터 IPP 주소로 직접 연결해 속성을 확인할 수 있습니다."
        )
    else:
        guidance = "프린터의 IPP 속성을 조회하지 못했습니다. 제조사 및 지원 드라이버를 확인하세요."
    if reason:
        guidance += " " + reason[:240]
    return PrinterIdentity(
        name=name,
        manufacturer=vendor,
        model=model,
        protocol=device.scheme.upper(),
        source="검색된 이름(미검증)" if name != "모델 미확인" else "확인 불가",
        driverless="unknown",
        recommendation=guidance,
    )


def identify_printer(
    device: DiscoveredPrinter,
    *,
    runner: Callable[..., CompletedProcess[str]] = run,
    which: Callable[[str], str | None] = shutil.which,
) -> PrinterIdentity:
    """IPP/IPPS 대상에만 1회 Get-Printer-Attributes를 호출합니다.

    dnssd URI는 직접 조회 가능한 IPP URI가 아니므로 이름만 보여주며,
    socket URI는 IPP로 임의 변경하여 조회하지 않습니다.
    """
    parsed = urlsplit(device.uri)
    if device.scheme not in {"ipp", "ipps"} or parsed.scheme != device.scheme:
        return unknown_identity(device)

    if not parsed.hostname or parsed.username or parsed.password or any(
        char.isspace() or ord(char) < 32 for char in device.uri
    ):
        return unknown_identity(device, "연결 URI 형식이 올바르지 않습니다.")

    ipptool = which("ipptool")
    if not ipptool:
        return unknown_identity(
            device, "IPP 속성 조회 도구가 없습니다. Debian에서는 cups-ipp-utils 패키지를 설치하세요."
        )
    try:
        with TemporaryDirectory(prefix="chromeos-printer-ipp-") as directory:
            script = Path(directory) / "identity.test"
            script.write_text(IPP_IDENTITY_TEST, encoding="utf-8")
            command = [ipptool, "-t", "-v", "-T", "5", device.uri, str(script)]
            result = runner(
                command, capture_output=True, text=True, check=False, timeout=12
            )
        if result.returncode:
            return unknown_identity(device, "IPP 장치 응답을 가져오지 못했습니다.")
        attributes = parse_ipp_attributes(result.stdout)
        if not attributes:
            return unknown_identity(device, "IPP 속성 응답에서 모델 정보를 확인하지 못했습니다.")
        return identity_from_attributes(device, attributes)
    except (OSError, TimeoutExpired):
        return unknown_identity(device, "IPP 정보 조회 중 연결 오류 또는 시간 초과가 발생했습니다.")
