"""CUPS 네트워크 탐색과 사용자 승인 기반 로컬 큐 등록."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run
from typing import Callable
from urllib.parse import unquote, urlsplit
import re
import socket

ALLOWED_SCHEMES = {"ipp", "ipps", "dnssd", "socket"}
QUEUE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


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
    devices = {}
    for line in output.splitlines():
        # lpinfo -v 결과 예: network dnssd://Printer._ipp._tcp.local/
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or parts[0] != "network":
            continue
        uri = parts[1].strip()
        parsed = urlsplit(uri)
        if parsed.scheme not in ALLOWED_SCHEMES or not parsed.netloc:
            continue
        name = unquote(parsed.netloc).split("._", 1)[0].replace("-", " ")
        devices[uri] = DiscoveredPrinter(name or "네트워크 프린터", uri, parsed.scheme)
    return sorted(devices.values(), key=lambda value: value.name.lower())


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
    ):
        self.runner = runner
        self.connector = connector

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
        # CUPS 및 mDNS의 발견 결과만 조회하며 IP 대역 전체를 스캔하지 않습니다.
        return parse_discovered_devices(self._run(["lpinfo", "-v"]))

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
