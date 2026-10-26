"""네트워크 프린터 검색·검증·승인 기반 등록 테스트."""

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from printer_supporter.discovery import (
    DiscoveryService, PrinterRegistrationError, Registration,
    manual_printer, parse_discovered_devices, parse_ippfind_devices,
    validate_registration, MAX_DISCOVERED_DEVICES,
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


@pytest.mark.parametrize("ip,protocol,path,port,expected", [
    ("192.168.6.147", "ipp", "/ipp/printer", None,
     "ipp://192.168.6.147/ipp/printer"),
    ("192.168.6.147", "ipps", "/printers/Office", "443",
     "ipps://192.168.6.147:443/printers/Office"),
    ("2001:db8::147", "ipps", "/ipp/print", None,
     "ipps://[2001:db8::147]/ipp/print"),
    ("192.168.6.147", "socket", "/ignored", "9101",
     "socket://192.168.6.147:9101"),
])
def test_manual_connection_supports_standard_ipp_paths_and_ip_versions(
    ip, protocol, path, port, expected,
):
    printer = manual_printer(ip, protocol=protocol, path=path, port=port)
    assert printer.uri == expected
    assert printer.scheme == protocol


@pytest.mark.parametrize("port", ["0", "65536", "631?x=y", "-1", "abc", "６３１", "9" * 100])
def test_manual_port_rejects_unsafe_values(port):
    with pytest.raises(PrinterRegistrationError, match="포트"):
        manual_printer("192.168.6.147", protocol="ipps", port=port)


@pytest.mark.parametrize("path", ["", "//evil", "/../ipp", "/./print",
                                   "/ipp?version=1.1", "/ipp#x", "/ipp print",
                                   "/ipp\\print", "/ipp%ZZ", "/" + "x" * 256])
def test_manual_ipp_path_requires_safe_absolute_resource(path):
    with pytest.raises(PrinterRegistrationError, match="IPP 경로"):
        manual_printer("192.168.6.147", protocol="ipp", path=path)


@pytest.mark.parametrize("ip", ["::1", "ff02::1", "fe80::1", "fe80::1%eth0",
                                     "::ffff:127.0.0.1"])
def test_manual_ipv6_rejects_loopback_multicast_and_scoped_addresses(ip):
    with pytest.raises(PrinterRegistrationError):
        manual_printer(ip, protocol="ipps")


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


def test_manual_ipps_registration_still_requires_separate_approval():
    printer = manual_printer(
        "192.168.6.147", protocol="ipps", path="/printers/Office", port="443",
    )
    commands = []
    service = DiscoveryService(runner=lambda command, **kwargs: commands.append(command))
    with pytest.raises(PrinterRegistrationError, match="사용자 확인"):
        service.register(Registration("Printer_1", printer.uri))
    assert commands == []
    validate_registration(Registration("Printer_1", printer.uri))


def test_ipps_tcp_probe_does_not_claim_tls_or_printing_success():
    connected = []

    class FakeSocket:
        def close(self):
            connected.append("closed")

    def connector(address, timeout):
        connected.append((address, timeout))
        return FakeSocket()

    service = DiscoveryService(connector=connector)
    printer = manual_printer("192.168.6.147", protocol="ipps", port="443")
    result = service.probe(printer)
    assert connected == [(("192.168.6.147", 443), 3), "closed"]
    assert "TCP" in result and "TLS" in result and "별도" in result


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


def test_installed_cups_model_registration_requires_user_approval():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command == ["lpstat", "-e"]:
            return CompletedProcess(command, 0, "", "")
        if command == ["lpinfo", "-m"]:
            return CompletedProcess(
                command, 0,
                "drv:///samsung/m203x.ppd Samsung M203x Series\n", "",
            )
        return CompletedProcess(command, 0, "", "")

    service = DiscoveryService(runner=runner)
    registration = Registration(
        "Samsung_M203x", "socket://192.168.6.147:9100",
        "model", None, "drv:///samsung/m203x.ppd",
    )
    with pytest.raises(PrinterRegistrationError, match="사용자 확인"):
        service.register(registration)
    assert not calls

    service.register(registration, approved=True)
    assert calls[:2] == [["lpstat", "-e"], ["lpinfo", "-m"]]
    assert calls[2][-2:] == ["-m", "drv:///samsung/m203x.ppd"]
    assert calls[2][:3] == ["sudo", "-n", "lpadmin"]
    assert "-d" not in calls[2]


def test_cups_model_unavailable_at_registration_cannot_be_submitted():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command == ["lpinfo", "-m"]:
            return CompletedProcess(
                command, 0, "drv:///other.ppd Samsung M2030W\n", "",
            )
        return CompletedProcess(command, 0, "", "")

    service = DiscoveryService(runner=runner)
    with pytest.raises(PrinterRegistrationError, match="설치 목록"):
        service.register(
            Registration("Printer_1", "socket://192.168.6.147:9100", "model",
                         None, "drv:///samsung/m203x.ppd"),
            approved=True,
        )
    assert not any("lpadmin" in c for c in calls)


@pytest.mark.parametrize("model", [None, "raw", "everywhere", "bad model",
                                    "-P", "bad\nvalue"])
def test_invalid_cups_model_rejected_before_any_system_command(model):
    calls = []
    service = DiscoveryService(
        runner=lambda command, **kwargs: calls.append(command)
    )
    with pytest.raises(PrinterRegistrationError, match="모델 ID"):
        service.register(
            Registration("Printer_1", "ipp://192.168.6.147/ipp/print",
                         "model", None, model),
            approved=True,
        )
    assert calls == []


def test_ippfind_parses_only_safe_ipp_uris_with_limits():
    uris = "\n".join([
        "ipp://printer.local./ipp/print",
        "ipps://secure.local:631/ipp/print",
        "ipp://printer.local./ipp/print",
        "https://bad.example",
        "ipp://user:password@bad.local/ipp/print",
        "ipp://host.local/path\tunsafe",
        "ipp://broken.local:invalid/ipp/print",
        "socket://printer.local:9100",
    ])
    devices = parse_ippfind_devices(uris)
    assert {dev.uri for dev in devices} == {
        "ipp://printer.local./ipp/print",
        "ipps://secure.local:631/ipp/print",
    }
    assert all(dev.scheme in {"ipp", "ipps"} for dev in devices)
    many = "\n".join(f"ipp://printer{i}.local/ipp/print" for i in range(400))
    assert len(parse_ippfind_devices(many)) == MAX_DISCOVERED_DEVICES


def test_dnssd_results_are_supplemented_by_bounded_ippfind_not_range_scan():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        if command == ["lpinfo", "-v"]:
            return CompletedProcess(command, 0, "network dnssd://Samsung%20M203x._ipp._tcp.local/\n", "")
        if command[0] == "/usr/bin/ippfind":
            return CompletedProcess(command, 0, "ipp://printer.local/ipp/print\n", "")
        raise AssertionError(command)

    devices = DiscoveryService(runner=runner, which=lambda _: "/usr/bin/ippfind").discover()
    assert {d.scheme for d in devices} == {"dnssd", "ipp"}
    assert any(d.uri == "ipp://printer.local/ipp/print" for d in devices)
    assert calls[0][0] == ["lpinfo", "-v"]
    assert calls[1] == (
        ["/usr/bin/ippfind", "-T", "2", "_ipp._tcp", "_ipps._tcp", "--print"],
        {"capture_output": True, "text": True, "check": False, "timeout": 7},
    )


def test_existing_direct_ipp_uri_skips_duplicate_discovery():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, "network ipp://printer.local/ipp/print\n", "")

    devices = DiscoveryService(runner=runner, which=lambda _: "/usr/bin/ippfind").discover()
    assert len(devices) == 1 and devices[0].scheme == "ipp"
    assert calls == [["lpinfo", "-v"]]


def test_mixed_direct_ipp_and_dnssd_still_resolves_other_printers():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command == ["lpinfo", "-v"]:
            return CompletedProcess(command, 0, (
                "network ipp://first.local/ipp/print\n"
                "network dnssd://Second._ipp._tcp.local/\n"
            ), "")
        return CompletedProcess(command, 0, (
            "ipp://first.local/ipp/print\n"
            "ipps://second.local/ipp/print\n"
        ), "")

    devices = DiscoveryService(runner=runner, which=lambda _: "ippfind").discover()
    assert {item.uri for item in devices} == {
        "ipp://first.local/ipp/print",
        "dnssd://Second._ipp._tcp.local/",
        "ipps://second.local/ipp/print",
    }
    assert calls == [
        ["lpinfo", "-v"],
        ["ippfind", "-T", "2", "_ipp._tcp", "_ipps._tcp", "--print"],
    ]


def test_missing_optional_discovery_tool_keeps_cups_results():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, "network dnssd://Samsung._ipp._tcp.local/\n", "")

    devices = DiscoveryService(runner=runner, which=lambda _: None).discover()
    assert len(devices) == 1 and devices[0].scheme == "dnssd"
    assert calls == [["lpinfo", "-v"]]


def test_ippfind_can_recover_from_cups_permission_failure():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command == ["lpinfo", "-v"]:
            return CompletedProcess(command, 1, "", "Forbidden")
        return CompletedProcess(command, 0, "ipps://printer.local/ipp/print\n", "")

    devices = DiscoveryService(runner=runner, which=lambda _: "ippfind").discover()
    assert len(devices) == 1 and devices[0].scheme == "ipps"
    assert len(calls) == 2


def test_cups_failure_without_fallback_does_not_claim_no_printers():
    def runner(command, **kwargs):
        return CompletedProcess(command, 1, "", "CUPS: Forbidden")

    service = DiscoveryService(runner=runner, which=lambda _: "ippfind")
    with pytest.raises(PrinterRegistrationError, match="Forbidden"):
        service.discover()


def test_resolved_ipp_is_not_dropped_when_cups_results_hit_limit():
    cups = "".join(
        f"network dnssd://Printer{i}._ipp._tcp.local/\n"
        for i in range(MAX_DISCOVERED_DEVICES)
    )

    def runner(command, **kwargs):
        if command == ["lpinfo", "-v"]:
            return CompletedProcess(command, 0, cups, "")
        return CompletedProcess(command, 0, "ipp://resolved.local/ipp/print\n", "")

    devices = DiscoveryService(runner=runner, which=lambda _: "ippfind").discover()
    assert len(devices) == MAX_DISCOVERED_DEVICES
    assert devices[0].uri == "ipp://resolved.local/ipp/print"
