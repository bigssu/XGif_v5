"""CuPy doctor 설치 경로 회귀 테스트."""

from types import SimpleNamespace

from cli import doctor


def _capture_install_command(monkeypatch, cuda_version):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[2] == "pip":
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0, stdout="CuPy_OK:14.0.1", stderr="")

    monkeypatch.setattr(doctor, "_detect_cuda_version", lambda: cuda_version)
    monkeypatch.setattr(doctor.subprocess, "run", fake_run)

    assert doctor._install_cupy() == doctor.EXIT_SUCCESS
    return commands[0]


def test_install_cupy_uses_cuda13_verified_package_set(monkeypatch):
    command = _capture_install_command(monkeypatch, "13.2")

    assert command[-1:] == list(doctor.CUDA13_CUPY_PACKAGES)


def test_install_cupy_falls_back_to_cuda13_package_set(monkeypatch):
    command = _capture_install_command(monkeypatch, "")

    assert command[-1:] == list(doctor.CUDA13_CUPY_PACKAGES)
