# 프린터 호환성

**이 앱은 특정 제조사나 7개 모델에 한정되지 않습니다.** IPP Everywhere 또는 호환되는 CUPS 드라이버·PPD를 사용할 수 있는 네트워크 프린터라면 연결을 시도할 수 있습니다. 실제 인쇄 가능 여부는 모델, 드라이버, Crostini의 장치·네트워크 접근 환경에 따라 달라집니다.

## 호환성 구분

- **일반 호환성 확인:** 목록에 없는 모델도 프린터 검색, IP 직접 입력, IPP 지원 확인, 설치된 CUPS 드라이버 추천 및 PPD 수동 선택을 이용할 수 있습니다.
- **우선 안내 모델:** 아래 7개 모델은 제조사·배포판·IPP 인증 자료를 참고해 연결 경로를 더 구체적으로 안내합니다. 이를 **앱에서 인쇄를 검증했다는 뜻으로 보지 않습니다.**
- **실기기 검증 완료:** Chromebook에서 모델 식별, CUPS 등록, 문서 인쇄까지 직접 확인한 모델을 뜻합니다. **현재 공개할 실기기 검증 기록은 없습니다.**

## 우선 안내 모델

| 제조사 | 모델 | 연결·드라이버 안내 |
|---|---|---|
| Samsung | SL-M2030W | [제조사 Linux 드라이버 안내](https://www.samsung.com/sec/support/model/SL-M2030W/) |
| Brother | HL-L2340D series | [Debian brlaser 패키지](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| Brother | DCP-L2540DW | [Debian brlaser 패키지](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| Brother | MFC-L2710DW | [Debian brlaser 패키지](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| HP | LaserJet Pro M404dw | [PWG IPP Everywhere 목록](https://www.pwg.org/printers/) |
| Canon | imageCLASS MF662Cdw | [PWG IPP Everywhere 목록](https://www.pwg.org/printers/) |
| Epson | EM-C7100 | [PWG IPP Everywhere 목록](https://www.pwg.org/printers/) |

## 드라이버 선택

1. 프린터가 IPP Everywhere를 지원하면 드라이버리스 연결을 우선 시도합니다.
2. 그렇지 않으면 Crostini에 설치된 CUPS 드라이버 중 모델이 일치하는 후보를 안내합니다.
3. 호환 드라이버를 찾지 못하면 제조사 공식 지원 페이지나 사용자가 선택한 PPD 파일을 이용합니다.

**목록에 없는 프린터도 같은 방식으로 진행합니다.** 이름이 비슷하다는 이유만으로 다른 모델의 드라이버를 자동 설치하지 않습니다. 배포판 패키지 설치와 CUPS 등록은 각각 사용자의 승인이 필요합니다.

[프린터 연결 방법](PRINTER_SETUP.md)
