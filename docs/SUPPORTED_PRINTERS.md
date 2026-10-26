# 프린터 호환성

특정 제조사 전용 앱이 아닙니다. IPP Everywhere나 설치된 CUPS 드라이버가 있으면 추가 설치 없이 연결할 수 있습니다.

## 드라이버 자동 탐색

필요한 경우 Debian/Ubuntu APT 저장소에서 다음 드라이버 패키지를 확인합니다. **모델 지원 자료와 실제 IPP 모델명이 정확히 일치한 경우에만** 설치를 제안합니다.

| 패키지 | 대상 제조사 예시 | 지원 모델 자료 |
|---|---|---|
| `printer-driver-brlaser` | Brother | [Debian](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| `printer-driver-splix` | Samsung, Xerox, Dell, Lexmark | [OpenPrinting SpliX](https://openprinting.github.io/splix/) |
| `printer-driver-foo2zjs` | HP, Minolta | [Debian](https://packages.debian.org/bookworm/printer-driver-foo2zjs) |
| `printer-driver-gutenprint` | Epson, Canon | [Gutenprint](https://gimp-print.sourceforge.io/p_Supported_Printers.php) |

이 목록은 지원 제조사를 제한하는 목록이 아닙니다. 앱은 이외의 프린터도 IPP/CUPS로 검색하고 등록할 수 있습니다. 모델별 설치 후보는 [앱의 패키지 목록](../src/printer_supporter/driver_package_catalog.py)에 기록되어 있습니다.

**다운로드는 자동으로 시작하지 않습니다.** 모델과 APT 패키지를 찾으면 먼저 설치 내용을 보여주고, 사용자가 승인했을 때 패키지를 다운로드·설치합니다. 설치 후에도 CUPS에서 실제 모델이 확인돼야 사용할 수 있습니다.

## Samsung SL-M2030W

[삼성 공식 지원 페이지](https://www.samsung.com/sec/support/model/SL-M2030W/)에 Linux 드라이버가 있습니다. 다만 SpliX에서 이 모델의 정확한 호환성은 확인되지 않았습니다. 현재 앱은 공식 페이지를 안내하며 **삼성 제공 ZIP 파일의 자동 설치는 지원하지 않습니다.**

## 프린터 추가 시 알아둘 점

- IPP Everywhere를 지원하면 별도 드라이버 다운로드가 필요하지 않습니다.
- CUPS에 이미 호환 드라이버가 있으면 이를 우선 사용합니다.
- 모델명을 확인할 수 없거나 패키지가 없으면 **PPD 파일 선택**으로 직접 설정할 수 있습니다.
- 설치와 프린터 등록은 각각 사용자의 승인을 받습니다.

[프린터 연결 방법](PRINTER_SETUP.md)
