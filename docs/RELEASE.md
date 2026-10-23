# 릴리즈 점검

릴리즈 파일은 GitHub Actions가 만드는 **`amd64.deb`와 `arm64.deb`**입니다. 태그를 푸시하면 초안(Draft) 릴리즈만 생성하며 **자동 공개하지 않습니다**.

1. PR 병합 후 GitHub Actions의 두 아키텍처 빌드·설치 검사가 모두 통과하는지 확인합니다.
2. **배포 라이선스 검토:** PyQt6(GPLv3 또는 상용), PyMuPDF(AGPLv3 또는 상용)와 포함된 Qt/라이브러리의 재배포·소스 공개·고지 의무를 확인하세요. 프로젝트 라이선스와 필요한 고지 파일을 준비하기 전에는 릴리즈를 공개하지 마세요.
3. 프로젝트 버전이 `0.1.0`이면 `git tag v0.1.0 && git push origin v0.1.0`으로 빌드를 시작합니다.
4. GitHub Releases의 **Draft**에서 두 `.deb`와 `SHA256SUMS`를 확인합니다.
5. 실제 Chromebook의 Linux 환경에서 해당 CPU 패키지를 설치하고 **Linux 앱 목록 표시, 메뉴·문서 선택, 프린터 검색**을 확인합니다. 테스트 인쇄는 사용자 동의하에 별도로 진행하세요.
6. 검증 후 GitHub Releases에서 **Publish release**를 누릅니다.

**빌드 기준:** Ubuntu 22.04 (glibc 2.35). Debian 12 이상 Crostini 환경을 주요 대상으로 하며, 모든 ChromeOS 장치에서 동작을 보장하지 않습니다. Python과 PyQt6는 릴리즈 실행 파일에 포함되지만 CUPS 등 Linux 시스템 의존성은 패키지 설치 시 APT가 처리합니다.

앱 제거: Linux 터미널에서 `sudo apt remove chromeos-printer-supporter`. 사용자 설정은 `~/.config/chromeos-printer-supporter/settings.json`에 유지됩니다.
