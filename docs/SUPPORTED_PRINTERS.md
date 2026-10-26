# 프린터 호환성

**목록에 없는 프린터도** 검색하고 연결할 수 있습니다. IPP Everywhere, 설치된 CUPS 드라이버 또는 PPD 파일을 이용하며, 실제 출력 가능 여부는 프린터와 ChromeOS Linux 환경에 따라 달라집니다.

## 어떤 프린터를 사용할 수 있나요?

- **일반 호환성 확인:** 제조사 제한 없이 프린터를 검색하고 드라이버를 확인할 수 있습니다.
- **우선 안내 모델:** 아래 모델은 연결에 참고할 공식 자료를 앱에서 안내합니다. 실제 인쇄 성공을 보장하는 목록은 아닙니다.
- **실기기 검증 완료:** Chromebook에서 직접 인쇄를 확인한 모델입니다. **현재 공개할 실기기 검증 기록은 없습니다.**

## 우선 안내 모델

| 제조사 | 모델 | 참고 자료 |
|---|---|---|
| Samsung | SL-M2030W | [Samsung 드라이버 지원](https://www.samsung.com/sec/support/model/SL-M2030W/) |
| Brother | HL-L2340D series | [Debian brlaser 드라이버](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| Brother | DCP-L2540DW | [Debian brlaser 드라이버](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| Brother | MFC-L2710DW | [Debian brlaser 드라이버](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| HP | LaserJet Pro M404dw | [IPP Everywhere 인증 모델](https://www.pwg.org/printers/) |
| Canon | imageCLASS MF662Cdw | [IPP Everywhere 인증 모델](https://www.pwg.org/printers/) |
| Epson | EM-C7100 | [IPP Everywhere 인증 모델](https://www.pwg.org/printers/) |

드라이버가 자동으로 선택되지 않으면 **프린터 추가 → 드라이버 선택**에서 설치된 CUPS 모델이나 PPD 파일을 확인하세요. 제조사 프로그램을 자동으로 내려받거나 실행하지는 않습니다.

[프린터 연결 방법](PRINTER_SETUP.md)
