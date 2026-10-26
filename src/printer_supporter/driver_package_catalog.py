"""드라이버 제공 자료로 확인된 모델별 배포판 패키지 후보.

지원 목록은 정확한 모델명만 포함합니다. 유사 번호/접미사 추정은 하지 않습니다.
APT 후보는 제조사의 독점 설치 파일이 아니라 Debian/Ubuntu 저장소 패키지입니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from .identification import PrinterIdentity

BRLASER_SOURCE = "https://packages.debian.org/bookworm/printer-driver-brlaser"
SPLIX_SOURCE = "https://openprinting.github.io/splix/"
FOO2ZJS_SOURCE = "https://packages.debian.org/bookworm/printer-driver-foo2zjs"
GUTENPRINT_SOURCE = "https://gimp-print.sourceforge.io/p_Supported_Printers.php"

# 공식 Debian 패키지 설명에 등재된 Brother 모델.
BROTHER_BR_LASER = frozenset({
    "DCP-1510", "DCP-1602", "DCP-7030", "DCP-7040", "DCP-7055",
    "DCP-7055W", "DCP-7060D", "DCP-7065DN", "DCP-7080",
    "DCP-L2500D", "DCP-L2540DW", "DCP-L2710DW",
    "HL-1110 SERIES", "HL-1200 SERIES", "HL-L2300D SERIES",
    "HL-L2320D SERIES", "HL-L2340D SERIES", "HL-L2360D SERIES",
    "MFC-1910W", "MFC-7240", "MFC-7360N", "MFC-7365DN",
    "MFC-7840W", "MFC-L2710DW",
})

# OpenPrinting/SpliX에 실제 모델이 명시된 항목(패키지 버전에 따라 다를 수 있음).
SPLIX_MODELS = {
    "Samsung": frozenset({
        "SCX-4100", "SCX-4200", "SCX-4300", "SCX-4500", "SCX-4521F",
        "ML-1510", "ML-1520", "ML-1610", "ML-1710", "ML-1740",
        "ML-1750", "ML-2571", "ML-2250", "ML-2251", "ML-3471ND",
        "ML-3560", "ML-2150", "ML-2550", "ML-1630", "ML-1640",
        "ML-2010", "ML-2015", "ML-2240", "ML-2510", "ML-1660",
        "ML-1910", "ML-2525", "ML-2525W", "ML-2580", "ML-2580N",
        "ML-3050", "ML-3051", "ML-3310", "ML-2160", "ML-2165",
        "ML-1860", "ML-1670", "ML-1865", "SCX-3200", "SCX-3400",
        "SCX-4600", "M2020 SERIES", "M2070 SERIES",
        "M262X 282X SERIES", "M267X 287X SERIES", "M283X SERIES",
        "CLP-500", "CLP-550", "CLP-510", "CLP-200", "CLP-600",
        "CLP-300", "CLP-310", "CLP-315", "CLP-310N",
        "CLX-2170", "CLX-216X", "CLX-3160",
    }),
    "Xerox": frozenset({
        "PHASER 3115", "PHASER 3116", "PHASER 3120", "PHASER 3121",
        "PHASER 3130", "PHASER 3420", "PHASER 3425", "PHASER 5500",
        "PHASER 3150", "PHASER 3160", "PHASER 3117", "PHASER 3122",
        "PHASER 3124", "PHASER 3140", "PHASER 3155", "PHASER 3020",
        "PHASER 3052", "PHASER 3260", "WORKCENTRE 3025",
        "WORKCENTRE 3215", "WORKCENTRE 3225", "PHASER 6100",
        "PHASER 6110",
    }),
    "Dell": frozenset({"1100", "1110"}),
    "Lexmark": frozenset({"X215 MFP"}),
}
# Debian foo2zjs 패키지 설명에서 모델이 구체적으로 언급된 항목.
FOO2ZJS_MODELS = {
    "HP": frozenset({
        "LASERJET 1000", "LASERJET 1005", "LASERJET 1018",
        "LASERJET 1020", "LASERJET 1022",
    }),
    "Minolta": frozenset({
        "MAGICOLOR 2200 DL", "MAGICOLOR 2300 DL", "MAGICOLOR 2430 DL",
    }),
}
# Gutenprint 공개 모델 목록에서 experimental/untested가 아닌 모델을 선정.
GUTENPRINT_MODELS = {
    "Epson": frozenset({
        "STYLUS PHOTO R200", "STYLUS PHOTO R210", "STYLUS PHOTO R220",
        "STYLUS PHOTO R230", "STYLUS PHOTO R260", "STYLUS PHOTO R270",
        "STYLUS PHOTO R280", "STYLUS PHOTO R285", "STYLUS PHOTO R300",
        "STYLUS PHOTO R310", "STYLUS PHOTO R320", "STYLUS PHOTO R340",
        "STYLUS PHOTO R360", "STYLUS PHOTO R380", "STYLUS PHOTO R390",
        "STYLUS PHOTO R800", "STYLUS PHOTO R1800", "STYLUS PHOTO R1900",
    }),
    "Canon": frozenset({
        "PIXMA IP4000", "PIXMA IP4000R",
    }),
}


@dataclass(frozen=True)
class DistroDriver:
    package: str
    source_url: str
    evidence: str
    verified_model: bool = True


def _clean(text: str) -> str:
    return " ".join(text.upper().strip().replace("_", "-").split())


def distro_package_for(identity: PrinterIdentity) -> DistroDriver | None:
    """장치에서 직접 확인된 제조사+모델에 대해 근거 있는 APT 후보만 반환."""
    if identity.source != "IPP 장치 응답":
        return None
    if not identity.manufacturer or not identity.model:
        return None
    brand = identity.manufacturer.strip().casefold()
    model = _clean(identity.model)
    # IPP 장치가 보고한 이름과 분리된 브랜드/모델이 서로 일치해야 합니다.
    if _clean(identity.name) != _clean(f"{identity.manufacturer} {identity.model}"):
        return None
    if brand == "brother" and model in BROTHER_BR_LASER:
        return DistroDriver("printer-driver-brlaser", BRLASER_SOURCE, "Debian 지원 모델")
    for mapping, package, source, evidence in (
        (SPLIX_MODELS, "printer-driver-splix", SPLIX_SOURCE, "OpenPrinting SpliX 모델 목록"),
        (FOO2ZJS_MODELS, "printer-driver-foo2zjs", FOO2ZJS_SOURCE, "Debian foo2zjs 모델 목록"),
        (GUTENPRINT_MODELS, "printer-driver-gutenprint", GUTENPRINT_SOURCE, "Gutenprint 모델 목록"),
    ):
        for vendor, names in mapping.items():
            if brand == vendor.casefold() and model in names:
                return DistroDriver(package, source, evidence)
    return None


# SL-M2030W는 제조사에서 Linux ZIP 파일을 제공하지만,
# SpliX의 정확한 지원 모델 목록에는 확인되지 않았습니다.
# 모델명이 비슷하다는 이유로 SpliX를 호환 드라이버라고 지정하지 않습니다.
