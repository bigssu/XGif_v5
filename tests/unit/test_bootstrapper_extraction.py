import importlib.util
import logging
import sys
import types
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def extraction(monkeypatch):
    logging_stub = types.ModuleType("logging_setup")
    logging_stub.get_logger = lambda: logging.getLogger("extraction-test")
    logging_stub.log_and_ui = lambda message: None
    monkeypatch.setitem(sys.modules, "logging_setup", logging_stub)
    source = Path(__file__).resolve().parents[2] / "BootStrapper" / "extract_utils.py"
    spec = importlib.util.spec_from_file_location("extraction_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_zip(tmp_path, name="app.exe"):
    archive = tmp_path / "update.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(name, "new")
    return archive


def old_install(tmp_path):
    target = tmp_path / "installed"
    target.mkdir()
    (target / "app.exe").write_text("old")
    return target


def test_corrupt_zip_preserves_install(extraction, tmp_path):
    target = old_install(tmp_path)
    archive = tmp_path / "bad.zip"
    archive.write_bytes(b"not a zip")
    assert not extraction.extract_zip(str(archive), str(target), "app.exe")
    assert (target / "app.exe").read_text() == "old"


@pytest.mark.parametrize("flatten", [False, True])
def test_missing_expected_file_preserves_install(extraction, tmp_path, flatten):
    target = old_install(tmp_path)
    archive = make_zip(tmp_path, "root/other.txt")
    assert not extraction.extract_zip(str(archive), str(target), "app.exe", flatten)
    assert (target / "app.exe").read_text() == "old"


@pytest.mark.parametrize("flatten", [False, True])
def test_success_replaces_install(extraction, tmp_path, flatten):
    target = old_install(tmp_path)
    archive = make_zip(tmp_path, "root/app.exe" if flatten else "app.exe")
    progress = []
    assert extraction.extract_zip(str(archive), str(target), "app.exe", flatten,
                                  lambda current, total: progress.append((current, total)))
    assert (target / "app.exe").read_text() == "new"
    assert progress == [(1, 1)]
    assert set(tmp_path.iterdir()) == {target, archive}


@pytest.mark.parametrize("flatten", [False, True])
def test_failed_promotion_restores_install(extraction, tmp_path, monkeypatch, flatten):
    target = old_install(tmp_path)
    archive = make_zip(tmp_path, "root/app.exe" if flatten else "app.exe")
    rename = extraction.os.rename

    def fail_promotion(source, destination):
        if Path(destination) == target and Path(source).name != "previous":
            raise OSError("promotion failed")
        return rename(source, destination)

    monkeypatch.setattr(extraction.os, "rename", fail_promotion)
    assert not extraction.extract_zip(str(archive), str(target), "app.exe", flatten)
    assert (target / "app.exe").read_text() == "old"
    assert set(tmp_path.iterdir()) == {target, archive}


def test_failed_rollback_preserves_backup(extraction, tmp_path, monkeypatch):
    target = old_install(tmp_path)
    archive = make_zip(tmp_path)
    rename = extraction.os.rename

    def fail_destination(source, destination):
        if Path(destination) == target:
            raise OSError("destination unavailable")
        return rename(source, destination)

    monkeypatch.setattr(extraction.os, "rename", fail_destination)
    assert not extraction.extract_zip(str(archive), str(target), "app.exe")
    backups = list(tmp_path.glob(".installed-*/previous/app.exe"))
    assert len(backups) == 1
    assert backups[0].read_text() == "old"


def test_unowned_temp_directory_is_preserved(extraction, tmp_path):
    target = old_install(tmp_path)
    unrelated = tmp_path / "installed_tmp_extract"
    unrelated.mkdir()
    (unrelated / "keep.txt").write_text("keep")
    assert extraction.extract_zip(str(make_zip(tmp_path)), str(target), "app.exe")
    assert (unrelated / "keep.txt").read_text() == "keep"


def test_ffmpeg_failed_extraction_does_not_modify_old_install(tmp_path, monkeypatch):
    target = tmp_path / "ffmpeg"
    (target / "bin").mkdir(parents=True)
    executable = target / "bin" / "ffmpeg.exe"
    executable.write_text("old")
    stubs = {
        "paths": {"TEMP_DIR": str(tmp_path), "FFMPEG_DIR": str(target),
                  "FFMPEG_EXE": str(target / "ffmpeg.exe")},
        "deps_specs": {"FFMPEG_ZIP_URL": "unused"},
        "deps_checker": {"check_ffmpeg": lambda *_: pytest.fail("checked a failed extraction")},
        "download_utils": {"download_file": lambda *args, **kwargs: True},
        "extract_utils": {"extract_zip": lambda *args, **kwargs: False},
        "logging_setup": {"log_and_ui": lambda message: None,
                          "log_subprocess_output": lambda message: None,
                          "get_logger": lambda: logging.getLogger("installer-test")},
    }
    for name, attributes in stubs.items():
        stub = types.ModuleType(name)
        stub.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, stub)
    source = Path(__file__).resolve().parents[2] / "BootStrapper" / "deps_installer.py"
    spec = importlib.util.spec_from_file_location("installer_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert not module.install_ffmpeg()
    assert executable.read_text() == "old"
    assert not (target / "ffmpeg.exe").exists()
