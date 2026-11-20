"""CuPy doctor 설치 경로 회귀 테스트."""

from types import SimpleNamespace

from cli import doctor
from core.dependency_checker import DependencyState, DependencyStatus


def _capture_install_command(monkeypatch, cuda_version):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(doctor, "_detect_cuda_version", lambda: cuda_version)
    monkeypatch.setattr(doctor, "run_install_command", fake_run)
    monkeypatch.setattr(doctor, "check_cupy", lambda *, verify_compute: DependencyStatus("CuPy", DependencyState.INSTALLED, "14.0.1"))

    assert doctor._install_cupy() == doctor.EXIT_SUCCESS
    return commands[0]


def test_install_cupy_uses_cuda13_verified_package_set(monkeypatch):
    command = _capture_install_command(monkeypatch, "13.2")

    assert command[-1:] == list(doctor.CUDA13_CUPY_PACKAGES)


def test_install_cupy_falls_back_to_cuda13_package_set(monkeypatch):
    command = _capture_install_command(monkeypatch, "")

    assert command[-1:] == list(doctor.CUDA13_CUPY_PACKAGES)


def test_frozen_install_reports_runtime_failure_after_successful_pip(monkeypatch, capsys):
    commands = [["external-python.exe", "-m", "pip", "install", "cupy-cuda12x"]]
    executed = []
    monkeypatch.setattr(doctor.sys, "frozen", True, raising=False)
    monkeypatch.setattr(doctor, "_detect_cuda_version", lambda: "12.8")
    monkeypatch.setattr(doctor, "frozen_install_commands", lambda packages: commands)
    monkeypatch.setattr(doctor, "run_install_command",
                        lambda cmd, **kwargs: executed.append(cmd) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(doctor, "check_cupy",
                        lambda *, verify_compute: DependencyStatus("CuPy", DependencyState.ERROR, error_message="DLL load failed"))

    assert doctor._install_cupy() == doctor.EXIT_DEPENDENCY
    assert executed == commands
    assert "DLL load failed" in capsys.readouterr().err
