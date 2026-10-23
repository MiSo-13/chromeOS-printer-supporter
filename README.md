# ChromeOS Printer Supporter

ChromeOS **Linux 개발 환경(Crostini)**에서 문서를 인쇄하고 CUPS 프린터를 관리하는 앱입니다. ChromeOS 브라우저의 인쇄 메뉴(Ctrl+P)를 대체하지는 않습니다.

## 설치

Chromebook에서 **설정 → 개발자 → Linux 개발 환경**을 활성화하세요.

1. [최신 릴리즈](https://github.com/MiSo-13/chromeOS-printer-supporter/releases)에서 Chromebook CPU에 맞는 `.deb` 파일을 받습니다.
   - Intel/AMD Chromebook: `amd64.deb`
   - ARM Chromebook: `arm64.deb`
2. ChromeOS **파일 앱**에서 다운로드한 `.deb` 파일을 열어 **Linux에 설치**합니다.
3. 앱 런처의 **Linux 앱 → ChromeOS 프린터 지원**을 선택합니다. **Python이나 터미널을 실행할 필요가 없습니다.**

Crostini(Debian 12 이상 호환 환경)가 필요하며 ChromeOS 자체 앱은 아닙니다. LibreOffice는 Office 미리보기·인쇄 시 필요할 수 있습니다.

개발용 소스 설치는 `bash install.sh` 후 `.venv/bin/chromeos-printer-supporter`를 실행하세요.

## 사용 방법

1. **프린터 선택:** 이미 등록된 프린터를 선택하거나 **프린터 추가**에서 검색합니다. 검색되지 않으면 IP 주소를 직접 입력하세요.
2. **문서 선택:** **파일 → 문서 열기**(`Ctrl+O`), 드래그 앤 드롭 또는 파일 복사 후 `Ctrl+V`를 사용합니다.
3. **미리보기·설정:** 페이지, 인쇄 매수, 용지 등 필요한 항목을 확인합니다.
4. **인쇄:** **인쇄**를 누르면 접수 상태가 표시됩니다. 진행 상황은 **인쇄 대기열**에서 확인할 수 있습니다.

**설정 → 화면 테마**에서 라이트·다크 모드를 변경합니다. 메뉴바는 창 맨 위에 있습니다.

[처음 프린터 연결하기](docs/PRINTER_SETUP.md)

## 지원 문서

- **PDF · TXT · 이미지:** PDF, TXT, PNG, JPG/JPEG, GIF, TIFF
- **Office:** DOC/DOCX, XLS/XLSX, PPT/PPTX, ODT/ODS/ODP, RTF — LibreOffice 필요

미리보기는 인쇄 전에 내용을 확인하는 기능이며 원본 문서를 수정하지 않습니다. Chromebook에서 파일 드롭/복사가 되지 않으면 **문서 선택** 버튼을 사용하세요.

## 프린터 호환성

IPP Everywhere를 우선 확인하고, 필요한 경우 설치된 CUPS 드라이버 또는 PPD 파일을 사용합니다. 프린터 등록과 패키지 설치 전에는 **실행할 작업을 표시하고 승인을 받습니다.** 안내 내용은 복사할 수 있습니다.

우선 안내 모델은 다음과 같으며 **이 앱에서 실물 출력까지 검증했다는 뜻은 아닙니다.**

| 제조사 | 우선 안내 모델 |
|---|---|
| Samsung | SL-M2030W |
| Brother | HL-L2340D series, DCP-L2540DW, MFC-L2710DW |
| HP | LaserJet Pro M404dw |
| Canon | imageCLASS MF662Cdw |
| Epson | EM-C7100 |

**목록에 없는 프린터도** IPP/CUPS 검색과 수동 드라이버 선택을 이용할 수 있습니다.

[지원 모델 및 드라이버 안내](docs/SUPPORTED_PRINTERS.md)

## 문제 해결

- 프린터가 검색되지 않음: 프린터 IP로 직접 추가하거나 Crostini의 네트워크·CUPS 연결을 확인하세요.
- Office 미리보기가 안 됨: LibreOffice 설치 여부를 확인하세요.
- 드라이버가 없음: 프린터 추가 화면의 공식 제조사 지원 링크나 PPD 파일을 이용하세요.
- 인쇄가 안 됨: **프린터 상태**와 **인쇄 대기열**에서 오류를 확인하세요.

개발 테스트: `python -m pip install -e '.[test]'` 다음 `pytest -q`
