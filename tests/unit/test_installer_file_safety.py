import importlib.util
import hashlib
import io
import logging
import sys
import time
import types
import urllib.error
import zipfile
from pathlib import Path

import pytest

from core import ffmpeg_installer


class Response(io.BytesIO):
    def __init__(self, payload=b"new", length="3"):
        super().__init__(payload)
        self.headers = {"Content-Length": length, "content-length": length}


@pytest.fixture
def bootstrap_download(monkeypatch):
    stub = types.ModuleType("logging_setup")
    stub.get_logger = lambda: logging.getLogger("download-test")
    stub.log_and_ui = lambda message: None
    monkeypatch.setitem(sys.modules, "logging_setup", stub)
    source = Path(__file__).resolve().parents[2] / "BootStrapper" / "download_utils.py"
    spec = importlib.util.spec_from_file_location("download_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_get_ssl_context", lambda: None)
    return module


@pytest.mark.parametrize("failure", ["network", "truncated", "hash", "callback", "replace"])
def test_bootstrap_failure_preserves_owned_and_unowned_files(bootstrap_download, tmp_path, monkeypatch, failure):
    target = tmp_path / "download.zip"
    target.write_bytes(b"old")
    unowned = tmp_path / "download.zip.part"
    unowned.write_bytes(b"unowned")
    response = Response(length="10" if failure == "truncated" else "3")

    def open_response(*args, **kwargs):
        if failure == "network":
            raise urllib.error.URLError("offline")
        return response

    def callback(*args):
        if failure == "callback":
            raise ValueError("callback failed")

    def fail_replace(*args):
        raise OSError("destination locked")

    monkeypatch.setattr(bootstrap_download.urllib.request, "urlopen", open_response)
    if failure == "replace":
        monkeypatch.setattr(bootstrap_download.os, "replace", fail_replace)
    try:
        assert not bootstrap_download.download_file("https://test.invalid/file", str(target), callback,
                                                   max_retries=1,
                                                   expected_sha256="0" * 64 if failure == "hash" else "")
    except ValueError:
        assert failure == "callback"
    assert target.read_bytes() == b"old"
    assert unowned.read_bytes() == b"unowned"
    assert set(tmp_path.iterdir()) == {target, unowned}
    assert failure == "network" or response.closed


@pytest.mark.parametrize("failure", ["truncated", "cancel", "callback", "replace"])
def test_core_download_failure_preserves_file(tmp_path, monkeypatch, failure):
    target = tmp_path / "download.zip"
    target.write_bytes(b"old")
    response = Response(length="10" if failure == "truncated" else "3")
    downloader = ffmpeg_installer.FFmpegDownloader()

    def callback(*args):
        if failure == "cancel":
            downloader.cancel()
        elif failure == "callback":
            raise ValueError("callback failed")

    downloader._progress_callback = callback
    monkeypatch.setattr(downloader, "_safe_callback", lambda cb, *args: cb(*args) if cb else None)
    monkeypatch.setattr(ffmpeg_installer.urllib.request, "urlopen", lambda *args, **kwargs: response)
    if failure == "replace":
        def fail_replace(*args):
            raise OSError("destination locked")
        monkeypatch.setattr(ffmpeg_installer.os, "replace", fail_replace)
    try:
        assert not downloader._download_file("https://test.invalid/file", str(target))
    except ValueError:
        assert failure == "callback"
    assert target.read_bytes() == b"old"
    assert set(tmp_path.iterdir()) == {target}
    assert response.closed


def make_archive(tmp_path, missing=False):
    archive = tmp_path / "tools.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("build/bin/ffmpeg.exe", b"new encoder")
        if not missing:
            zf.writestr("build/bin/ffprobe.exe", b"new probe")
    return archive


@pytest.mark.parametrize("failure", ["missing", "cancel", "callback", "promotion"])
def test_extract_failure_preserves_tool_pair(tmp_path, monkeypatch, failure):
    destination = tmp_path / "tools"
    destination.mkdir()
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        (destination / name).write_bytes(b"old " + name.encode())
    archive = make_archive(tmp_path, missing=failure == "missing")
    downloader = ffmpeg_installer.FFmpegDownloader()

    def callback(*args):
        if failure == "cancel":
            downloader.cancel()
        elif failure == "callback":
            raise ValueError("callback failed")

    downloader._progress_callback = callback
    monkeypatch.setattr(downloader, "_safe_callback", lambda cb, *args: cb(*args) if cb else None)
    replace = ffmpeg_installer.os.replace

    def fail_second(source, target):
        if Path(target) == destination / "ffprobe.exe" and Path(source).parent.name != "backup":
            raise OSError("second executable locked")
        return replace(source, target)

    if failure == "promotion":
        monkeypatch.setattr(ffmpeg_installer.os, "replace", fail_second)
    with pytest.raises(Exception):
        downloader._extract_ffmpeg(str(archive), destination)
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        assert (destination / name).read_bytes() == b"old " + name.encode()
    assert set(destination.iterdir()) == {destination / "ffmpeg.exe", destination / "ffprobe.exe"}


def test_extract_success_replaces_both_tools_and_preserves_other_files(tmp_path):
    destination = tmp_path / "tools"
    destination.mkdir()
    (destination / "keep.txt").write_text("keep")
    ffmpeg_installer.FFmpegDownloader()._extract_ffmpeg(str(make_archive(tmp_path)), destination)
    assert (destination / "ffmpeg.exe").read_bytes() == b"new encoder"
    assert (destination / "ffprobe.exe").read_bytes() == b"new probe"
    assert (destination / "keep.txt").read_text() == "keep"


@pytest.mark.parametrize("bootstrap", [True, False])
def test_download_success_atomically_replaces_file(bootstrap_download, tmp_path, monkeypatch, bootstrap):
    target = tmp_path / "download.zip"
    target.write_bytes(b"old")
    response = Response()
    monkeypatch.setattr(ffmpeg_installer.urllib.request, "urlopen", lambda *args, **kwargs: response)
    if bootstrap:
        assert bootstrap_download.download_file("https://test.invalid/file", str(target), max_retries=1,
                                               expected_sha256=hashlib.sha256(b"new").hexdigest())
    else:
        assert ffmpeg_installer.FFmpegDownloader()._download_file("https://test.invalid/file", str(target))
    assert target.read_bytes() == b"new"
    assert set(tmp_path.iterdir()) == {target}
    assert response.closed


def test_core_timeout_preserves_file(tmp_path, monkeypatch):
    target = tmp_path / "download.zip"
    target.write_bytes(b"old")
    response = Response()
    clock = iter([0, 0, 301])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(ffmpeg_installer.urllib.request, "urlopen", lambda *args, **kwargs: response)
    assert not ffmpeg_installer.FFmpegDownloader()._download_file("https://test.invalid/file", str(target))
    assert target.read_bytes() == b"old"
    assert set(tmp_path.iterdir()) == {target}
    assert response.closed


def test_failed_pair_rollback_retains_old_backup(tmp_path, monkeypatch):
    destination = tmp_path / "tools"
    destination.mkdir()
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        (destination / name).write_bytes(b"old " + name.encode())
    replace = ffmpeg_installer.os.replace

    def fail_replace(source, target):
        if Path(target).name == "ffprobe.exe" or Path(source).parent.name == "backup":
            raise OSError("locked")
        return replace(source, target)

    monkeypatch.setattr(ffmpeg_installer.os, "replace", fail_replace)
    with pytest.raises(OSError):
        ffmpeg_installer.FFmpegDownloader()._extract_ffmpeg(str(make_archive(tmp_path)), destination)
    backups = list(destination.glob(".ffmpeg-*/backup/ffmpeg.exe"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"old ffmpeg.exe"
    assert (destination / "ffprobe.exe").read_bytes() == b"old ffprobe.exe"


def test_integrity_requires_ffprobe(tmp_path, monkeypatch):
    archive = make_archive(tmp_path, missing=True)
    monkeypatch.setattr(ffmpeg_installer.os.path, "getsize", lambda path: 31 * 1024 * 1024)
    assert not ffmpeg_installer.FFmpegDownloader._verify_zip_integrity(str(archive))


def test_installed_check_requires_both_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_installer, "get_ffmpeg_dir", lambda: tmp_path)
    (tmp_path / "ffmpeg.exe").write_bytes(b"encoder")
    assert not ffmpeg_installer.is_ffmpeg_installed()
    (tmp_path / "ffprobe.exe").write_bytes(b"probe")
    assert ffmpeg_installer.is_ffmpeg_installed()
