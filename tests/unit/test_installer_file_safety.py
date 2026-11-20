import importlib.util
import hashlib
import http.client
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


@pytest.fixture
def runnable_staged_tools(monkeypatch):
    def run(command, **kwargs):
        path = Path(command[0])
        assert command[1:] == ["-version"]
        assert path.parent.name.startswith(".ffmpeg-") and path.exists()
        assert 0 < kwargs["timeout"] <= 10
        return types.SimpleNamespace(returncode=0, stdout=f"{path.stem} version 1".encode())
    monkeypatch.setattr(ffmpeg_installer.subprocess, "run", run)


def make_archive(tmp_path, missing=False):
    archive = tmp_path / "tools.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("build/bin/ffmpeg.exe", b"new encoder")
        if not missing:
            zf.writestr("build/bin/ffprobe.exe", b"new probe")
    return archive


@pytest.mark.parametrize("failure", ["missing", "cancel", "callback", "promotion"])
def test_extract_failure_preserves_tool_pair(tmp_path, monkeypatch, failure, runnable_staged_tools):
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


def test_extract_success_replaces_both_tools_and_preserves_other_files(tmp_path, runnable_staged_tools):
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


def test_failed_pair_rollback_retains_old_backup(tmp_path, monkeypatch, runnable_staged_tools):
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



@pytest.mark.parametrize("legacy_source", ["bundle", "executable"])
def test_frozen_download_is_per_user_and_legacy_is_discoverable(tmp_path, monkeypatch, legacy_source, runnable_staged_tools):
    from editor.core.video_decoder import VideoDecoder

    bundle = tmp_path / "_MEI"
    program = tmp_path / "Program Files" / "XGif"
    local = tmp_path / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(program / "XGif.exe"))
    monkeypatch.setattr(ffmpeg_installer, "check_system_ffmpeg", lambda: None)
    legacy = (bundle if legacy_source == "bundle" else program) / "ffmpeg"
    legacy.mkdir(parents=True)
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        (legacy / name).write_bytes(b"old")
    manager = ffmpeg_installer.FFmpegManager
    assert manager.get_ffmpeg_executable() == str(legacy / "ffmpeg.exe")
    assert VideoDecoder._ffmpeg_tools() == tuple(str(legacy / name) for name in ("ffmpeg.exe", "ffprobe.exe"))

    downloader = ffmpeg_installer.FFmpegDownloader()
    archive = make_archive(tmp_path)
    def download(_url, destination):
        Path(destination).write_bytes(archive.read_bytes())
        return True
    monkeypatch.setattr(downloader, "_download_file", download)
    monkeypatch.setattr(downloader, "_verify_zip_integrity", lambda _: True)
    downloader._download_and_install()
    installed = local / "XGif" / "ffmpeg"
    assert manager.get_ffmpeg_executable() == str(installed / "ffmpeg.exe")
    assert VideoDecoder._ffmpeg_tools() == tuple(str(installed / name) for name in ("ffmpeg.exe", "ffprobe.exe"))
    assert (installed / "ffprobe.exe").read_bytes() == b"new probe"
    assert (legacy / "ffmpeg.exe").read_bytes() == b"old"

    system_encoder = tmp_path / "system" / "ffmpeg.exe"
    system_encoder.parent.mkdir()
    system_encoder.touch()
    monkeypatch.setattr(ffmpeg_installer, "check_system_ffmpeg", lambda: str(system_encoder))
    monkeypatch.setattr(ffmpeg_installer.shutil, "which", lambda _name: None)
    assert manager.get_ffmpeg_executable() == str(system_encoder)
    assert VideoDecoder._ffmpeg_tools() == (str(installed / "ffmpeg.exe"), str(installed / "ffprobe.exe"))


@pytest.mark.parametrize("failure", ["bad_zip", "bad_tool", "offline", "cancel"])
def test_core_mirror_attempts_include_validation(tmp_path, monkeypatch, failure):
    callbacks = []
    calls = []
    worker = ffmpeg_installer.FFmpegDownloader(finished_callback=lambda *result: callbacks.append(result))
    monkeypatch.setattr(worker, "_safe_callback", lambda cb, *args: cb(*args) if cb else None)
    monkeypatch.setattr(ffmpeg_installer, "get_ffmpeg_install_dir", lambda: tmp_path)
    def download(url, path):
        calls.append(url)
        if failure == "cancel":
            worker.cancel()
        return failure != "offline"
    def extract(path, dest):
        if failure == "bad_tool" and len(calls) == 1:
            raise ValueError("ffprobe.exe failed validation")
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            (dest / name).touch()
    monkeypatch.setattr(worker, "_download_file", download)
    monkeypatch.setattr(worker, "_verify_zip_integrity", lambda _: failure != "bad_zip" or len(calls) > 1)
    monkeypatch.setattr(worker, "_extract_ffmpeg", extract)
    worker.run()
    assert len(calls) == (1 if failure == "cancel" else 2)
    assert len(callbacks) == 1
    ok, message = callbacks[0]
    assert ok == (failure in {"bad_zip", "bad_tool"})
    assert ("취소" in message) == (failure == "cancel")


def test_unlaunchable_staged_tools_preserve_previous_installation(tmp_path):
    dest = tmp_path / "ffmpeg"
    dest.mkdir()
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        (dest / name).write_bytes(b"previous")
    with pytest.raises(ValueError, match="ffmpeg.exe"):
        ffmpeg_installer.FFmpegDownloader()._extract_ffmpeg(str(make_archive(tmp_path)), dest)
    assert all((dest / name).read_bytes() == b"previous" for name in ("ffmpeg.exe", "ffprobe.exe"))

@pytest.mark.parametrize("bootstrap", [True, False])
@pytest.mark.parametrize("failure", ["interrupted_chunk", "bad_length"])
def test_http_response_errors_allow_retry_without_replacing_download(
        bootstrap_download, tmp_path, monkeypatch, bootstrap, failure):
    class InterruptedResponse(Response):
        def read(self, size):
            raise http.client.IncompleteRead(b"partial")

    response = InterruptedResponse() if failure == "interrupted_chunk" else Response(length="unavailable")
    monkeypatch.setattr(ffmpeg_installer.urllib.request, "urlopen", lambda *a, **kw: response)
    destination = tmp_path / "download.zip"
    destination.write_bytes(b"existing")
    if bootstrap:
        success = bootstrap_download.download_file("https://test.invalid/file", str(destination), max_retries=1)
    else:
        success = ffmpeg_installer.FFmpegDownloader()._download_file("https://test.invalid/file", str(destination))
    assert not success and response.closed
    assert list(tmp_path.iterdir()) == [destination]
    assert destination.read_bytes() == b"existing"
