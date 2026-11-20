"""CuPy dependency policy regression tests."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import cupy_policy


def test_cupy_policy_prefers_verified_cuda13_package_set():
    assert cupy_policy.cupy_packages_for_cuda_major(None) == cupy_policy.CUDA13_CUPY_PACKAGES
    assert cupy_policy.cupy_packages_for_cuda_major(13) == cupy_policy.CUDA13_CUPY_PACKAGES
    assert cupy_policy.should_use_gpu_requirements(None)
    assert cupy_policy.should_use_gpu_requirements(13)
    assert not cupy_policy.should_use_gpu_requirements(12)


def test_cupy_policy_keeps_legacy_cuda_packages_explicit():
    assert cupy_policy.cupy_packages_for_cuda_major(12) == (cupy_policy.CUDA12_CUPY_PACKAGE,)
    assert cupy_policy.cupy_packages_for_cuda_major(11) == (cupy_policy.CUDA11_CUPY_PACKAGE,)
    assert cupy_policy.cupy_packages_for_cuda_major(10) == ()


def test_cupy_policy_formats_special_requirements_safely():
    command = cupy_policy.format_pip_install_command(cupy_policy.CUDA13_CUPY_PACKAGES)

    assert command == 'pip install "cupy-cuda13x[ctk]==14.0.1"'


def test_ui_cupy_dialog_uses_shared_policy(monkeypatch):
    from ui import dependency_dialogs

    monkeypatch.setattr(dependency_dialogs, "_detect_cuda_driver_version", lambda: (13, 2))
    assert dependency_dialogs._get_cupy_packages() == cupy_policy.CUDA13_CUPY_PACKAGES

    monkeypatch.setattr(dependency_dialogs, "_detect_cuda_driver_version", lambda: (12, 4))
    assert dependency_dialogs._get_cupy_packages() == (cupy_policy.CUDA12_CUPY_PACKAGE,)

    monkeypatch.setattr(dependency_dialogs, "_detect_cuda_driver_version", lambda: None)
    assert dependency_dialogs._get_cupy_packages() == cupy_policy.CUDA13_CUPY_PACKAGES

    monkeypatch.setattr(dependency_dialogs, "_detect_cuda_driver_version", lambda: (10, 2))
    assert dependency_dialogs._get_cupy_packages() == ()


def test_frozen_cupy_guide_quotes_same_commands_it_runs(tmp_path, monkeypatch):
    import cupy_env
    from ui import dependency_dialogs

    target = tmp_path / "user's folder" / "env"
    monkeypatch.setattr(cupy_env, "find_compatible_python", lambda: r"C:\Python311\python.exe")
    commands = cupy_env.frozen_install_commands(cupy_policy.CUDA13_CUPY_PACKAGES, env_dir=target)
    assert commands[0] == [r"C:\Python311\python.exe", "-m", "venv", str(target)]
    assert commands[-1][0] == str(target / "Scripts" / "python.exe")
    assert list(cupy_policy.CUDA13_CUPY_PACKAGES)[0] in commands[-1]

    text = dependency_dialogs._format_powershell_commands(commands)
    assert "user''s folder" in text
    assert "New-Item" in text and "if ($LASTEXITCODE -ne 0)" in text
    assert "'cupy-cuda13x[ctk]==14.0.1'" in text
    assert "_MEI" not in text


def test_packaged_cupy_guide_invokes_sibling_cli_with_live_plan(tmp_path, monkeypatch):
    from ui import dependency_dialogs

    directory = tmp_path / "user's apps"
    directory.mkdir()
    cli = directory / "XGif-cli.exe"
    cli.touch()
    monkeypatch.setattr(sys, "executable", str(directory / "XGif.exe"))
    text = dependency_dialogs._format_powershell_commands([["stale", "-m", "venv", "old-env"]])
    quoted_cli = str(cli).replace("'", "''")
    assert text == f"& '{quoted_cli}' doctor --install-cupy"


def test_direct_cupy_install_requires_post_install_verification(monkeypatch):
    from core.dependency_checker import DependencyState, DependencyStatus
    from ui import dependency_dialogs

    monkeypatch.setattr(
        dependency_dialogs,
        "_run_cupy_install_commands",
        lambda _commands: (True, "pip ok"),
    )
    monkeypatch.setattr(
        dependency_dialogs,
        "_verify_cupy_install_status",
        lambda: DependencyStatus(
            "CuPy",
            DependencyState.MISSING,
            error_message="CuPy still cannot import",
        ),
    )

    success, message = dependency_dialogs._install_cupy_and_verify([["pip"]])

    assert not success
    assert message == "CuPy still cannot import"


def test_direct_cupy_install_reports_success_only_after_verified(monkeypatch):
    from core.dependency_checker import DependencyState, DependencyStatus
    from ui import dependency_dialogs

    monkeypatch.setattr(
        dependency_dialogs,
        "_run_cupy_install_commands",
        lambda _commands: (True, "pip ok"),
    )
    monkeypatch.setattr(
        dependency_dialogs,
        "_verify_cupy_install_status",
        lambda: DependencyStatus("CuPy", DependencyState.INSTALLED, installed_version="14.0.1"),
    )

    success, message = dependency_dialogs._install_cupy_and_verify([["pip"]])

    assert success
    assert message == "14.0.1"


def test_cupy_install_command_runner_stops_on_failed_command(monkeypatch):
    from ui import dependency_dialogs

    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1, stdout="", stderr="failed")

    monkeypatch.setattr(dependency_dialogs.subprocess, "run", fake_run)

    success, message = dependency_dialogs._run_cupy_install_commands([["first"], ["second"]])

    assert not success
    assert message == "failed"
    assert calls == [["first"]]


def test_bootstrapper_installs_from_gpu_requirements(monkeypatch):
    deps_installer, commands = _load_bootstrapper_installer(monkeypatch)
    monkeypatch.setattr(deps_installer, "_detect_cuda_major", lambda: 13)

    assert deps_installer.install_cupy()
    install_command = commands[0]
    assert "-r" in install_command
    requirements_path = install_command[install_command.index("-r") + 1]
    assert requirements_path.endswith(cupy_policy.GPU_REQUIREMENTS_FILE)
    assert "cupy-cuda12x" not in " ".join(install_command)


def test_bootstrapper_keeps_cuda12_on_cuda12_driver(monkeypatch):
    deps_installer, commands = _load_bootstrapper_installer(monkeypatch)
    monkeypatch.setattr(deps_installer, "_detect_cuda_major", lambda: 12)

    assert deps_installer.install_cupy()
    install_command = commands[0]
    assert "-r" not in install_command
    assert cupy_policy.CUDA12_CUPY_PACKAGE in install_command


def test_bootstrapper_rejects_unsupported_cuda(monkeypatch):
    deps_installer, commands = _load_bootstrapper_installer(monkeypatch)
    monkeypatch.setattr(deps_installer, "_detect_cuda_major", lambda: 10)

    assert not deps_installer.install_cupy()
    assert commands == []


def _load_bootstrapper_installer(monkeypatch):
    project_root = Path(__file__).resolve().parents[2]
    bootstrapper_dir = project_root / "BootStrapper"
    for module_name in (
        "deps_installer",
        "deps_specs",
        "download_utils",
        "extract_utils",
        "logging_setup",
        "paths",
    ):
        sys.modules.pop(module_name, None)
    monkeypatch.syspath_prepend(str(project_root))
    monkeypatch.syspath_prepend(str(bootstrapper_dir))
    deps_installer = importlib.import_module("deps_installer")

    commands = []

    def fake_stream_run(command, timeout=deps_installer.SUBPROCESS_TIMEOUT_LONG, cwd=None):
        commands.append(command)
        return 0

    monkeypatch.setattr(deps_installer, "_stream_run", fake_stream_run)
    monkeypatch.setattr(deps_installer, "log_and_ui", lambda _message: None)
    monkeypatch.setattr(deps_installer.paths, "get_venv_dir", lambda: Path("test-env"))
    monkeypatch.setattr(deps_installer.paths, "is_compatible_venv", lambda _path: True)
    return deps_installer, commands
