# 프린터 지원 범위 및 우선 안내 모델

> 이 문서는 **ChromeOS Linux(Crostini) 앱의 프린터 호환성 정책**을 설명합니다.
> 목록은 앱에서 집중적으로 안내할 모델이지, 이 앱으로 실제 종이 출력까지
> 검증한 모델 목록이 아닙니다. 외부 인증, 배포판 패키지 지원 보고, 제조사
> 다운로드 제공과 **우리 앱에서의 실기기 테스트 완료**는 서로 다른 개념입니다.

## 지원 정책 요약

| 범주 | 앱에서 하는 일 | 보장하지 않는 것 |
|---|---|---|
| 우선 안내 모델 | 정확한 모델명이 감지되면 공식 근거·설치/연결 경로를 더 명확히 보여줌 | Crostini에서의 실물 출력 성공 |
| IPP Everywhere 대상 | IPP/IPPS 속성 조회 후 가능한 경우 드라이버리스 연결 제안 | IPP 인증·실제 연결 성공을 IPP 속성 없이 단정 |
| CUPS 설치 드라이버 대상 | `lpinfo -m`으로 설치된 모델을 읽고 정확히 일치할 때만 후보 추천 | 근접 모델명으로 드라이버 호환성 추정 |
| 목록에 없는 제조사·모델 | 네트워크 검색, IP 수동 입력, IPP 조사, CUPS 모델 추천, PPD 수동 선택 제공 | 공식 드라이버 자동 다운로드/모든 모델 보장 |

검색 자체는 **제조사 및 우선 안내 목록으로 제한되지 않습니다.**
드라이버 패키지 자동 설치 역시 일부 근거가 확인된 경우에만 가능하며,
모든 제조사의 드라이버를 자동 다운로드하거나 설치하지 않습니다.

## 우선 안내 모델 (5개 제조사 · 7개 모델)

| 제조사 | 정확한 모델 | 우선 경로 | 외부 근거 | 현재 앱 검증 수준 |
|---|---|---|---|---|
| Samsung | **SL-M2030W** | 제조사 Linux 드라이버 공식 지원 페이지 안내 | [Samsung SL-M2030W 지원](https://www.samsung.com/sec/support/model/SL-M2030W/) | 공식 자료 확인, 실물 출력 미검증 |
| Brother | **HL-L2340D series** | `printer-driver-brlaser` 패키지 후보 확인 | [Debian brlaser 지원 모델](https://packages.debian.org/bookworm/printer-driver-brlaser) | 패키지 지원 보고, 실물 출력 미검증 |
| Brother | **DCP-L2540DW** | `printer-driver-brlaser` 패키지 후보 확인 | [Debian brlaser 지원 모델](https://packages.debian.org/bookworm/printer-driver-brlaser) | 패키지 지원 보고, 실물 출력 미검증 |
| Brother | **MFC-L2710DW** | `printer-driver-brlaser` 패키지 후보 확인 | [Debian brlaser 지원 모델](https://packages.debian.org/bookworm/printer-driver-brlaser) | 패키지 지원 보고, 실물 출력 미검증 |
| HP | **LaserJet Pro M404dw** | IPP Everywhere 연결 우선 확인 | [PWG 인증 프린터 목록](https://www.pwg.org/printers/) | 외부 IPP 인증 목록 등재, Crostini 출력 미검증 |
| Canon | **imageCLASS MF662Cdw** | IPP Everywhere 연결 우선 확인 | [PWG 인증 프린터 목록](https://www.pwg.org/printers/) | 외부 IPP 인증 목록 등재, Crostini 출력 미검증 |
| Epson | **EM-C7100** | IPP Everywhere 연결 우선 확인 | [PWG 인증 프린터 목록](https://www.pwg.org/printers/) | 외부 IPP 인증 목록 등재, Crostini 출력 미검증 |

**주의:** 정식 모델명과 비슷하더라도 `M2030`과 `M2030W`, `HL-L2340D`와
`HL-L2340DW` 같은 이름을 동일 모델로 취급하지 않습니다. 프린터 검색
서비스의 이름만 일치하면 **미검증**으로 표시합니다. 프린터가 실제로
보고한 IPP 모델명이 정확히 맞으면 이를 구분하여 안내합니다.

### Samsung 계열

- SL-M2030W는 삼성 공식 사이트에서 Linux용 드라이버 설치 경로를 안내합니다.
- 일부 모델은 `socket://…:9100`으로 보일 수 있으며, 이 경우 IPP Everywhere
  지원 여부가 확인되지 않았으면 설치된 호환 PPD를 직접 선택해야 할 수 있습니다.
- `Samsung M203x Series` 같은 넓은 범위의 서비스명은 SL-M2030W로 **자동 확정하지 않습니다**.
- 제조사 설치 스크립트는 앱이 자동 다운로드하거나 실행하지 않습니다.

### Brother 계열

- 위 세 모델은 Debian 패키지 설명에 지원 보고 모델로 등재되어 있습니다.
- 단, 실제 프린터의 **IPP 응답**에서 정확한 모델이 확인되고 배포판
  `apt-cache policy`에서도 설치 가능한 패키지가 있을 때만 **설치 승인 버튼**을 제공합니다.
- Socket/mDNS에서 이름만 감지되면 공식 근거를 안내하되 **자동 설치하지 않습니다**.
- 설치는 사용자의 확인 이후 실행하며 CUPS 큐 등록과 실제 인쇄는 별도입니다.

### HP · Canon · Epson 계열

- 위 세 모델은 Printer Working Group(PWG)의 IPP Everywhere 인증 목록을 근거로 선정했습니다.
- 앱은 모델만 보고 무조건 드라이버리스 설치를 선택하지 않습니다.
  실제 연결의 IPP 기능을 조회해 지원 수준을 확인합니다.
- 프린터가 IPP를 제공하지 않거나 Crostini에서 검색되지 않으면 연결 환경
  및 제조사 지원 안내를 먼저 확인해야 합니다.

## 그 밖의 프린터: 기존 정책 유지

1. CUPS/mDNS 네트워크 검색 또는 IPv4 직접 입력으로 프린터를 선택합니다.
2. IPP/IPPS 주소인 경우 읽기 전용 `Get-Printer-Attributes`로 모델/지원 형식을 확인합니다.
3. IPP Everywhere 기능이 확인되거나 후보 조건을 충족하면 드라이버리스 연결을 제안합니다.
4. 아니면 `lpinfo -m`에서 이미 설치된 CUPS 모델을 비교합니다.
5. 호환이 확인되지 않으면 제조사 공식 지원 페이지나 사용자가 보유한 PPD를 안내합니다.
6. **새 프린터 큐 등록은 반드시 사용자가 승인**해야 합니다. 자동으로 인쇄하거나 시스템 패키지를 설치하지 않습니다.

## 검증 상태 및 추가 기준

- 외부 인증/패키지 지원 목록은 수시로 변동될 수 있으며, 드라이버 사용 가능성과
  **ChromeOS의 Crostini USB·네트워크 노출 상태**에 따라 실제 연결이 달라질 수 있습니다.
- 테스트 완료로 분류하려면 실제 Chromebook에서 **기기 검색, 모델 식별,
  드라이버 적용, 등록, PDF 인쇄 결과**를 확인한 기록이 필요합니다.
  현재 위 우선 안내 모델은 모두 실기기 출력 확인 기록이 없습니다.
- 새 모델을 추가할 때는 `src/printer_supporter/support_catalog.py`의
  `FOCUS_PRINTERS`에 공식 근거/정확한 모델명/연결 경로를 남기고 테스트합니다.
- 모델명 일치나 안내 목록 등록으로 IPP 검증 로직, 패키지 설치 승인,
  프린터 등록 승인 제한을 우회하지 않습니다.

## 공식 참고 자료

- [Printer Working Group — IPP Everywhere 인증 프린터](https://www.pwg.org/printers/)
- [Debian — printer-driver-brlaser 패키지 설명](https://packages.debian.org/bookworm/printer-driver-brlaser)
- [Samsung — SL-M2030W 공식 지원](https://www.samsung.com/sec/support/model/SL-M2030W/)
- [HP 프린터 지원](https://support.hp.com/us-en/drivers/printers)
- [Canon 지원](https://global.canon/en/support/)
- [Epson Korea 지원](https://www.epson.co.kr/sl/s)
- [Brother Korea 지원](https://www.brother-korea.com/ko-kr/support)
