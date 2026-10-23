"""사용자 설정을 JSON으로 저장합니다."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

DEFAULT_SETTINGS = {"theme": "light"}
VALID_THEMES = {"light", "dark"}


def settings_path() -> Path:
    """앱 데이터 디렉터리. 환경변수로 경로를 변경할 수 있습니다."""
    base = os.environ.get("PRINTHUB_CONFIG_DIR")
    return (Path(base).expanduser() if base else Path.home() / ".config" / "printhub") / "settings.json"


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else settings_path()
        self.data = self.load()

    def load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return DEFAULT_SETTINGS.copy()
        except (OSError, ValueError, UnicodeError):
            return DEFAULT_SETTINGS.copy()
        settings = {**DEFAULT_SETTINGS, **data}
        if settings.get("theme") not in VALID_THEMES:
            settings["theme"] = DEFAULT_SETTINGS["theme"]
        return settings

    def set_theme(self, theme: str) -> None:
        if theme not in VALID_THEMES:
            raise ValueError(f"지원하지 않는 테마: {theme}")
        updated = {**self.data, "theme": theme}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, prefix=".settings-", suffix=".tmp", delete=False) as stream:
                temp_path = Path(stream.name)
                json.dump(updated, stream, ensure_ascii=False, indent=2)
                stream.write("\\n")
            os.replace(temp_path, self.path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        self.data = updated
