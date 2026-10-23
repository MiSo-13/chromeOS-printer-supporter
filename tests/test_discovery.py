"""네트워크 프린터 검색·검증·승인 기반 등록 테스트."""

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from printer_supporter.discovery import (
    DiscoveryService, PrinterRegistrationError, Registration,
    manual_printer, parse_discovered_devices, validate_registration,
)


def test_parse_cups_network_devices_only():
    output = (
        "network dnssd://Samsung%20M203x._ipp._tcp.local/\n"
        "network socket://192.168.6.147:9100\n"
        "direct usb://SomeDevice\n"
        "network ipp://192.168.6.150/ipp/print\n"
        "network socket\n"
    )
    devices = parse_discovered_devices(output)
    assert len(devices) == 3
    assert {device.scheme for device in devices} == {"dnssd", "socket", "ipp"}
    assert any(device.name == "Samsung M203x" for device in devices)


def test_manual_ip_builds_expected_uri():
    assert manual_printer("192.168.6.147", protocol="socket").uri == (
        "socket://192.168.6.147:9100"
    )
    assert manual_printer("192.168.6.147", protocol="ipp").uri == (
        "ipp://192.168.6.147/ipp/print"
    )


@pytest.mark.parametrize("ip", ["bad-host", "127.0.0.1", "224.0.0.1", "::1"])
def test_manual_ip_rejects_unsupported_address(ip):
    with pytest.raises(PrinterRegistrationError):
        manual_printer(ip, protocol="ipp")


def test_ipp_cannot_use_socket_uri():
    with pytest.raises(PrinterRegistrationError, match="IPP Everywhere"):
        validate_registration(Registration("Samsung_SL_M2030W", "socket://192.168.6.147:9100"))


def test_ppd_requires_real_file(tmp_path):
    with pytest.raises(PrinterRegistrationError, match="PPD"):
        validate_registration(
            Registration("Samsung_SL_M2030W", "socket://192.168.6.147:9100",
                         "ppd", str(tmp_path / "missing.ppd"))
        )


def test_registration_needs_explicit_approval():
    service = DiscoveryService(runner=lambda *a, **k: pytest.fail("실행하면 안 됩니다"))
    with pytest.raises(PrinterRegistrationError, match="사용자 확인"):
        service.register(Registration("Printer_1", "ipp://192.168.6.147/ipp/print"))


def test_existing_queue_is_not_overwritten():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, "Printer_1\n", "")

    service = DiscoveryService(runner=runner)
    with pytest.raises(PrinterRegistrationError, match="이미 등록"):
        service.register(Registration("Printer_1", "ipp://192.168.6.147/ipp/print"), approved=True)
    assert calls == [["lpstat", "-e"]]


def test_register_ipp_uses_everywhere_without_changing_default():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, "", "")

    service = DiscoveryService(runner=runner)
    message = service.register(
        Registration("Printer_1", "ipp://192.168.6.147/ipp/print"), approved=True
    )
    assert "등록했습니다" in message
    assert calls[0] == ["lpstat", "-e"]
    assert calls[1] == [
        "sudo", "-n", "lpadmin", "-p", "Printer_1", "-E",
        "-v", "ipp://192.168.6.147/ipp/print", "-o",
        "printer-is-shared=false", "-m", "everywhere",
    ]
    assert "-d" not in calls[1]


def test_register_ppd_does_not_modify_source(tmp_path):
    ppd = tmp_path / "Samsung.ppd"
    ppd.write_text("*PPD-Adobe: \"4.3\"", encoding="utf-8")
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return CompletedProcess(command, 0, "", "")

    service = DiscoveryService(runner=runner)
    service.register(
        Registration("Samsung_M2030W", "socket://192.168.6.147:9100",
                     "ppd", str(ppd)), approved=True
    )
    assert commands[1][-2:] == ["-P", str(ppd)]
    assert ppd.read_text(encoding="utf-8") == '*PPD-Adobe: "4.3"'


def test_discovery_does_not_scan_network_ranges():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, "network ipp://192.168.6.147/ipp/print\n", "")

    devices = DiscoveryService(runner=runner).discover()
    assert len(devices) == 1
    assert calls == [["lpinfo", "-v"]]
