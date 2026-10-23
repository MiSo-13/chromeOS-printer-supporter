"""CUPS lpoptions -l 옵션 파싱 및 기능 매핑 테스트."""

import pytest

from printer_supporter.capabilities import (
    feature_options, parse_printer_options, validate_job_options,
)


def test_samsung_m203x_ppd_options_are_detected():
    output = (
        "PageSize/Media Size: *A4 Letter Legal\n"
        "ColorModel/Color Mode: *Gray\n"
        "Duplex/2-Sided Printing: *None DuplexNoTumble DuplexTumble\n"
        "Resolution/Resolution: *600dpi 1200dpi\n"
        "InputSlot/Media Source: *Auto Tray1\n"
    )
    supported = feature_options(parse_printer_options(output))
    assert supported["paper"].key == "PageSize"
    assert [c.value for c in supported["paper"].choices] == ["A4", "Letter", "Legal"]
    assert supported["paper"].choices[0].default is True
    assert supported["color"].choices[0].value == "Gray"
    assert supported["duplex"].choices[0].value == "None"
    assert supported["resolution"].choices[0].value == "600dpi"
    assert "quality" not in supported


def test_driverless_ipp_style_options_supported():
    output = (
        "media/Media Size: *iso_a4_210x297mm na_letter_8.5x11in\n"
        "print-color-mode/Print Color Mode: *monochrome color\n"
        "sides/2-Sided Printing: *one-sided two-sided-long-edge\n"
        "print-quality/Print Quality: 3 *4 5\n"
        "printer-resolution/Printer Resolution: *300dpi 600dpi\n"
    )
    supported = feature_options(parse_printer_options(output))
    assert len(supported) == 5
    assert supported["color"].choices[1].value == "color"
    assert supported["duplex"].choices[1].value == "two-sided-long-edge"
    assert supported["quality"].choices[1].default is True


def test_invalid_or_unrecognized_lines_are_ignored():
    output = "broken line\n-unsafe/Unsafe: *bad\nPageSize/Size: *A4 A4\n"
    options = parse_printer_options(output)
    assert list(options) == ["PageSize"]
    assert len(options["PageSize"].choices) == 1


@pytest.mark.parametrize("options", [
    {"ColorModel": "--bad"}, {"-o": "foo"}, {"sides": "one-sided;touch"},
])
def test_unsafe_job_options_rejected(options):
    with pytest.raises(ValueError):
        validate_job_options(options)
