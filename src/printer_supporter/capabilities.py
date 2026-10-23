"""CUPS lpoptions -l 출력으로 프린터별 지원 옵션을 읽습니다."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class OptionChoice:
    value: str
    default: bool = False


@dataclass(frozen=True)
class PrinterOption:
    key: str
    description: str
    choices: tuple[OptionChoice, ...]


# 프린터의 실제 응답에 있는 키 중 우선순위가 높은 옵션만 선택합니다.
FEATURE_KEYS = {
    "paper": ("PageSize", "media", "media-size"),
    "color": ("print-color-mode", "ColorModel", "ColorMode", "OutputMode"),
    "duplex": ("sides", "Duplex"),
    "quality": ("print-quality", "PrintQuality", "Quality"),
    "resolution": ("printer-resolution", "Resolution", "SetResolution"),
}

VALID_TOKEN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]*$")
VALID_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


def parse_printer_options(output: str) -> dict[str, PrinterOption]:
    options = {}
    for line in output.splitlines():
        heading, sep, choices_text = line.partition(":")
        if not sep or not choices_text.strip():
            continue
        key, _, description = heading.strip().partition("/")
        if not VALID_KEY.fullmatch(key):
            continue
        choices = []
        for token in choices_text.split():
            default = token.startswith("*")
            value = token.lstrip("*")
            if VALID_TOKEN.fullmatch(value) and not any(c.value == value for c in choices):
                choices.append(OptionChoice(value, default))
        if choices:
            options[key] = PrinterOption(key, description.strip() or key, tuple(choices))
    return options


def feature_options(options: dict[str, PrinterOption]) -> dict[str, PrinterOption]:
    available = {}
    for feature, candidates in FEATURE_KEYS.items():
        for candidate in candidates:
            found = next((option for key, option in options.items()
                          if key.lower() == candidate.lower()), None)
            if found:
                available[feature] = found
                break
    return available


def validate_job_options(options: dict[str, str]) -> None:
    """명령행 인자에 안전하게 전달할 수 있는 옵션 토큰만 허용합니다."""
    for key, value in options.items():
        if not VALID_KEY.fullmatch(key) or not (
            re.fullmatch(r"[1-9][0-9]*(?:-[1-9][0-9]*)?(?:,[1-9][0-9]*(?:-[1-9][0-9]*)?)*", value)
            if key == "page-ranges" else VALID_TOKEN.fullmatch(value)
        ):
            raise ValueError(f"유효하지 않은 CUPS 옵션입니다: {key}={value}")
