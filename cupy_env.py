"""Select a Windows CuPy environment compatible with the packaged CPython runtime."""

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

PYTHON_VERSION = sys.version_info[:2]
PYTHON_BITS = struct.calcsize("P") * 8


def legacy_env_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "XGif" / "env"


def _probe(command, *, base=False):
    script = (
        "import json,struct,sys; "
        "print(json.dumps([sys.implementation.name, list(sys.version_info[:2]), "
        "struct.calcsize('P')*8, sys.prefix, sys._base_executable]))"
    )
    if base:
        script = "import ensurepip,venv; " + script
    try:
        result = subprocess.run(
            [*command, "-I", *(["-S"] if base else []), "-c", script],
            capture_output=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0:
            implementation, version, bits, prefix, executable = json.loads(result.stdout)
            if implementation == "cpython":
                return tuple(version), bits, Path(prefix), Path(executable)
    except (OSError, subprocess.TimeoutExpired, TypeError, ValueError):
        pass
    return None


def env_matches_runtime(path, *, version=PYTHON_VERSION, bits=PYTHON_BITS) -> bool:
    path = Path(path)
    exe = path / "Scripts" / "python.exe"
    if not (path / "pyvenv.cfg").is_file() or not exe.is_file():
        return False
    info = _probe([str(exe)])
    return bool(info and info[:2] == (version, bits) and info[2] == path)


CUPY_DEVICE_PROBE = (
    "import cupy as cp\nn = cp.cuda.runtime.getDeviceCount()\n"
    "if n and (cp.asarray([1]) + 1).get().item() != 2:\n"
    "    raise RuntimeError('CUDA calculation failed')\nprint(n)"
)


def _has_working_cupy(env: Path) -> bool:
    try:
        result = subprocess.run(
            [str(env / "Scripts" / "python.exe"), "-I", "-c", CUPY_DEVICE_PROBE],
            capture_output=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0 and int(result.stdout.strip()) > 0
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False


def select_cupy_env(*, version=PYTHON_VERSION, bits=PYTHON_BITS) -> Path:
    legacy = legacy_env_dir()
    sibling = legacy.with_name(f"env-cp{version[0]}{version[1]}-{bits}")
    if env_matches_runtime(sibling, version=version, bits=bits):
        # A failed pip install can leave a compatible but empty versioned venv.
        package = Path("Lib/site-packages/cupy/__init__.py")
        if (legacy / package).is_file() and env_matches_runtime(legacy, version=version, bits=bits):
            if not (sibling / package).is_file():
                return legacy
            if not _has_working_cupy(sibling) and _has_working_cupy(legacy):
                return legacy
        return sibling
    if not os.path.lexists(legacy) or env_matches_runtime(legacy, version=version, bits=bits):
        return legacy
    return sibling


def find_compatible_python():
    """Return the verified base executable, including when PATH points into a venv."""
    launcher = shutil.which("py")
    version = ".".join(map(str, PYTHON_VERSION))
    candidates = [[launcher, f"-{version}"]] if launcher else []
    for name in ("python", "python3"):
        exe = shutil.which(name)
        if exe:
            candidates.append([exe])
    local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    exe = local / "Programs" / "Python" / f"Python{version.replace('.', '')}" / "python.exe"
    if exe.is_file():
        candidates.append([str(exe)])
    for candidate in candidates:
        info = _probe(candidate, base=True)
        if info and info[:2] == (PYTHON_VERSION, PYTHON_BITS) and info[3].is_file():
            return str(info[3])
    return None


class MissingCompatiblePython(RuntimeError):
    pass


def frozen_install_commands(pip_args, *, env_dir=None):
    target = Path(env_dir) if env_dir is not None else select_cupy_env()
    exe = str(target / "Scripts" / "python.exe")
    commands = []
    if not env_matches_runtime(target):
        if os.path.lexists(target):
            raise RuntimeError(f"Cannot use the existing Python environment: {target}")
        base = find_compatible_python()
        if not base:
            version = ".".join(map(str, PYTHON_VERSION))
            raise MissingCompatiblePython(f"Install CPython {version} ({PYTHON_BITS}-bit) and restart XGif.")
        commands.append([base, "-m", "venv", str(target)])
    elif not (target / "Lib" / "site-packages" / "pip" / "__main__.py").is_file():
        commands.append([exe, "-m", "ensurepip", "--upgrade"])
    commands.append([exe, "-m", "pip", "install", "--upgrade", "pip>=24.0", "--quiet"])
    commands.append([exe, "-m", "pip", "install", *pip_args, "--no-cache-dir"])
    return commands


def run_install_command(command, **kwargs):
    if command[1:3] == ["-m", "venv"]:
        # Claim a fresh path before venv can write into a directory created since planning.
        target = Path(command[3])
        target.mkdir(parents=True, exist_ok=False)
        claimed = target.stat()
        created = False
        try:
            result = subprocess.run(command, **kwargs)
            created = result.returncode == 0
            return result
        finally:
            if not created and target.exists() and os.path.samestat(claimed, target.stat()):
                shutil.rmtree(target)
    if getattr(sys, "frozen", False) and command[1:3] in (["-m", "pip"], ["-m", "ensurepip"]):
        env_dir = Path(command[0]).parent.parent
        if not env_matches_runtime(env_dir):
            raise RuntimeError(f"Python environment changed before installation: {env_dir}")
    return subprocess.run(command, **kwargs)
