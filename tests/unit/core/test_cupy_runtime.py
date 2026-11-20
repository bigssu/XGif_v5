import builtins
import os
import site as python_site
import sys
from types import SimpleNamespace

import pytest
import numpy as np

from core import dependency_checker, utils
from core.dependency_checker import DependencyState


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (ModuleNotFoundError("No module named 'cupy'", name="cupy"), DependencyState.MISSING),
        (ModuleNotFoundError("No module named 'cupy_backends'", name="cupy_backends"), DependencyState.ERROR),
        (ImportError("DLL load failed: cudart64_13.dll"), DependencyState.ERROR),
    ],
)
def test_import_failures_retain_the_actual_reason(monkeypatch, error, expected_state):
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        if name == "cupy":
            raise error
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_module)
    status = dependency_checker.check_cupy()
    assert status.state == expected_state
    assert str(error) in status.error_message


def test_recheck_keeps_loaded_native_modules_and_requires_a_device(monkeypatch):
    class DeviceArray(np.ndarray):
        def get(self):
            return self

    devices = []
    runtime = SimpleNamespace(getDeviceCount=lambda: len(devices))
    cupy = SimpleNamespace(__version__="14.0.1", cuda=SimpleNamespace(runtime=runtime),
                           int32=np.int32, asarray=lambda *a, **kw: np.array([1]).view(DeviceArray))
    monkeypatch.setitem(sys.modules, "cupy", cupy)
    monkeypatch.setitem(sys.modules, "cupy.cuda.runtime", runtime)

    status = dependency_checker.check_cupy()
    assert status.state == DependencyState.ERROR
    assert "getDeviceCount" in status.error_message
    devices.append(0)
    assert dependency_checker.check_cupy().state == DependencyState.INSTALLED
    assert sys.modules["cupy.cuda.runtime"] is runtime


def test_post_install_requires_successful_gpu_computation(monkeypatch):
    from ui import dependency_dialogs

    runtime = SimpleNamespace(getDeviceCount=lambda: 1)
    cupy = SimpleNamespace(__version__="14.0.1", cuda=SimpleNamespace(runtime=runtime), int32=np.int32)
    monkeypatch.setitem(sys.modules, "cupy", cupy)

    class DeviceArray:
        def __add__(self, other):
            assert other == 1
            return self

        def get(self):
            raise RuntimeError("nvrtc DLL missing")

    cupy.asarray = lambda *args, **kwargs: DeviceArray()
    from core import gpu_utils
    monkeypatch.setattr(gpu_utils, "_cupy_status", None)
    monkeypatch.setattr(gpu_utils, "_cp", None)
    assert not gpu_utils.is_cupy_available()
    assert dependency_checker.check_cupy().state == DependencyState.ERROR
    failed = dependency_dialogs._verify_cupy_install_status()
    assert failed.state == DependencyState.ERROR
    assert "nvrtc DLL missing" in failed.error_message
    monkeypatch.setattr(DeviceArray, "get", lambda self: np.array([2]))
    assert not gpu_utils.is_cupy_available()
    assert dependency_dialogs._verify_cupy_install_status().state == DependencyState.INSTALLED
    assert gpu_utils.is_cupy_available()


def test_frozen_env_is_rechecked_after_install_without_changing_path(monkeypatch, tmp_path):
    import cupy_env

    env = tmp_path / "env"
    sibling = tmp_path / "compatible"
    env.mkdir()
    (env / "pyvenv.cfg").write_text("version = 3.12.4", encoding="utf-8")
    site = sibling / "Lib" / "site-packages"
    handles = {}

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(cupy_env, "select_cupy_env", lambda: sibling)
    monkeypatch.setattr(cupy_env, "legacy_env_dir", lambda: env)
    monkeypatch.setattr(cupy_env, "env_matches_runtime", lambda candidate: candidate == sibling and site.is_dir())
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(python_site, "PREFIXES", [])
    monkeypatch.setattr(utils, "_cupy_dll_handles", handles)
    monkeypatch.setattr(os, "add_dll_directory", lambda _: object(), raising=False)
    original_path = os.environ.get("PATH")

    status = dependency_checker.check_cupy()
    assert status.state == DependencyState.ERROR
    assert str(env) in status.error_message
    assert "configured Python 3.12.4" in status.error_message
    assert f"CPython {sys.version_info.major}.{sys.version_info.minor}" in status.error_message
    site.mkdir(parents=True)
    utils.ensure_system_site_packages()
    cuda = site / "nvidia" / "cu13" / "bin" / "x86_64"
    cuda.mkdir(parents=True)
    utils.ensure_system_site_packages()
    handle = handles[cuda]
    utils.ensure_system_site_packages()
    assert handles[cuda] is handle
    assert sys.path.count(str(site)) == 1
    assert python_site.PREFIXES.count(str(sibling)) == 1
    assert os.environ.get("PATH") == original_path


def test_recheck_dialog_reports_native_error(monkeypatch):
    from ui import dependency_dialogs

    detail = "import cupy: DLL load failed: cudart64_13.dll"
    status = dependency_checker.DependencyStatus("CuPy", DependencyState.ERROR, error_message=detail)
    monkeypatch.setattr(dependency_dialogs, "_verify_cupy_install_status", lambda: status)
    messages = []
    monkeypatch.setattr(dependency_dialogs.wx, "MessageBox", lambda message, *_: messages.append(message))
    dependency_dialogs.CuPyInstallGuideDialog._on_recheck(None, None)
    assert detail in messages[0]


def test_editor_probe_keeps_environment_diagnostic(monkeypatch):
    from editor.core import editor_gpu_utils

    def incompatible():
        raise RuntimeError("CuPy environment requires CPython 3.11")

    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr(utils, "ensure_system_site_packages", incompatible)
    monkeypatch.setattr(editor_gpu_utils, "_gpu_init_error", None)
    assert not editor_gpu_utils._check_gpu()
    assert "requires CPython 3.11" in editor_gpu_utils.get_gpu_init_error()


def test_editor_reports_cuda_error_on_detected_hardware(monkeypatch):
    from editor.ui import editor_main_window_wx as editor

    detail = "CUDA driver initialization failed"
    monkeypatch.setattr(editor.gpu_utils, "is_gpu_available", lambda: False)
    monkeypatch.setattr(editor.gpu_utils, "has_nvidia_gpu_hardware", lambda: True)
    monkeypatch.setattr(editor.gpu_utils, "get_gpu_init_error", lambda: detail)
    messages = []
    monkeypatch.setattr(editor.wx, "MessageBox", lambda text, *_: messages.append(text))
    translations = SimpleNamespace(tr=lambda key, **args: args.get("detail", key))
    editor.MainWindow._show_gpu_info(SimpleNamespace(_translations=translations))
    assert messages == [detail]
