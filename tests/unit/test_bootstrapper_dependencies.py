import importlib
import sys
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def bootstrap(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "BootStrapper"))
    for name in ("paths", "deps_checker", "deps_installer", "deps_specs", "download_utils",
                 "extract_utils", "logging_setup"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    installer = importlib.import_module("deps_installer")
    checker = importlib.import_module("deps_checker")
    monkeypatch.setattr(installer, "log_and_ui", lambda _: None)
    monkeypatch.setattr(checker, "log_and_ui", lambda _: None)
    return installer, checker


def test_existing_incompatible_envs_survive_force(bootstrap, tmp_path, monkeypatch):
    installer, _ = bootstrap
    for name in ("env", "env-cp311-64"):
        directory = tmp_path / "XGif" / name
        directory.mkdir(parents=True)
        (directory / "keep").write_text(name)
    monkeypatch.setattr(installer, "_stream_run", lambda *_: pytest.fail("unexpected install"))
    monkeypatch.setattr(installer, "_detect_cuda_major", lambda: 13)
    assert not installer.install_venv(force=True)
    assert not installer.install_cupy()
    for name in ("env", "env-cp311-64"):
        assert (tmp_path / "XGif" / name / "keep").read_text() == name


def test_failed_creation_preserves_legacy_and_releases_owned_target(bootstrap, tmp_path, monkeypatch):
    installer, _ = bootstrap
    legacy = tmp_path / "XGif" / "env"
    legacy.mkdir(parents=True)
    (legacy / "keep").write_text("existing")
    sibling = legacy.with_name("env-cp311-64")

    def run(command):
        if command[1:3] == ["-m", "virtualenv"]:
            assert Path(command[-1]) == sibling
            (sibling / "partial").touch()
            return 1
        return 0

    monkeypatch.setattr(installer, "_stream_run", run)
    assert not installer.install_venv()
    assert (legacy / "keep").read_text() == "existing"
    assert not sibling.exists()


def test_target_created_during_install_is_not_overwritten(bootstrap, monkeypatch):
    installer, _ = bootstrap
    target = installer.paths.get_venv_dir()

    def finish_base_install(_command):
        target.mkdir(parents=True)
        (target / "keep").write_text("other install")
        return 0

    monkeypatch.setattr(installer, "_stream_run", finish_base_install)
    assert not installer.install_venv()
    assert (target / "keep").read_text() == "other install"


def test_frozen_gpu_requirements_come_from_bundle(bootstrap, tmp_path, monkeypatch):
    installer, _ = bootstrap
    bundle = tmp_path / "_internal"
    bundle.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    (tmp_path / "requirements-gpu.txt").touch()
    assert installer._find_gpu_requirements_file() is None
    requirements = bundle / "requirements-gpu.txt"
    requirements.touch()
    assert installer._find_gpu_requirements_file() == requirements


def test_failed_subprocess_reports_last_error(bootstrap, monkeypatch):
    installer, _ = bootstrap
    messages = []
    monkeypatch.setattr(installer, "log_and_ui", messages.append)
    command = [sys.executable, "-c", "import sys; print('pip failed'); sys.exit(1)"]
    assert installer._stream_run(command) == 1
    assert messages == ["pip failed"]


@pytest.mark.parametrize(("code", "stdout", "stderr", "expected"), [
    (0, "0", "", (False, "사용 가능한 CUDA 장치가 없습니다.")),
    (0, "1", "", (True, "GPU 1개")),
    (1, "", "Traceback\nDLL load failed", (False, "DLL load failed")),
])
def test_cupy_requires_usable_device(bootstrap, monkeypatch, code, stdout, stderr, expected):
    _, checker = bootstrap
    monkeypatch.setattr(checker, "_nvidia_cache", (True, "NVIDIA"))
    monkeypatch.setattr(checker.paths, "is_compatible_venv", lambda _: True)
    monkeypatch.setattr(checker, "_run", lambda *a, **kw: (code, stdout, stderr))
    assert checker.check_cupy() == expected


@pytest.mark.parametrize("probe", [None, "", "broken", "new"])
def test_ffmpeg_pair_promoted_together(bootstrap, tmp_path, monkeypatch, probe):
    installer, checker = bootstrap
    target = tmp_path / "ffmpeg"
    target.mkdir()
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        (target / name).write_text("previous")
    monkeypatch.setattr(installer.paths, "FFMPEG_DIR", str(target))
    monkeypatch.setattr(installer, "download_file", lambda *a, **kw: True)
    archive = Path(installer.paths.TEMP_DIR) / "ffmpeg.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("release/bin/ffmpeg.exe", "new")
        if probe is not None:
            zipped.writestr("release/bin/ffprobe.exe", probe)
        zipped.writestr("release/LICENSE", "license")
    def probe_version(command):
        return (1 if Path(command[0]).read_text() == "broken" else 0, "version 4.0", "")
    monkeypatch.setattr(checker, "_run", probe_version)
    complete = probe == "new"
    assert installer.install_ffmpeg() is complete
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        assert (target / name).read_text() == ("new" if complete else "previous")
    monkeypatch.setattr(checker, "_run", lambda *_: (0, "version 4.0", ""))
    assert checker.check_ffmpeg()[0]
    (target / "ffprobe.exe").unlink()
    assert checker.check_ffmpeg() == (False, "ffprobe.exe 없음")


def test_ffmpeg_retries_mirror_after_invalid_archive(bootstrap, tmp_path, monkeypatch):
    installer, checker = bootstrap
    calls = []
    def download(url, dest, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            Path(dest).write_text("network login page")
        else:
            with zipfile.ZipFile(dest, "w") as archive:
                for name in ("ffmpeg.exe", "ffprobe.exe"):
                    archive.writestr("release/bin/" + name, b"second mirror")
        return True
    monkeypatch.setattr(installer, "download_file", download)
    monkeypatch.setattr(checker, "_run", lambda *_: (0, "version 1.0", ""))
    assert installer.install_ffmpeg()
    assert calls == [installer.deps_specs.FFMPEG_ZIP_URL, installer.deps_specs.FFMPEG_ZIP_URL_FALLBACK]
