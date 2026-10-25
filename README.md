# ChromeOS Printer Supporter

ChromeOS **Linux 개발 환경(Crostini)**에서 문서를 인쇄하고 CUPS 프린터를 관리하는 앱입니다. ChromeOS 브라우저의 인쇄 메뉴(Ctrl+P)를 대체하지는 않습니다.

## 설치

Chromebook에서 **설정 → 개발자 → Linux 개발 환경**을 활성화하세요.

1. [최신 릴리즈](https://github.com/MiSo-13/chromeOS-printer-supporter/releases)에서 CPU에 맞는 `.deb` 파일을 받습니다. 터미널에서 `dpkg --print-architecture`로 확인할 수 있습니다.
   - Intel/AMD: `chromeos-printer-supporter_0.1.0_amd64.deb`
   - ARM: `chromeos-printer-supporter_0.1.0_arm64.deb`
2. ChromeOS **파일 앱 → 다운로드**에서 설치 파일을 **Linux 파일** 폴더로 복사합니다.
3. **터미널 → Penguin**에서 아래 명령어를 실행합니다(예: Intel/AMD).
   
   ```bash
   sudo apt update
   sudo apt install ./chromeos-printer-supporter_0.1.0_amd64.deb
   ```
   
   ARM Chromebook이면 파일명의 `amd64`를 `arm64`로 바꿉니다.
4. 설치 후 앱 런처의 **Linux 앱 → ChromeOS 프린터 지원**을 누릅니다. **실행할 때 Python이나 터미널을 열 필요는 없습니다.**

ChromeOS 147부터 파일 앱의 Debian 패키지 설치 기능은 지원 중단되었습니다. 처음 설치할 때는 터미널을 사용해야 합니다. [ChromeOS 공식 안내](https://developers.google.com/chromeos/app-development/develop/news)

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

특정 제조사 전용 앱이 아닙니다. **IPP Everywhere, 설치된 CUPS 드라이버, PPD 파일**을 이용해 다양한 네트워크 프린터를 연결할 수 있습니다.

프린터 모델과 Crostini 연결 환경에 따라 실제 사용 가능 여부는 달라집니다. 일부 모델은 드라이버 설치 경로를 추가로 안내하지만, **목록에 없는 프린터도 검색·연결할 수 있습니다.**

프린터 등록과 패키지 설치 전에는 작업 내용을 확인하고 승인해야 합니다.

[프린터 호환성 및 우선 안내 모델](docs/SUPPORTED_PRINTERS.md)

## 문제 해결

- 프린터가 검색되지 않음: 프린터 IP로 직접 추가하거나 Crostini의 네트워크·CUPS 연결을 확인하세요.
- Office 미리보기가 안 됨: LibreOffice 설치 여부를 확인하세요.
- 드라이버가 없음: 프린터 추가 화면의 공식 제조사 지원 링크나 PPD 파일을 이용하세요.
- 인쇄가 안 됨: **프린터 상태**와 **인쇄 대기열**에서 오류를 확인하세요.

개발 테스트: `python -m pip install -e '.[test]'` 다음 `pytest -q`
