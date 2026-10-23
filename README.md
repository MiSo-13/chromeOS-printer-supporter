# PrintHub · ChromeOS Printer Supporter

ChromeOS의 Linux(Crostini)에서 실행하는 PyQt6 기반 CUPS 프린터 관리자입니다.
첫 번째 검증 모델은 **Samsung SL-M2030W / Samsung M203x Series**입니다. 특정 모델에 종속되지 않도록 기존 CUPS 큐를 탐색해 사용합니다.

## 제공 기능

- 등록된 CUPS 프린터 조회, 상태 및 오류 내용 표시 (5초마다 갱신)
- PDF, TXT, PNG/JPEG/TIFF/GIF 파일 인쇄
- Word(`.doc`, `.docx`), Excel(`.xls`, `.xlsx`), PowerPoint(`.ppt`, `.pptx`) 및 ODF 문서 인쇄 (LibreOffice로 임시 PDF 변환)
- A4/Letter, 인쇄 매수 지정
- 현재 CUPS 큐의 작업 조회 및 **내 작업** 취소
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

## 프린터 검색 및 등록

앱의 **프린터 추가** 탭에서 다음을 사용할 수 있습니다.

1. **네트워크 프린터 검색**: `lpinfo -v`의 발견 결과를 표시합니다. IP 대역 전체를 스캔하지 않습니다.
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
- '대기' 및 작업 목록 제거는 실제 종이 출력 완료를 보증하지 않습니다.
- 회사 공용 프린터의 전역 설정은 변경하지 않습니다. 앱은 `lpadmin`을 실행하지 않습니다.

## 개발 및 검증

```bash
python3 -m pip install -e '.[test]'
python3 -m compileall -q src tests
pytest -q
```

## 다음 단계

프린터별 기능 조회, 용지 종류 자동 인식, 정확한 장치 오류 모니터링(IPP/SNMP), 테스트 페이지, 배포 패키지를 차례로 확장할 예정입니다.
