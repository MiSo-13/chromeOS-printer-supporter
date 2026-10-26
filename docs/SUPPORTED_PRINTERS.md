# 프린터 호환성

특정 제조사 전용 앱이 아닙니다. IPP Everywhere나 설치된 CUPS 드라이버가 있으면 추가 설치 없이 연결할 수 있습니다.

앱은 목록에 없는 프린터도 **일반 호환성 확인**을 수행합니다.

## 드라이버 자동 탐색

필요한 경우 Debian/Ubuntu APT 저장소에서 다음 드라이버 패키지를 확인합니다. **모델 지원 자료와 실제 IPP 모델명이 정확히 일치한 경우에만** 설치를 제안합니다.

| 패키지 | 대상 제조사 예시 | 지원 모델 자료 |
|---|---|---|
| `printer-driver-brlaser` | Brother | [Debian](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| `printer-driver-splix` | Samsung, Xerox, Dell, Lexmark | [OpenPrinting SpliX](https://openprinting.github.io/splix/) |
| `printer-driver-foo2zjs` | HP, Minolta | [Debian](https://packages.debian.org/bookworm/printer-driver-foo2zjs) |
| `printer-driver-gutenprint` | Epson, Canon | [Gutenprint](https://gimp-print.sourceforge.io/p_Supported_Printers.php) |

이 목록은 지원 제조사를 제한하는 목록이 아닙니다. 앱은 이외의 프린터도 IPP/CUPS로 검색하고 등록할 수 있습니다. 모델별 설치 후보는 [앱의 패키지 목록](../src/printer_supporter/driver_package_catalog.py)에 기록되어 있습니다.

**다운로드는 자동으로 시작하지 않습니다.** 모델과 APT 패키지를 찾으면 먼저 설치 내용을 보여주고, 승인 후 다운로드·설치합니다. 설치가 끝나면 CUPS 목록에서 모델명을 다시 확인합니다. 일치하지 않거나 후보가 여러 개이면 직접 드라이버를 확인해야 합니다.

**HP LaserJet 1000·1005·1018·1020:** 드라이버 외에 프린터 펌웨어 전송이 필요할 수 있습니다. 앱에서 설치 전에 안내하지만 펌웨어를 자동으로 전송하지는 않습니다. [foo2zjs 설치 문서](https://sources.debian.org/src/foo2zjs/20200505dfsg0-1/INSTALL/)를 참고하세요. ChromeOS Linux에서 USB 연결이 가능한지도 확인해야 합니다.

## Samsung SL-M2030W / M203x Series

[삼성 공식 지원 페이지](https://www.samsung.com/sec/support/model/SL-M2030W/)의 Linux 드라이버 파일을 확인했습니다. **x86_64 Chromebook**에서 IPP 모델명이 `Samsung SL-M2030W` 또는 `Samsung M203x Series`로 확인되면, 사용자가 승인한 뒤 공식 ZIP 다운로드·SHA-256 검증·CUPS 필터 및 PPD 설치를 진행합니다.

삼성 설치 스크립트는 실행하지 않습니다. **ARM Chromebook은 공식 파일에 arm64 필터가 없어 자동 설치가 불가능합니다.** 드라이버 설치 후에도 프린터 등록은 따로 승인해야 하며 실제 인쇄는 별도 확인이 필요합니다.

## 우선 안내 모델

아래 7개는 설치 경로 안내를 우선 제공하는 모델입니다. **실기기 검증 완료**와는 다릅니다. **현재 공개할 실기기 검증 기록은 없습니다.**

| 제조사 | 모델 | 참고 자료 |
|---|---|---|
| Samsung | SL-M2030W | [삼성 공식 지원](https://www.samsung.com/sec/support/model/SL-M2030W/) |
| Brother | HL-L2340D series, DCP-L2540DW, MFC-L2710DW | [Debian brlaser](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| HP | LaserJet Pro M404dw | [PWG IPP Everywhere](https://www.pwg.org/printers/) |
| Canon | imageCLASS MF662Cdw | [PWG IPP Everywhere](https://www.pwg.org/printers/) |
| Epson | EM-C7100 | [PWG IPP Everywhere](https://www.pwg.org/printers/) |

## 프린터 추가 시 알아둘 점

- IPP Everywhere를 지원하면 별도 드라이버 다운로드가 필요하지 않습니다.
- CUPS에 이미 호환 드라이버가 있으면 이를 우선 사용합니다.
- 모델명을 확인할 수 없거나 패키지가 없으면 **PPD 파일 선택**으로 직접 설정할 수 있습니다.
- 설치와 프린터 등록은 각각 사용자의 승인을 받습니다.

[프린터 연결 방법](PRINTER_SETUP.md)
