# 지원 프린터 안내

프린터 검색은 **제조사나 모델에 제한되지 않습니다.** 아래 모델은 공식 자료를 바탕으로 연결 방법을 우선 안내합니다. **모두 앱에서의 실물 출력 미검증 상태**이며, 연결 성공을 보장하지 않습니다.

| 제조사 | 모델 | 권장 확인 경로 |
|---|---|---|
| Samsung | SL-M2030W | [Samsung 공식 Linux 드라이버 지원](https://www.samsung.com/sec/support/model/SL-M2030W/) |
| Brother | HL-L2340D series | [Debian brlaser 패키지](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| Brother | DCP-L2540DW | [Debian brlaser 패키지](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| Brother | MFC-L2710DW | [Debian brlaser 패키지](https://packages.debian.org/bookworm/printer-driver-brlaser) |
| HP | LaserJet Pro M404dw | [PWG IPP Everywhere 인증 목록](https://www.pwg.org/printers/) |
| Canon | imageCLASS MF662Cdw | [PWG IPP Everywhere 인증 목록](https://www.pwg.org/printers/) |
| Epson | EM-C7100 | [PWG IPP Everywhere 인증 목록](https://www.pwg.org/printers/) |

### 드라이버 정책

- **IPP Everywhere:** 프린터가 직접 보고한 지원 정보를 우선 사용합니다.
- **설치된 드라이버:** 현재 CUPS 목록에서 모델이 일치하는 후보를 제안합니다.
- **Brother brlaser:** 정확한 IPP 모델 응답과 설치 가능한 배포판 패키지가 확인되면 승인 후 설치할 수 있습니다.
- **제조사 드라이버:** 공식 지원 페이지를 안내합니다. 파일 다운로드나 제조사 설치 스크립트 실행은 자동화하지 않습니다.
- **목록에 없는 모델:** 동일한 IPP/CUPS 검색과 수동 PPD 선택을 이용합니다. 비슷한 모델명을 근거로 자동 설치하지 않습니다.

패키지 설치와 CUPS 등록은 각각 사용자 승인 후 실행됩니다. 실제 Chromebook에서 테스트한 모델은 검증 기록이 생긴 뒤 별도로 표시할 예정입니다.
