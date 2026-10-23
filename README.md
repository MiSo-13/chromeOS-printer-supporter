# PrintHub · ChromeOS Printer Supporter

ChromeOS의 Linux(Crostini)에서 실행하는 PyQt6 기반 CUPS 프린터 관리자입니다.
첫 번째 검증 모델은 **Samsung SL-M2030W / Samsung M203x Series**입니다. 특정 모델에 종속되지 않도록 기존 CUPS 큐를 탐색해 사용합니다.

## 제공 기능

- 등록된 CUPS 프린터 조회, 상태 및 오류 내용 표시 (5초마다 갱신)
- PDF, TXT, PNG/JPEG/TIFF/GIF 파일 인쇄
- Word(`.doc`, `.docx`), Excel(`.xls`, `.xlsx`), PowerPoint(`.ppt`, `.pptx`) 및 ODF 문서 인쇄 (LibreOffice로 임시 PDF 변환)
- CUPS `lpoptions -p <프린터> -l` 기반 용지·흑백/컬러·양면·품질·해상도 자동 인식 (지원하는 값만 선택)
- 인쇄 매수 및 선택한 인쇄 옵션을 작업별로 적용
- 선택한 CUPS 프린터로 테스트 페이지 1장 출력 (확인 후 전송, 원본 문서 불필요)
- 현재 CUPS 큐의 진행 중인 작업 및 처리 종료 이력 조회(최대 100건 표시)\n- **내 작업**에 한해 보류·재개·취소 (다른 사용자 작업 및 프린터 전체 대기열은 변경하지 않음)
- 네트워크 프린터 검색(CUPS/mDNS), IP 직접 입력, 연결 확인 및 사용자 승인 후 CUPS 큐 등록
- 원본 문서를 수정하지 않고 작업별 인쇄 옵션 지정

> ChromeOS 브라우저의 Ctrl+P 통합은 지원 범위가 아닙니다. 앱을 실행해 문서를 선택하는 방식입니다.

## Crostini 설치 및 의존성 자동 설치

프로젝트를 받은 뒤 터미널에서 설치 도우미를 실행할 수 있습니다.

```bash
bash install.sh
.venv/bin/chromeos-printer-supporter
```

설치 도우미는 **Python 3 및 Debian/Ubuntu(Crostini)** 환경을 전제로 하며,
누락된 `python3-venv`, `cups`, `cups-client`, PyQt6와 선택적인 LibreOffice 설치를
각 단계에서 사용자에게 확인합니다. 동의 없이는 설치하지 않습니다.
삼성 전용 ULD 등 제조사 드라이버는 자동 다운로드하지 않습니다.

앱을 실행하면 CUPS 명령을 확인하고, 누락 시 패키지명과 실제 설치 명령을 보여줍니다.
메인 화면의 **패키지 점검**에서 선택 의존성도 검사할 수 있습니다.
Word/Excel/PowerPoint 파일 인쇄 시 LibreOffice가 없다면 그때 설치 여부를 물어봅니다.

앱 내부 설치는 `sudo -n apt-get install -y ...`를 사용하므로 Crostini에 암호 없는
sudo 권한이 필요합니다. 권한이 없다면 오류를 표시하며 터미널에서 직접 설치할 수 있습니다.
설치는 **Linux 컨테이너에만** 적용되고 회사 공용 프린터의 하드웨어 설정을 변경하지 않습니다.

### Crostini의 Wayland 연결 오류 대응

WorKing, PDF Helper, Postman Tester에서 사용한 안정화 방식을 적용했습니다.

- ChromeOS Crostini가 감지되고 X11 DISPLAY가 있으면 **PyQt6 로딩 전에** Qt 플랫폼을 `xcb`로 선택합니다.
- Windows, macOS, 일반 Linux와 사용자가 명시한 `QT_QPA_PLATFORM` 설정은 그대로 유지합니다.
- `libqxcb.so` 의존성이 부족하면 Qt 초기화 전에 누락된 라이브러리 및 Debian 설치 명령을 터미널에 표시합니다. 승인 없는 자동 설치는 하지 않습니다.
- 실행 시 터미널에 `QT_PLATFORM_SELECTED platform=xcb`, 정상 종료 시 `APP_EXIT code=0`을 출력합니다. 비정상 네이티브 종료는 Python `faulthandler`가 진단에 도움을 줄 수 있습니다.

터미널에서 인쇄 작업 없이 화면 실행만 검증할 수 있습니다.

```bash
.venv/bin/chromeos-printer-supporter
```

X11 동작 확인 후에도 오류가 지속되면 로그를 복사해 주세요. 디스플레이 설정만 변경하며 CUPS 프린터 설정이나 인쇄 작업은 건드리지 않습니다.

### 수동 설치

먼저 프린터가 CUPS에 등록되어 실제 출력되는지 확인합니다.

```bash
sudo apt update
sudo apt install -y cups cups-client libreoffice python3-venv
lpstat -p -d
```

프로젝트를 받은 폴더에서:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/chromeos-printer-supporter
```

앱을 ChromeOS Linux 앱 런처에 등록하려면 설치된 명령의 절대 경로를 확인한 뒤 `.desktop` 파일의 `Exec`를 해당 경로로 수정하고 `~/.local/share/applications/`에 복사하세요.

## 프린터별 인쇄 옵션

앱의 **문서 인쇄** 탭에서 선택한 프린터의 CUPS/PPD 옵션을 읽습니다. 다음 항목을 지원하는 경우에만 선택할 수 있습니다.

- 용지 크기: 프린터가 보고한 PageSize/media
- 흑백/컬러: print-color-mode, ColorModel 등
- 단면/양면: sides 또는 Duplex
- 품질 및 해상도: 프린터가 보고한 선택 목록

알 수 없는 항목은 **프린터 기본값**으로 두며, 실제 지원 여부를 임의로 추측하지 않습니다.
`lpoptions -l` 조회만 수행하며 사용자/공용 프린터의 기본 설정을 변경하지 않습니다.
선택값은 인쇄할 때 해당 작업의 `lp -o 키=값` 옵션으로 전송됩니다.
드라이버에 따라 일부 기능이 보고되지 않거나, 컬러처럼 하드웨어상 지원되지 않는 옵션이 목록에 없을 수 있습니다.

## 테스트 페이지 출력

**문서 인쇄** 탭에서 프린터와 용지(A4/Letter)를 선택하고 **테스트 페이지 인쇄**를 누르면 확인창이 나타납니다. 승인하면 영문 텍스트 테스트 페이지 한 장을 CUPS에 전송합니다. 새 드라이버 설치나 프린터 기본값 변경은 하지 않습니다. 출력 성공 여부는 실제 종이로 확인해 주세요.

## 프린터 검색 및 등록

앱의 **프린터 추가** 탭에서 다음을 사용할 수 있습니다.

1. **네트워크 프린터 검색**: 버튼을 눌렀을 때만 `lpinfo -v`의 발견 결과를 표시합니다. IP 대역 전체를 스캔하지 않습니다. Crostini에서 `lpinfo: Forbidden` 오류가 발생하면 검색을 건너뛰고 IP를 직접 입력하거나 기존 CUPS 프린터를 사용할 수 있습니다.
2. **IP 직접 입력**: IPv4 주소와 IPP(631) 또는 Socket/JetDirect(9100) 연결 방식 선택
3. **연결 확인**: 직접 연결 가능한 IPP/Socket 주소의 TCP 포트를 확인
4. **드라이버 지정**:
   - IPP 프린터: `IPP Everywhere`(프린터가 지원해야 함)
   - Samsung ULD 등 전용 드라이버: 설치된 `.ppd`를 직접 선택
5. **프린터 등록**: URI·큐 이름·드라이버를 보여주고 동의를 받은 후에만 `sudo -n lpadmin` 실행

기존 CUPS 큐와 동일한 이름은 거부합니다. 새 큐는 공유하지 않도록 등록하고,
기본 프린터는 변경하지 않습니다. 회사 공용 프린터의 자체 설정에도 접근하지 않습니다.
등록에는 Crostini의 sudo 권한이 필요합니다.

> SL-M2030W에서 이전에 확인한 `socket://192.168.6.147:9100` 방식은
> 설치된 Samsung M203x PPD 파일을 선택해야 합니다.
> `IPP Everywhere`는 지원하는 모델에서만 사용하세요.
> 실제 기기에서 네트워크 검색·인쇄를 검증하는 과정은 남아 있습니다.

## 파일 형식과 실행 방식

| 형식 | 처리 |
|---|---|
| PDF, 텍스트, 이미지 | CUPS `lp`로 직접 전송 |
| Office, ODF, RTF | LibreOffice headless로 임시 PDF 변환 후 CUPS 전송 |

문서 변환에 실패하면 인쇄 작업을 전송하지 않습니다. Office 문서의 레이아웃은 LibreOffice 호환성에 영향을 받을 수 있으므로 중요한 문서는 미리 PDF로 확인하는 것이 좋습니다.

## 대기열 및 오류의 한계

- CUPS가 처리하는 작업만 표시됩니다. 다른 Windows PC가 프린터에 직접 전송한 작업은 표시되지 않을 수 있습니다.
- TCP 9100 프린터는 용지 없음·토너 부족 같은 장치 오류가 CUPS에 모두 전달되지 않을 수 있습니다.
- 대기/처리 중 목록은 개별 작업의 실제 인쇄 진행률이나 보류 상태를 구분하지 못합니다.\n- '처리 종료 이력'에는 CUPS가 종료 처리한 작업이 표시되며, 취소·오류도 포함될 수 있어 실제 종이 출력 성공을 보증하지 않습니다. CUPS 서버가 이력을 보존하지 않으면 목록이 비어 있을 수 있습니다.\n- 보류·재개는 CUPS의 개별 작업 명령으로 실행합니다. 이미 처리 완료된 작업 등에는 실패할 수 있고, 이 경우 CUPS 오류를 표시합니다.
- 대기열 작업 기능은 회사 공용 프린터의 전역 설정을 변경하지 않습니다. 프린터 등록 기능은 별도 탭에서 확인을 받은 뒤에만 `lpadmin`을 실행합니다.

## 개발 및 검증

```bash
python3 -m pip install -e '.[test]'
python3 -m compileall -q src tests
pytest -q
```

## 다음 단계

용지 종류의 세부 옵션 확대, 정확한 장치 오류 모니터링(IPP/SNMP), 배포 패키지를 차례로 확장할 예정입니다.
