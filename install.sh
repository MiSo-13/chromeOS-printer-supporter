#!/usr/bin/env bash
set -euo pipefail

# Crostini에서 처음 실행할 때만 필요한 부트스트랩 도구입니다.
# 시스템 패키지 설치와 Python 패키지 설치 모두 사용자 동의를 받습니다.

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3가 필요합니다. Debian/Ubuntu Linux를 확인해 주세요." >&2
  exit 1
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo "이 설치 스크립트는 Debian/Ubuntu(Crostini) 환경만 지원합니다." >&2
  exit 1
fi

missing=()
if ! dpkg-query -W -f='${Status}' python3-venv 2>/dev/null | grep -q "install ok installed"; then
  missing+=(python3-venv)
fi
if ! command -v lpstat >/dev/null 2>&1 || ! command -v lp >/dev/null 2>&1; then
  missing+=(cups cups-client)
fi

if (( ${#missing[@]} > 0 )); then
  echo "필수 패키지 설치 예정: ${missing[*]}"
  read -r -p "sudo apt-get install로 설치할까요? [y/N] " answer
  case "$answer" in
    y|Y|yes|YES) sudo apt-get install -y "${missing[@]}" ;;
    *) echo "설치를 취소했습니다."; exit 1 ;;
  esac
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

echo "PyQt6 및 PrintHub 패키지를 Python 가상환경에 설치합니다."
read -r -p "pip 설치를 진행할까요? [y/N] " answer
case "$answer" in
  y|Y|yes|YES) .venv/bin/python -m pip install -e . ;;
  *) echo "설치를 취소했습니다."; exit 1 ;;
esac

if ! command -v libreoffice >/dev/null 2>&1; then
  echo "LibreOffice는 선택 의존성입니다. Word/Excel/PowerPoint 인쇄에 필요합니다."
  read -r -p "지금 설치할까요? [y/N] " answer
  case "$answer" in
    y|Y|yes|YES) sudo apt-get install -y libreoffice ;;
    *) echo "LibreOffice 설치를 건너뜁니다. 앱에서 나중에 설치할 수 있습니다." ;;
  esac
fi

echo
echo "설치 완료! 앱 실행:"
echo "  .venv/bin/chromeos-printer-supporter"
