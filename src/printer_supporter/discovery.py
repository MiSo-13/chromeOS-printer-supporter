"""CUPS 네트워크 탐색과 사용자 승인 기반 로컬 큐 등록."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from itertools import islice
from ipaddress import ip_address
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run
from typing import Callable
from urllib.parse import unquote, urlsplit
import re
import shutil
import socket

ALLOWED_SCHEMES = {"ipp", "ipps", "dnssd", "socket"}
QUEUE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
MAX_DISCOVERED_DEVICES = 96
MAX_DISCOVERY_LINES = 512
MAX_PRINTER_URI = 1024


class PrinterRegistrationError(RuntimeError):
    """네트워크 프린터 등록과 관련된 안내용 오류."""


@dataclass(frozen=True)
class DiscoveredPrinter:
    name: str
    uri: str
    scheme: str


@dataclass(frozen=True)
class Registration:
    name: str
    uri: str
    driver: str = "everywhere"
    ppd_path: str | None = None
    driver_model: str | None = None


def parse_discovered_devices(output: str) -> list[DiscoveredPrinter]:
    devices: dict[str, DiscoveredPrinter] = {}
    for line in islice(StringIO(output), MAX_DISCOVERY_LINES):
        # lpinfo -v 결과 예: network dnssd://Printer._ipp._tcp.local/
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or parts[0] != "network":
            continue
        uri = parts[1].strip()
        parsed = urlsplit(uri)
        if parsed.scheme not in ALLOWED_SCHEMES or not parsed.netloc:
            continue
        if not _safe_discovery_uri(uri, parsed):
            continue
        if len(devices) >= MAX_DISCOVERED_DEVICES:
            break
        # URI의 hostname 속성은 소문자로 변환되므로 원본 서비스 표시명을 사용합니다.
        name = unquote(parsed.netloc).split("._", 1)[0].replace("-", " ")
        devices[uri] = DiscoveredPrinter(name[:160] or "네트워크 프린터", uri, parsed.scheme)
    return sorted(devices.values(), key=lambda value: value.name.lower())


def _safe_discovery_uri(uri: str, parsed=None) -> bool:
    """외부 검색 결과로부터 명령/IPP 조회에 사용할 URI만 보수적으로 허용."""
    if not uri or len(uri) > MAX_PRINTER_URI or any(
        c.isspace() or ord(c) < 32 for c in uri
    ):
        return False
    try:
        parsed = parsed or urlsplit(uri)
        return bool(
            parsed.scheme in ALLOWED_SCHEMES and parsed.hostname
            and not parsed.username and not parsed.password
            and parsed.port != 0
        )
    except ValueError:
        return False


def parse_ippfind_devices(output: str) -> list[DiscoveredPrinter]:
    """ippfind가 출력한 실제 IPP/IPPS URI만 사용하며 모델명을 추정하지 않습니다."""
    found: dict[str, DiscoveredPrinter] = {}
    for line in islice(StringIO(output), MAX_DISCOVERY_LINES):
        uri = line.strip()
        if not _safe_discovery_uri(uri):
            continue
        parsed = urlsplit(uri)
        if parsed.scheme not in {"ipp", "ipps"} or uri in found:
            continue
        # 호스트 이름은 확인된 프린터 모델명이 아닙니다.
        found[uri] = DiscoveredPrinter((parsed.hostname or "IPP 프린터")[:160], uri, parsed.scheme)
        if len(found) >= MAX_DISCOVERED_DEVICES:
            break
    return sorted(found.values(), key=lambda device: device.name.lower())


def manual_printer(ip: str, *, protocol: str) -> DiscoveredPrinter:
    try:
        address = ip_address(ip.strip())
    except ValueError as exc:
        raise PrinterRegistrationError("올바른 IP 주소를 입력해 주세요.") from exc
    if address.version != 4:
        raise PrinterRegistrationError("현재 버전에서는 IPv4 주소만 직접 입력할 수 있습니다.")
    if address.is_unspecified or address.is_multicast or address.is_loopback:
        raise PrinterRegistrationError("프린터의 실제 네트워크 IP를 입력해 주세요.")
    if protocol == "ipp":
        uri = f"ipp://{address}/ipp/print"
    elif protocol == "socket":
        uri = f"socket://{address}:9100"
    else:
        raise PrinterRegistrationError("지원하지 않는 연결 방식입니다.")
    return DiscoveredPrinter(str(address), uri, protocol)


def validate_registration(registration: Registration) -> None:
    if not QUEUE_PATTERN.fullmatch(registration.name):
        raise PrinterRegistrationError("큐 이름은 영문자로 시작하고 영문·숫자·._-만 사용할 수 있습니다.")
    parsed = urlsplit(registration.uri)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.netloc:
        raise PrinterRegistrationError("지원하지 않는 프린터 연결 주소입니다.")
    if any(char.isspace() for char in registration.uri):
        raise PrinterRegistrationError("연결 주소에는 공백을 사용할 수 없습니다.")
    if registration.driver == "everywhere":
        if parsed.scheme not in {"ipp", "ipps", "dnssd"}:
            raise PrinterRegistrationError("IPP Everywhere는 IPP 연결 방식에서만 사용할 수 있습니다.")
    elif registration.driver == "ppd":
        ppd = Path(registration.ppd_path or "").expanduser()
        if not ppd.is_file() or ppd.suffix.lower() != ".ppd":
            raise PrinterRegistrationError("유효한 PPD 파일을 선택해 주세요.")
    elif registration.driver == "model":
        from .driver_recommendation import safe_model_id
        if not registration.driver_model or not safe_model_id(registration.driver_model):
            raise PrinterRegistrationError("유효한 CUPS 드라이버 모델 ID를 선택해 주세요.")
    else:
        raise PrinterRegistrationError("지원하지 않는 드라이버 방식입니다.")


def registration_command(registration: Registration) -> list[str]:
    """등록 전 확인창과 실제 실행에서 동일한 명령을 사용합니다."""
    args = [
        "sudo", "-n", "lpadmin", "-p", registration.name,
        "-E", "-v", registration.uri,
        "-o", "printer-is-shared=false",
    ]
    if registration.driver == "ppd":
        args.extend(["-P", str(Path(registration.ppd_path).expanduser())])
    elif registration.driver == "model":
        args.extend(["-m", registration.driver_model])
    else:
        args.extend(["-m", "everywhere"])
    return args


class DiscoveryService:
    def __init__(
        self,
        runner: Callable[..., CompletedProcess[str]] = run,
        connector: Callable[..., socket.socket] = socket.create_connection,
        which: Callable[[str], str | None] = shutil.which,
    ):
        self.runner = runner
        self.connector = connector
        self.which = which

    def _run(self, command: list[str], timeout: int = 20) -> str:
        try:
            result = self.runner(
                command, capture_output=True, text=True, check=False, timeout=timeout,
            )
        except (OSError, TimeoutExpired) as exc:
            raise PrinterRegistrationError(f"CUPS 명령 실행 실패: {exc}") from exc
        if result.returncode:
            raise PrinterRegistrationError(
                (result.stderr or result.stdout or "CUPS 명령 실행 실패").strip()
            )
        return result.stdout

    def discover(self) -> list[DiscoveredPrinter]:
        """사용자가 요청한 시점에만 CUPS와 짧은 DNS-SD 탐색을 실행합니다.

        lpinfo의 dnssd:// 서비스 이름만으로는 IPP 모델을 확인할 수 없으므로
        ippfind에서 실제 IPP 주소를 찾으면 함께 표시합니다. 네트워크 대역을
        스캔하거나 백그라운드에서 반복 실행하지 않습니다.
        """
        cups_error: PrinterRegistrationError | None = None
        try:
            devices = parse_discovered_devices(self._run(["lpinfo", "-v"], timeout=10))
        except PrinterRegistrationError as exc:
            cups_error = exc
            devices = []

        # 일부 IPP 프린터가 보여도 다른 장치는 dnssd 이름만 나올 수 있습니다.
        # 그런 경우에만 보조 검색을 실행하고, 이미 모두 IPP라면 생략합니다.
        if any(device.scheme == "dnssd" for device in devices) or not any(
            device.scheme in {"ipp", "ipps"} for device in devices
        ):
            ippfind = self.which("ippfind")
            if ippfind:
                try:
                    resolved = parse_ippfind_devices(self._run(
                        [ippfind, "-T", "2", "_ipp._tcp", "_ipps._tcp", "--print"],
                        timeout=7,
                    ))
                    known = {device.uri for device in devices}
                    devices.extend(device for device in resolved if device.uri not in known)
                except PrinterRegistrationError:
                    # ippfind이 없거나 이 네트워크에서 DNS-SD가 막혀 있어도
                    # CUPS 결과와 IP 직접 입력은 유지합니다.
                    pass

        if not devices and cups_error is not None:
            raise cups_error
        # 결과가 많을 때 실제 IPP 모델 조회가 가능한 주소를 우선 표시합니다.
        return sorted(
            devices,
            key=lambda value: (value.scheme not in {"ipp", "ipps"}, value.name.lower()),
        )[:MAX_DISCOVERED_DEVICES]

    def probe(self, device: DiscoveredPrinter) -> str:
        parsed = urlsplit(device.uri)
        if parsed.scheme not in {"ipp", "ipps", "socket"}:
            return "mDNS 장치는 등록 과정에서 연결을 확인합니다."
        port = parsed.port or (9100 if parsed.scheme == "socket" else 631)
        try:
            connection = self.connector((parsed.hostname, port), timeout=3)
            connection.close()
        except OSError as exc:
            raise PrinterRegistrationError(f"프린터 연결에 실패했습니다: {exc}") from exc
        return f"{parsed.hostname}:{port} 연결에 성공했습니다."

    def register(self, registration: Registration, *, approved: bool = False) -> str:
        if not approved:
            raise PrinterRegistrationError("프린터 등록 전에 사용자 확인이 필요합니다.")
        validate_registration(registration)
        existing = set(self._run(["lpstat", "-e"]).splitlines())
        if registration.name in existing:
            raise PrinterRegistrationError(
                "동일한 이름의 프린터가 이미 등록되어 있습니다. 기존 설정을 덮어쓰지 않습니다."
            )
        if registration.driver == "model":
            from .driver_recommendation import parse_installed_drivers
            # 드롭다운의 값만 신뢰하지 않고 등록 직전에 실제 CUPS 카탈로그를 재확인.
            available = {
                entry.model_id for entry in parse_installed_drivers(self._run(["lpinfo", "-m"]))
            }
            if registration.driver_model not in available:
                raise PrinterRegistrationError(
                    "선택한 CUPS 드라이버가 현재 설치 목록에 없습니다. 다시 조회해 주세요."
                )
        self._run(registration_command(registration), timeout=60)
        return f"{registration.name} 프린터를 Crostini CUPS에 등록했습니다."
