"""프린터 식별은 읽기 전용 IPP 속성만 사용하고 인쇄하지 않습니다."""
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from printer_supporter.discovery import DiscoveredPrinter
from printer_supporter.identification import (
    IPP_IDENTITY_TEST, identity_from_attributes, identify_printer,
    parse_ipp_attributes, unknown_identity,
)


def device(uri, name="Samsung M203x Series"):
    return DiscoveredPrinter(name, uri, uri.split(":", 1)[0])


def test_ipp_attribute_parser_uses_only_named_capabilities():
    output = """
Read printer identity [PASS]
    printer-make-and-model (textWithoutLanguage) = Samsung M203x Series
    ipp-versions-supported (1setOf keyword) = 1.1,2.0,2.1
    document-format-supported (1setOf mimeMediaType) = application/pdf, image/pwg-raster
    ipp-features-supported (1setOf keyword) = ipp-everywhere
    operation-required (keyword) = Print-Job
"""
    parsed = parse_ipp_attributes(output)
    assert parsed["printer-make-and-model"] == ("Samsung M203x Series",)
    assert parsed["ipp-versions-supported"] == ("1.1", "2.0", "2.1")
    assert "operation-required" not in parsed


def test_ieee1284_device_id_identifies_unlisted_manufacturer_without_download():
    """제조사 하드코딩 없이 IPP의 MFG/MDL만으로 표시 가능한 모델을 식별."""
    printer = device("ipp://printer.local/ipp/print", name="printer.local")
    raw = (
        "printer-device-id (textWithoutLanguage) = "
        "MFG:Zebra Technologies;MDL:ZD421;CMD:ZPL,PDF;SN:private\n"
    )
    parsed = parse_ipp_attributes(raw)
    assert parsed["printer-device-id"] == (
        "MFG:Zebra Technologies;MDL:ZD421;CMD:ZPL,PDF;SN:private",
    )
    identified = identity_from_attributes(printer, parsed)
    assert identified.name == "Zebra Technologies ZD421"
    assert identified.manufacturer == "Zebra Technologies"
    assert identified.model == "ZD421"
    assert identified.source == "IPP 장치 응답"
    assert "private" not in identified.name


def test_make_model_with_vendor_comma_is_not_split():
    parsed = parse_ipp_attributes(
        "printer-make-and-model (textWithoutLanguage) = Acme, Inc. Laser 42\n"
    )
    assert parsed["printer-make-and-model"] == ("Acme, Inc. Laser 42",)


def test_ieee1284_device_id_only_refines_matching_reported_model():
    printer = device("ipp://printer.local/ipp/print", name="Unknown")
    matching = identity_from_attributes(printer, {
        "printer-make-and-model": ("Acme Laser 42",),
        "printer-device-id": ("MANUFACTURER:Acme;MODEL:Laser 42;",),
    })
    assert (matching.manufacturer, matching.model) == ("Acme", "Laser 42")

    conflicting = identity_from_attributes(printer, {
        "printer-make-and-model": ("Acme Laser 42",),
        "printer-device-id": ("MFG:Other;MDL:Ink 99;",),
    })
    assert conflicting.name == "Acme Laser 42"
    assert conflicting.manufacturer is None and conflicting.model is None


def test_device_id_requires_both_bounded_fields():
    printer = device("ipp://printer.local/ipp/print", name="printer.local")
    for raw in ("MFG:Acme;", "MDL:Laser 42;", "MFG:Acme;MDL:bad\x01model;",
                f"MFG:{'x' * 200};MDL:Laser 42;"):
        result = identity_from_attributes(printer, {"printer-device-id": (raw,)})
        assert result.manufacturer is None
        assert result.source != "IPP 장치 응답"


def test_ipp_parser_bounds_large_and_noisy_device_output():
    output = "printer-name (nameWithoutLanguage) = ignored\n" * 512
    output += "printer-device-id (textWithoutLanguage) = MFG:Acme;MDL:Laser 42;\n"
    assert "printer-device-id" not in parse_ipp_attributes(output)
    giant = "printer-device-id (textWithoutLanguage) = " + "X" * 6000
    assert "printer-device-id" not in parse_ipp_attributes(giant)


def test_identify_ipp_reads_model_and_ipp_everywhere_without_printing():
    calls = []
    script_paths = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        script = Path(command[-1])
        script_paths.append(script)
        assert script.is_file()
        assert "OPERATION Get-Printer-Attributes" in script.read_text()
        assert "printer-device-id" in script.read_text()
        assert "Print-Job" not in script.read_text()
        assert "lpadmin" not in script.read_text()
        return CompletedProcess(
            command, 0,
            "printer-make-and-model (textWithoutLanguage) = Samsung M203x Series\n"
            "ipp-versions-supported (1setOf keyword) = 2.0,2.1\n"
            "document-format-supported (1setOf mimeMediaType) = image/pwg-raster,application/pdf\n"
            "ipp-features-supported (1setOf keyword) = ipp-everywhere\n",
            "",
        )

    found = identify_printer(
        device("ipp://192.168.6.147/ipp/print"),
        runner=runner,
        which=lambda name: "/usr/bin/ipptool" if name == "ipptool" else None,
    )
    assert found.name == "Samsung M203x Series"
    assert found.manufacturer == "Samsung"
    assert found.model == "M203x Series"
    assert found.source == "IPP 장치 응답"
    assert found.driverless == "reported"
    assert found.document_formats == ("image/pwg-raster", "application/pdf")
    assert calls[0][0][:5] == ["/usr/bin/ipptool", "-t", "-v", "-T", "5"]
    assert calls[0][0][5] == "ipp://192.168.6.147/ipp/print"
    assert calls[0][1]["timeout"] == 12
    assert calls[0][1]["check"] is False
    assert len(script_paths) == 1 and not script_paths[0].exists()


def test_driverless_candidate_not_certification():
    ipp = device("ipps://printer.local/ipp/print", name="Printer")
    result = identity_from_attributes(ipp, {
        "printer-make-and-model": ("Canon ABC-100",),
        "ipp-versions-supported": ("2.1",),
        "document-format-supported": ("image/pwg-raster", "application/pdf"),
    })
    assert result.manufacturer == "Canon"
    assert result.driverless == "candidate"
    assert "보장하지 않습니다" in result.recommendation


@pytest.mark.parametrize("attrs", [
    {},
    {"ipp-versions-supported": ("1.1",), "document-format-supported": ("image/pwg-raster",)},
    {"ipp-versions-supported": ("2.0",), "document-format-supported": ("application/pdf",)},
])
def test_do_not_guess_driverless_from_scheme_or_pdf(attrs):
    result = identity_from_attributes(device("ipp://printer.local/ipp/print"), attrs)
    assert result.driverless == "unknown"


@pytest.mark.parametrize("uri", [
    "socket://192.168.6.147:9100",
    "dnssd://Samsung%20M203x._ipp._tcp.local/",
    "file:///tmp/secret",
])
def test_no_ipptool_for_non_ipp_uris(uri):
    result = identify_printer(
        device(uri), runner=lambda *a, **kw: pytest.fail("네트워크 요청 불가"),
        which=lambda _: pytest.fail("ipptool 조회 불가"),
    )
    assert result.driverless == "unknown"


def test_missing_ipptool_is_actionable_and_no_installation():
    result = identify_printer(
        device("ipp://192.168.6.147/ipp/print", name="192.168.6.147"),
        which=lambda _: None,
        runner=lambda *a, **kw: pytest.fail("실행 불가"),
    )
    assert result.name == "모델 미확인"
    assert "cups-ipp-utils" in result.recommendation
    assert result.manufacturer is None


def test_timeout_and_fail_return_unknown():
    printer = device("ipp://192.168.6.147/ipp/print")
    def timeouts(command, **kwargs):
        raise TimeoutExpired(command, kwargs["timeout"])

    result = identify_printer(printer, which=lambda _: "/usr/bin/ipptool", runner=timeouts)
    assert result.driverless == "unknown"
    assert "시간 초과" in result.recommendation
    fail = identify_printer(
        printer, which=lambda _: "/usr/bin/ipptool",
        runner=lambda command, **kw: CompletedProcess(command, 1, "", "bad"),
    )
    assert fail.driverless == "unknown"


def test_uri_credentials_or_whitespace_not_probed():
    for uri in ("ipp://user:pass@printer.local/ipp/print",
                "ipp://printer.local/ipp/print xyz"):
        result = identify_printer(
            device(uri), which=lambda _: pytest.fail("조회 불가"),
            runner=lambda *a, **kw: pytest.fail("실행 불가"),
        )
        assert result.driverless == "unknown"
