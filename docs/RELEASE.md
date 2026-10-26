# 릴리즈 만들기

관리자용 안내입니다. 일반 사용자는 [README 설치 방법](../README.md#설치)을 참고하세요.

## 배포 순서

1. `pyproject.toml`과 `src/printer_supporter/__init__.py`의 버전을 함께 변경합니다.
2. 변경 사항을 `main`에 병합하고 GitHub Actions 테스트 결과를 확인합니다.
3. **배포 라이선스 확인:** PyQt6(GPLv3 또는 상용), PyMuPDF(AGPLv3 또는 상용) 및 포함 라이브러리의 라이선스·소스 공개·고지 의무를 검토합니다.
4. 버전에 맞는 **새 태그**를 푸시합니다. 예: 버전이 `0.2.0`일 때 `git tag v0.2.0 && git push origin v0.2.0`.
5. Actions에서 `amd64`, `arm64` 빌드가 모두 통과하면 GitHub Release **초안(Draft)**이 생성됩니다. 파일과 `SHA256SUMS`를 확인합니다.
6. Chromebook에서 설치 및 앱 실행을 확인한 뒤 릴리즈를 공개합니다.

## Chromebook 설치 확인

1. CPU에 맞는 `.deb` 파일을 내려받아 **파일 앱 → Linux 파일** 폴더에 복사합니다.
2. **터미널 → Penguin**에서 설치합니다. 아래는 amd64, 버전 0.1.0 예시입니다.

   ```bash
   sudo apt install ./chromeos-printer-supporter_0.1.0_amd64.deb
   ```

3. **Linux 앱 → ChromeOS 프린터 지원**이 표시되는지, 메뉴·문서 선택·프린터 검색이 정상인지 확인합니다. 실제 인쇄는 별도로 테스트합니다.

**빌드 기준:** Ubuntu 22.04 기반, Debian 12 이상 Crostini 환경 대상. Python은 실행 파일에 포함되며 CUPS 등 시스템 패키지는 설치 시 함께 처리됩니다. 모든 Chromebook에서 동작을 보장하지는 않습니다.

앱 제거: `sudo apt remove chromeos-printer-supporter` (사용자 설정 파일은 남습니다).
