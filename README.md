# ChromeOS Printer Supporter

Chromebook의 Linux 환경에서 프린터를 연결하고 문서를 인쇄하는 앱입니다.

## 설치

먼저 Chromebook에서 **설정 → 개발자 → Linux 개발 환경**을 켜 주세요.

1. [Releases](https://github.com/MiSo-13/chromeOS-printer-supporter/releases)에서 설치 파일을 내려받습니다.
   - Intel/AMD Chromebook: `chromeos-printer-supporter_0.1.0_amd64.deb`
   - ARM Chromebook: `chromeos-printer-supporter_0.1.0_arm64.deb`
   - 잘 모르겠다면 Linux 터미널에서 `dpkg --print-architecture`로 확인할 수 있습니다.
2. **파일 앱 → 다운로드**에서 받은 파일을 **Linux 파일** 폴더로 복사합니다.
3. **터미널 → Penguin**을 열어 설치합니다. Intel/AMD 기준 명령어입니다.

   ```bash
   sudo apt update
   sudo apt install ./chromeos-printer-supporter_0.1.0_amd64.deb
   ```

   ARM 기기는 파일명의 `amd64`를 `arm64`로 바꿔 입력하세요. 새 버전을 받았다면 파일명에 맞게 버전도 변경하면 됩니다.
4. 설치가 끝나면 앱 런처의 **Linux 앱 → ChromeOS 프린터 지원**에서 실행합니다.

ChromeOS의 파일 앱에서는 `.deb` 파일을 직접 설치할 수 없는 버전이 있습니다. **처음 설치할 때만 터미널을 사용**하며, 이후에는 아이콘으로 실행할 수 있습니다.

## 인쇄하기

1. **문서 인쇄**에서 프린터를 고릅니다.
2. **파일 → 문서 열기**(`Ctrl+O`)로 문서를 선택합니다. 파일을 끌어놓거나 `Ctrl+V`로 경로를 붙여넣어도 됩니다.
3. 미리보기와 인쇄 매수 등을 확인한 후 **인쇄**를 누릅니다.
4. **인쇄 대기열**에서 진행 상태를 확인합니다.

프린터가 목록에 없다면 [프린터 연결 방법](docs/PRINTER_SETUP.md)을 참고하세요.

**파일 형식:** PDF, TXT, PNG/JPEG/GIF/TIFF, Word, Excel, PowerPoint, ODF, RTF

Office 문서의 미리보기와 인쇄에는 **LibreOffice**가 필요합니다.

## 프린터 호환성

특정 제조사 전용 앱이 아닙니다. 프린터를 선택하면 **IPP Everywhere → 설치된 CUPS 드라이버 → Debian/Ubuntu 드라이버 패키지 → 제조사 지원 페이지** 순서로 확인합니다.

호환 패키지가 발견되면 **실행할 명령과 출처를 먼저 보여주고**, 승인 후 다운로드·설치합니다. Brother, Samsung, Xerox, HP, Epson, Canon 등 여러 제조사 모델을 대상으로 하며, **목록에 없는 프린터도** IPP/CUPS로 연결할 수 있습니다.

**Samsung SL-M2030W**는 x86_64에서 공식 Linux 파일을 SHA-256으로 검증해 승인 후 설치합니다. ARM은 지원되지 않습니다. 호환 패키지를 찾지 못하면 가지고 있는 PPD 파일을 직접 지정할 수도 있습니다. 프린터별 실제 인쇄 가능 여부는 다릅니다. [드라이버 탐색 범위](docs/SUPPORTED_PRINTERS.md)를 참고하세요.

## 자주 묻는 문제

- **프린터가 안 보여요:** **프린터 추가 → 프린터 검색**을 누르세요. 검색되지 않으면 화면의 **프린터가 안 보여요**에서 모델·IP 주소 찾는 법을 확인한 뒤 IP 주소로 연결해 보세요. ChromeOS에 등록된 프린터가 Crostini에서 반드시 검색되는 것은 아닙니다.
- **인쇄가 안 돼요:** 앱의 **프린터 상태**와 **인쇄 대기열**에서 오류를 확인하세요. 드라이버 설치나 등록이 실패하면 **연결 문제 해결**에서 다시 조회하거나 IPP·CUPS·PPD 중 확인된 방식으로 바꿀 수 있습니다. 별도 펌웨어가 필요한 프린터도 있습니다.
- **Office 문서가 안 열려요:** LibreOffice가 설치돼 있는지 확인하세요.
- **설정 파일이 없어요:** `설정 → 화면 테마`에서 테마를 변경하면 `~/.config/chromeos-printer-supporter/settings.json`이 생성됩니다. 설치 직후에는 없을 수 있습니다.

앱을 제거하려면 Linux 터미널에서 `sudo apt remove chromeos-printer-supporter`를 실행하세요.

개발·배포 절차는 [릴리즈 안내](docs/RELEASE.md)에 정리했습니다.
