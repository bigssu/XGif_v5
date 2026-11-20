import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import cupy_env


def test_incompatible_legacy_is_kept_and_existing_compatible_env_is_reused(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy = cupy_env.legacy_env_dir()
    legacy.mkdir(parents=True)
    (legacy / "keep.txt").write_text("original")
    sibling = cupy_env.select_cupy_env()
    assert sibling.parent == legacy.parent and sibling != legacy
    monkeypatch.setattr(cupy_env, "find_compatible_python", lambda: None)
    with pytest.raises(cupy_env.MissingCompatiblePython, match="CPython"):
        cupy_env.frozen_install_commands(["cupy"])
    assert (legacy / "keep.txt").read_text() == "original"

    sibling.mkdir()
    with pytest.raises(RuntimeError, match="existing Python environment"):
        cupy_env.frozen_install_commands(["cupy"])
    pip_main = sibling / "Lib" / "site-packages" / "pip" / "__main__.py"
    pip_main.parent.mkdir(parents=True)
    pip_main.touch()
    monkeypatch.setattr(cupy_env, "env_matches_runtime", lambda path, **kw: path == sibling)
    commands = cupy_env.frozen_install_commands(["cupy"])
    assert all(cmd[:3] == [str(sibling / "Scripts" / "python.exe"), "-m", "pip"] for cmd in commands)
    assert (legacy / "keep.txt").read_text() == "original"


@pytest.mark.skipif(os.name != "nt", reason="Windows venv redirector")
def test_installed_env_checks_actual_python_minor_bitness_and_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy = cupy_env.legacy_env_dir()
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(legacy)], check=True)
    assert cupy_env.env_matches_runtime(legacy)
    assert not cupy_env.env_matches_runtime(legacy, bits=32 if cupy_env.PYTHON_BITS == 64 else 64)
    assert not cupy_env.env_matches_runtime(legacy, version=(2, 7))
    assert cupy_env.select_cupy_env() == legacy
    with monkeypatch.context() as isolated:
        isolated.setattr(cupy_env, "find_compatible_python", lambda: pytest.fail("discovered base for valid env"))
        commands = cupy_env.frozen_install_commands(["cupy"])
    exe = str(legacy / "Scripts" / "python.exe")
    assert commands[0] == [exe, "-m", "ensurepip", "--upgrade"]
    assert all(cmd[1:3] == ["-m", "pip"] for cmd in commands[1:])
    cupy_env.run_install_command(commands[0], check=True, capture_output=True)
    subprocess.run([exe, "-I", "-m", "pip", "--version"], check=True, capture_output=True)
    assert all(cmd[1:3] == ["-m", "pip"] for cmd in cupy_env.frozen_install_commands(["cupy"]))

    # Exercise actual base discovery when PATH resolves to the target interpreter.
    monkeypatch.setattr(cupy_env.shutil, "which", lambda name: str(legacy / "Scripts" / "python.exe")
                        if name == "python" else None)
    assert Path(cupy_env.find_compatible_python()).samefile(sys._base_executable)


@pytest.mark.parametrize("raises", [False, True])
def test_failed_create_is_retryable_but_existing_target_is_never_overwritten(tmp_path, monkeypatch, raises):
    target = tmp_path / "env"
    command = ["python", "-m", "venv", str(target)]

    def fail(*args, **kwargs):
        (target / "partial").touch()
        if raises:
            raise subprocess.TimeoutExpired(command, 5)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(subprocess, "run", fail)
    if raises:
        with pytest.raises(subprocess.TimeoutExpired):
            cupy_env.run_install_command(command)
    else:
        assert cupy_env.run_install_command(command).returncode == 1
    assert not target.exists()
    target.mkdir()
    (target / "keep").touch()
    with pytest.raises(FileExistsError):
        cupy_env.run_install_command(command)
    assert sorted(p.name for p in target.iterdir()) == ["keep"]


@pytest.mark.parametrize("module", ["pip", "ensurepip"])
def test_pip_rechecks_environment_before_install(tmp_path, monkeypatch, module):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    exe = tmp_path / "env" / "Scripts" / "python.exe"
    with pytest.raises(RuntimeError, match="changed before installation"):
        cupy_env.run_install_command([str(exe), "-m", module, "--version"])


@pytest.mark.parametrize("sibling_state", ["empty", "broken", "ready"])
def test_selection_prefers_usable_cupy_with_two_compatible_envs(tmp_path, monkeypatch, sibling_state):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy = cupy_env.legacy_env_dir()
    sibling = legacy.with_name(f"env-cp{sys.version_info.major}{sys.version_info.minor}-{cupy_env.PYTHON_BITS}")
    for env in (legacy, sibling):
        site = env / "Lib" / "site-packages" / "cupy"
        site.mkdir(parents=True)
        if env == legacy or sibling_state != "empty":
            (site / "__init__.py").touch()

    monkeypatch.setattr(cupy_env, "env_matches_runtime", lambda *_args, **_kwargs: True)
    def probe(cmd, **kwargs):
        assert "getDeviceCount" in cmd[-1] and kwargs["timeout"] > 0
        ok = Path(cmd[0]).parent.parent == legacy or sibling_state == "ready"
        return SimpleNamespace(returncode=0 if ok else 1, stdout=b"1" if ok else b"")
    monkeypatch.setattr(subprocess, "run", probe)
    assert cupy_env.select_cupy_env() == (sibling if sibling_state == "ready" else legacy)
