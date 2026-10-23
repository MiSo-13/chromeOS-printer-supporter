import json

from printer_supporter.document_input import local_document_from_text
from printer_supporter.settings import SettingsStore


def test_last_document_folder_persists(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    folder = tmp_path / "docs"
    folder.mkdir()
    store.set_last_document_dir(folder)
    assert SettingsStore(store.path).data["last_document_dir"] == str(folder.resolve())
    store.set_theme("dark")
    assert json.loads(store.path.read_text())["last_document_dir"] == str(folder.resolve())


def test_invalid_saved_folder_falls_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"theme":"light","last_document_dir":123}', encoding="utf-8")
    assert SettingsStore(path).data["last_document_dir"] == ""


def test_pasted_path_and_file_uri(tmp_path):
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"dummy")
    assert local_document_from_text(str(document)) == document
    assert local_document_from_text(document.as_uri()) == document
    assert local_document_from_text("https://example.com/sample.pdf") is None
    assert local_document_from_text(str(tmp_path / "missing.pdf")) is None
    unsupported = tmp_path / "script.sh"
    unsupported.write_text("echo test")
    assert local_document_from_text(str(unsupported)) is None

def test_chromeos_uri_list_clipboard(tmp_path):
    from PyQt6.QtCore import QMimeData
    from printer_supporter.document_input import local_document_from_mime

    document = tmp_path / "테스트 문서.pdf"
    document.write_bytes(b"dummy")
    mime = QMimeData()
    mime.setData("text/uri-list", (document.as_uri() + "\\r\\n").encode())
    assert local_document_from_mime(mime) == document


def test_gnome_copied_files_clipboard(tmp_path):
    from PyQt6.QtCore import QMimeData
    from printer_supporter.document_input import local_document_from_mime

    document = tmp_path / "sample.pdf"
    document.write_bytes(b"dummy")
    mime = QMimeData()
    mime.setData("x-special/gnome-copied-files", ("copy\\n" + document.as_uri()).encode())
    assert local_document_from_mime(mime) == document
