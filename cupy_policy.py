"""CuPy optional dependency policy shared across CLI, GUI, and packaging."""

from __future__ import annotations

from collections.abc import Sequence

GPU_REQUIREMENTS_FILE = "requirements-gpu.txt"

CUDA13_CUPY_PACKAGE = "cupy-cuda13x[ctk]==14.0.1"
CUDA13_CUPY_PACKAGES = (CUDA13_CUPY_PACKAGE,)
CUDA12_CUPY_PACKAGE = "cupy-cuda12x"
CUDA11_CUPY_PACKAGE = "cupy-cuda11x"


def cupy_packages_for_cuda_major(cuda_major: int | None) -> tuple[str, ...]:
    """Return the supported CuPy package set for a CUDA driver major version."""
    if cuda_major is None or cuda_major >= 13:
        return CUDA13_CUPY_PACKAGES
    if cuda_major == 12:
        return (CUDA12_CUPY_PACKAGE,)
    if cuda_major == 11:
        return (CUDA11_CUPY_PACKAGE,)
    return ()


def cupy_packages_for_driver_version(version: tuple[int, int] | None) -> tuple[str, ...]:
    """Return CuPy packages for a detected ``(major, minor)`` CUDA driver tuple."""
    if version is None:
        return cupy_packages_for_cuda_major(None)
    major, _minor = version
    return cupy_packages_for_cuda_major(major)


def should_use_gpu_requirements(cuda_major: int | None) -> bool:
    """Return whether the verified GPU requirements file is the preferred install route."""
    return cuda_major is None or cuda_major >= 13


def quote_requirement(requirement: str) -> str:
    """Quote a requirement for shell display when special characters are present."""
    if any(ch in requirement for ch in "[]<>=!~ "):
        return f'"{requirement}"'
    return requirement


def format_pip_install_command(
    packages: Sequence[str],
    *,
    python_executable: str | None = None,
) -> str:
    """Return a user-facing pip install command for a package list."""
    pip_prefix = f'"{python_executable}" -m pip' if python_executable else "pip"
    package_args = " ".join(quote_requirement(package) for package in packages)
    return f"{pip_prefix} install {package_args}"


def format_gpu_requirements_command(
    *,
    python_executable: str | None = None,
    requirements_path: str = GPU_REQUIREMENTS_FILE,
) -> str:
    """Return a user-facing pip install command for the verified GPU requirements file."""
    pip_prefix = f'"{python_executable}" -m pip' if python_executable else "pip"
    return f'{pip_prefix} install -r "{requirements_path}"'


def format_cupy_install_hint() -> str:
    """Return concise install guidance for logs and static UI hints."""
    return (
        f"pip install -r {GPU_REQUIREMENTS_FILE} "
        f"or pip install {quote_requirement(CUDA13_CUPY_PACKAGE)}"
    )
