import argparse
import os
import subprocess
import sys
import json
import re
import venv
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = PROJECT_DIR
BUILD_VENV = os.path.join(PROJECT_DIR, "build_venv")
DOT_VENV = os.path.join(PROJECT_DIR, ".venv")
REQ_MINIMAL = os.path.join(PROJECT_DIR, "requirements_minimal.txt")
MAIN_SCRIPT = os.path.join(PROJECT_DIR, "main.py")


def _get_python_exe(venv_dir):
    """Return the python executable path for a given venv directory."""
    if os.name == 'nt':
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _get_pip_exe(venv_dir):
    """Return the pip executable path for a given venv directory."""
    if os.name == 'nt':
        return os.path.join(venv_dir, "Scripts", "pip.exe")
    return os.path.join(venv_dir, "bin", "pip")


def _parse_requirements(req_file):
    """Parse requirements file and return list of (name, min_version_or_None)."""
    requirements = []
    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Match: package_name>=version or just package_name
            m = re.match(r'^([A-Za-z0-9_.-]+)\s*(?:>=\s*([0-9][0-9.]*))?\s*', line)
            if m:
                name = m.group(1).lower()
                version = m.group(2)  # None if no version specified
                requirements.append((name, version))
    return requirements


def _version_tuple(version_str):
    """Convert version string to tuple for comparison."""
    parts = []
    for p in version_str.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_dependencies(python_exe, req_file=None):
    """Check if all required packages are installed in the given Python environment.

    Returns:
        (all_ok, missing, found) where:
        - all_ok: bool - True if all dependencies are satisfied
        - missing: list of (name, required_version) tuples
        - found: list of (name, installed_version) tuples
    """
    if req_file is None:
        req_file = REQ_MINIMAL

    requirements = _parse_requirements(req_file)

    # Get installed packages via pip list --format=json
    try:
        result = subprocess.run(
            [python_exe, "-m", "pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, [(name, ver) for name, ver in requirements], []
        installed_raw = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return False, [(name, ver) for name, ver in requirements], []

    # Build lookup: lowercase name -> version
    installed = {}
    for pkg in installed_raw:
        installed[pkg["name"].lower()] = pkg["version"]

    missing = []
    found = []

    print("\n=== Dependency Check ===")
    for req_name, req_version in requirements:
        # pip normalizes names: underscores become hyphens
        lookup_names = [req_name, req_name.replace("-", "_"), req_name.replace("_", "-")]

        inst_version = None
        for lookup in lookup_names:
            if lookup in installed:
                inst_version = installed[lookup]
                break

        if inst_version is None:
            print(f"  [MISSING] {req_name}")
            missing.append((req_name, req_version))
        elif req_version and _version_tuple(inst_version) < _version_tuple(req_version):
            print(f"  [OLD]     {req_name} {inst_version} (need >={req_version})")
            missing.append((req_name, req_version))
        else:
            print(f"  [OK]      {req_name} {inst_version}")
            found.append((req_name, inst_version))

    total = len(requirements)
    print(f"\n  Found: {len(found)}/{total}, Missing: {len(missing)}")

    all_ok = len(missing) == 0
    return all_ok, missing, found


def install_missing_only(pip_exe, missing):
    """Install only the missing packages."""
    if not missing:
        return

    # Build pip install args: "name>=version" or just "name"
    specs = []
    for name, version in missing:
        if version:
            specs.append(f"{name}>={version}")
        else:
            specs.append(name)

    print(f"\nInstalling {len(specs)} missing package(s)...")
    print(f"  pip install {' '.join(specs)}")
    subprocess.run([pip_exe, "install"] + specs, check=True)


def _is_valid_venv(venv_dir):
    """Check if a venv directory exists and has a working python executable."""
    python_exe = _get_python_exe(venv_dir)
    if not os.path.isfile(python_exe):
        return False
    # Quick sanity check: can it run?
    try:
        result = subprocess.run(
            [python_exe, "-c", "import sys; print(sys.version)"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def setup_venv():
    """Build를 위한 가상환경 구축 (기존 venv 재사용 우선)"""
    global BUILD_VENV

    # Strategy 1: Try reusing existing .venv
    if _is_valid_venv(DOT_VENV):
        print(f"\nFound existing .venv at {DOT_VENV}")
        python_exe = _get_python_exe(DOT_VENV)
        all_ok, missing, found = check_dependencies(python_exe)

        if all_ok:
            print("\nReusing .venv — all dependencies satisfied!")
            BUILD_VENV = DOT_VENV
            return
        else:
            print(f"\n.venv has {len(missing)} missing package(s), installing...")
            pip_exe = _get_pip_exe(DOT_VENV)
            install_missing_only(pip_exe, missing)
            BUILD_VENV = DOT_VENV
            return

    # Strategy 2: Try reusing existing build_venv
    if _is_valid_venv(BUILD_VENV):
        print(f"\nFound existing build_venv at {BUILD_VENV}")
        python_exe = _get_python_exe(BUILD_VENV)
        all_ok, missing, found = check_dependencies(python_exe)

        if all_ok:
            print("\nReusing build_venv — all dependencies satisfied!")
            return
        else:
            print(f"\nbuild_venv has {len(missing)} missing package(s), installing...")
            pip_exe = _get_pip_exe(BUILD_VENV)
            install_missing_only(pip_exe, missing)
            return

    # Strategy 3: Create fresh build_venv
    print("\nNo usable venv found. Creating clean virtual environment for build...")
    BUILD_VENV = os.path.join(PROJECT_DIR, "build_venv")

    if os.path.exists(BUILD_VENV):
        print(f"Removing broken venv: {BUILD_VENV}")
        shutil.rmtree(BUILD_VENV)

    venv.create(BUILD_VENV, with_pip=True)

    pip_exe = _get_pip_exe(BUILD_VENV)

    # pip upgrade (optional, non-fatal)
    try:
        subprocess.run([pip_exe, "install", "--upgrade", "pip"], check=False)
    except Exception:
        pass

    print("Installing all dependencies...")
    subprocess.run([pip_exe, "install", "-r", REQ_MINIMAL], check=True)


def _ensure_build_tool(tool_name, pip_packages):
    """Ensure a build tool is installed, skip if already present."""
    python_exe = _get_python_exe(BUILD_VENV)

    # Check if the main tool is already importable
    try:
        result = subprocess.run(
            [python_exe, "-c", f"import {tool_name}; print({tool_name}.__version__)"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"  [OK] {tool_name} {version} already installed")
            return
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    print(f"  Installing {', '.join(pip_packages)}...")
    pip_exe = _get_pip_exe(BUILD_VENV)
    subprocess.run([pip_exe, "install"] + pip_packages, check=True)


def run_nuitka_build():
    """Nuitka를 사용한 최적화된 빌드 실행"""
    python_exe = _get_python_exe(BUILD_VENV)
    nuitka_cmd = [
        python_exe, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=wx",
        "--follow-imports",
        "--windows-disable-console",
        f"--output-dir={os.path.join(PROJECT_DIR, 'dist_optimized')}",
        "--onefile", # 필요 시 단일 파일 빌드 (더 느리지만 배포 용이)
        "--no-pyi-file",
        "--remove-output",
        MAIN_SCRIPT
    ]

    print("Starting Nuitka build process... (This may take a while)")
    subprocess.run(nuitka_cmd, check=True)

def create_version_file():
    """PyInstaller용 Windows exe 버전 메타데이터 파일 생성"""
    sys.path.insert(0, PROJECT_DIR)
    from core.version import APP_VERSION
    sys.path.pop(0)
    parts = APP_VERSION.split(".")
    major = int(re.match(r'\d+', parts[0]).group()) if len(parts) > 0 else 0
    minor = int(re.match(r'\d+', parts[1]).group()) if len(parts) > 1 else 0
    version_file = os.path.join(PROJECT_DIR, "file_version_info.txt")
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, 0, 0),
    prodvers=({major}, {minor}, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'XGif'),
        StringStruct('FileDescription', 'XGif Screen Recorder'),
        StringStruct('FileVersion', '{APP_VERSION}'),
        StringStruct('InternalName', 'XGif'),
        StringStruct('OriginalFilename', 'XGif.exe'),
        StringStruct('ProductName', 'XGif'),
        StringStruct('ProductVersion', '{APP_VERSION}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Version file created: {APP_VERSION}")
    return version_file


def create_ico_from_png():
    """resources/Xgif_icon.png 또는 xgif_icon.png를 .ico로 변환 (빌드용). build_venv의 Python으로 실행."""
    resources_dir = os.path.join(PROJECT_DIR, "resources")
    png_path = None
    for name in ("Xgif_icon.png", "xgif_icon.png"):
        p = os.path.join(resources_dir, name)
        if os.path.exists(p):
            png_path = p
            break
    if not png_path:
        return None
    ico_path = os.path.join(resources_dir, "xgif_icon.ico")
    script = os.path.join(PROJECT_DIR, "scripts", "create_ico.py")
    if not os.path.exists(script):
        print("Warning: scripts/create_ico.py not found, skipping icon")
        return None
    python_exe = _get_python_exe(BUILD_VENV)
    try:
        subprocess.run([python_exe, script, png_path, ico_path], check=True, cwd=PROJECT_DIR)
        print(f"Created {ico_path}")
        return ico_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Warning: Could not create .ico: {e}")
        return None


def _scan_cupy_hidden_imports(venv_dir):
    """CuPy/CuPy-backends의 모든 컴파일된 모듈(.pyd)을 스캔하여 hiddenimports 목록 생성"""
    import pathlib
    site_packages = pathlib.Path(venv_dir) / "Lib" / "site-packages"
    modules = []
    for pkg_name in ["cupy", "cupy_backends", "cupyx", "fastrlock"]:
        pkg_dir = site_packages / pkg_name
        if not pkg_dir.exists():
            continue
        for pyd in pkg_dir.rglob("*.pyd"):
            rel = pyd.relative_to(site_packages)
            mod = str(rel.with_suffix("")).replace(os.sep, ".")
            # Remove .cpXXX-win_amd64 suffix (e.g. "module.cp311-win_amd64" → "module")
            parts = mod.rsplit(".", 1)
            if len(parts) == 2 and "cp3" in parts[-1]:
                mod = parts[0]
            modules.append(mod)
    # cupy 패키지 자체와 주요 서브패키지도 포함
    for extra in ["cupy", "cupy.cuda", "cupy.cuda.runtime", "cupy._environment",
                   "cupy._core", "cupy_backends", "cupy_backends.cuda",
                   "cupy_backends.cuda.api", "cupy_backends.cuda.libs"]:
        if extra not in modules:
            modules.append(extra)
    modules.sort()
    print(f"  [CuPy] Found {len(modules)} hidden imports")
    return modules


def _generate_spec_file(icon_ico, version_file, onefile=False):
    """PyInstaller spec 파일 생성 (바이너리 필터링 포함)"""
    resources_data = os.path.join(PROJECT_ROOT, "resources")
    requirements_txt = os.path.join(PROJECT_ROOT, "requirements.txt")

    icon_line = f"icon=r'{icon_ico}'," if icon_ico and os.path.exists(icon_ico) else ""
    version_line = f"version=r'{version_file}'," if version_file and os.path.exists(version_file) else ""

    # VC++ 런타임 DLL 경로 탐색 (대상 PC에 VC++ Redist 없어도 실행되도록 번들)
    python_dir = os.path.dirname(sys.executable)
    vcrt_binaries = []
    for dll_name in ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll'):
        dll_path = os.path.join(python_dir, dll_name)
        if os.path.isfile(dll_path):
            vcrt_binaries.append((dll_path, dll_name))

    vcrt_lines = ""
    for src, name in vcrt_binaries:
        vcrt_lines += f"    (r'{src}', '.'),\n"
        print(f"  [VCRT] Bundling {name}")

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import copy_metadata, collect_submodules

# 제외할 바이너리 패턴 (wx html DLL ~0.7MB)
EXCLUDE_BINARIES = [
    'wxmsw32u_html',
]

a = Analysis(
    [r'{MAIN_SCRIPT}'],
    pathex=[r'{PROJECT_ROOT}'],
    binaries=[
{vcrt_lines}    ],
    datas=[(r'{resources_data}', 'resources'), (r'{requirements_txt}', '.')] + copy_metadata('imageio'),
    hiddenimports=[
        'comtypes',
        'pynput.keyboard',
        'pynput.mouse',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'sounddevice',
        'soundfile',
        'unittest',
        'unittest.mock',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        # GPU 및 선택적 의존성 (cupy는 외부 venv에서 로드)
        'cupy', 'cupy_backends', 'cupyx', 'fastrlock',
        'scipy', 'numba', 'llvmlite',
        # 미사용 wx 모듈 (wx.grid, wx.adv는 에디터에서 사용)
        'wx.html', 'wx.html2', 'wx.xml', 'wx.richtext',
        'wx.stc', 'wx.media', 'wx.glcanvas',
        'wx.dataview', 'wx.ribbon', 'wx.propgrid', 'wx.aui',
        # 미사용 numpy 서브패키지
        'numpy.f2py', 'numpy.testing', 'numpy.tests',
        'numpy.distutils', 'numpy.polynomial', 'numpy.ma.tests',
        # 미사용 PIL 플러그인
        'PIL.ImageTk', 'PIL.ImageQt',
        # 개발 도구
        'tkinter', 'matplotlib', 'IPython', 'jupyter',
        'pytest', 'setuptools', 'distutils',
        'xmlrpc', 'doctest', 'pdb',
        # 기타 미사용
        'pdb', 'lib2to3', 'ensurepip',
        # NOTE: email, http are needed by urllib (used by ffmpeg_installer)
    ],
    noarchive=False,
    optimize=0,
)

# 바이너리 필터링 — OpenBLAS, wx html DLL 제거
a.binaries = [
    (name, path, typ) for name, path, typ in a.binaries
    if not any(pat in os.path.basename(path).lower() for pat in EXCLUDE_BINARIES)
]

pyz = PYZ(a.pure)
"""

    if onefile:
        spec_content += f"""
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='XGif',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {icon_line}
    {version_line}
)
"""
    else:
        spec_content += f"""
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='XGif',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {icon_line}
    {version_line}
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='XGif',
)
"""

    spec_path = os.path.join(PROJECT_DIR, "XGif.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)
    return spec_path


def run_pyinstaller_build(onefile=False):
    """PyInstaller를 사용한 빌드 (spec 파일 기반, 바이너리 필터링 포함)"""
    print("\n=== Build Tool Check ===")
    _ensure_build_tool("PyInstaller", ["pyinstaller"])

    icon_ico = create_ico_from_png()
    version_file = create_version_file()

    spec_path = _generate_spec_file(icon_ico, version_file, onefile=onefile)
    print(f"  Spec file: {spec_path} ({'onefile' if onefile else 'onedir'})")

    python_exe = _get_python_exe(BUILD_VENV)
    cmd = [python_exe, "-m", "PyInstaller", "--noconfirm", spec_path]

    print("Starting PyInstaller build process...")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    subprocess.run(cmd, check=True, env=env)

def _find_iscc():
    """Inno Setup 컴파일러(ISCC.exe) 경로 자동 감지"""
    # PATH에서 찾기
    for p in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(p, "ISCC.exe")
        if os.path.isfile(candidate):
            return candidate

    # 기본 설치 경로
    for prog in [os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")]:
        if not prog:
            continue
        for name in ("Inno Setup 6", "Inno Setup 5"):
            candidate = os.path.join(prog, name, "ISCC.exe")
            if os.path.isfile(candidate):
                return candidate
    return None


def run_sign(pfx_path, pfx_password, exe_paths=None):
    """코드 서명 실행 (scripts/sign_exe.ps1 호출)"""
    sign_script = os.path.join(PROJECT_DIR, "scripts", "sign_exe.ps1")
    if not os.path.isfile(sign_script):
        print(f"[ERROR] Sign script not found: {sign_script}")
        sys.exit(1)

    if exe_paths is None:
        exe_paths = [os.path.join(PROJECT_DIR, "dist", "XGif.exe")]

    cmd = [
        "powershell.exe", "-ExecutionPolicy", "Bypass",
        "-File", sign_script,
        "-PfxPath", pfx_path,
        "-ExePaths", ",".join(exe_paths),
    ]

    # 비밀번호를 커맨드라인 대신 환경변수로 전달 (보안: tasklist로 노출 방지)
    sign_env = os.environ.copy()
    sign_env["XGIF_SIGN_PASSWORD"] = pfx_password

    print("\n=== Code Signing ===")
    subprocess.run(cmd, check=True, cwd=PROJECT_DIR, env=sign_env)


def run_installer():
    """Inno Setup 인스톨러 빌드 (ISCC.exe 호출)"""
    iss_path = os.path.join(PROJECT_DIR, "installer", "xgif_setup.iss")
    if not os.path.isfile(iss_path):
        print(f"[ERROR] Installer script not found: {iss_path}")
        sys.exit(1)

    iscc = _find_iscc()
    if not iscc:
        print("[ERROR] ISCC.exe (Inno Setup Compiler) not found.")
        print("        Install Inno Setup 6: https://jrsoftware.org/isdl.php")
        print("        Or add ISCC.exe to PATH.")
        sys.exit(1)

    print("\n=== Building Installer ===")
    print(f"  ISCC: {iscc}")
    print(f"  Script: {iss_path}")
    subprocess.run([iscc, iss_path], check=True, cwd=PROJECT_DIR)
    print("  Installer created successfully!")


def _parse_args():
    parser = argparse.ArgumentParser(description="XGif Build Script")
    parser.add_argument(
        "--tool", choices=["pyinstaller", "nuitka"], default=None,
        help="Build tool (default: pyinstaller, or set XGIF_BUILD_TOOL env var)"
    )
    parser.add_argument(
        "--sign", action="store_true",
        help="Sign EXE after build (requires signing/XGif_CodeSign.pfx)"
    )
    parser.add_argument(
        "--sign-pfx", default=os.path.join(PROJECT_DIR, "signing", "XGif_CodeSign.pfx"),
        help="PFX certificate path (default: signing/XGif_CodeSign.pfx)"
    )
    parser.add_argument(
        "--sign-password", default=os.environ.get("XGIF_SIGN_PASSWORD", ""),
        help="PFX certificate password (or set XGIF_SIGN_PASSWORD env var)"
    )
    parser.add_argument(
        "--onefile", action="store_true",
        help="Build as single EXE file (PyInstaller onefile mode)"
    )
    parser.add_argument(
        "--installer", action="store_true",
        help="Create Inno Setup installer after build (requires ISCC.exe)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    try:
        setup_venv()

        # 빌드 도구 결정: CLI 인자 > 환경 변수 > 기본값
        if args.tool:
            build_tool = "2" if args.tool == "nuitka" else "1"
        else:
            build_tool = os.environ.get("XGIF_BUILD_TOOL", "1").strip()
            if build_tool not in ["1", "2"]:
                build_tool = "1"

        print("\nBuild system comparison:")
        print("1. PyInstaller: Faster build, medium size")
        print("2. Nuitka: Much slower build, smaller size, faster performance")
        print(f"\nUsing build tool: {'PyInstaller' if build_tool == '1' else 'Nuitka'}")

        if build_tool == "2":
            print("\n=== Build Tool Check ===")
            _ensure_build_tool("nuitka", ["nuitka", "zstandard"])
            run_nuitka_build()
        else:
            run_pyinstaller_build(onefile=args.onefile)

        print("\nBuild finished successfully!")

        # 빌드 후 단계: 서명 → 인스톨러 (인스톨러에 서명된 EXE 포함)
        if build_tool == "2":
            exe_path = os.path.join(PROJECT_DIR, "dist_optimized", "XGif.exe")
        elif args.onefile:
            # onefile 모드: dist/XGif.exe
            exe_path = os.path.join(PROJECT_DIR, "dist", "XGif.exe")
        else:
            # onedir 모드: dist/XGif/XGif.exe
            exe_path = os.path.join(PROJECT_DIR, "dist", "XGif", "XGif.exe")

        # 진단용 런처 배치 파일 생성 (ASCII only — 다국어 Windows 호환)
        dist_dir = os.path.dirname(exe_path)
        diag_bat = os.path.join(dist_dir, "XGif_Debug.bat")
        bat_lines = [
            '@echo off',
            'setlocal enabledelayedexpansion',
            'title XGif - Diagnostic Launcher',
            '',
            'echo ================================================================',
            'echo   XGif Diagnostic Launcher',
            'echo ================================================================',
            'echo.',
            '',
            'cd /d "%~dp0"',
            '',
            'set "LOGFILE=%~dp0xgif_diag.log"',
            'set "PASS=0"',
            'set "WARN=0"',
            'set "FAIL=0"',
            '',
            'echo [%date% %time%] XGif Diagnostic Start > "%LOGFILE%"',
            '',
            ':: ================================================================',
            ':: STEP 1 - System Info',
            ':: ================================================================',
            'echo [1/6] System Info',
            'echo ----------------------------------------',
            'echo --- System Info --- >> "%LOGFILE%"',
            'for /f "tokens=2 delims==" %%a in (\'wmic os get Caption /value 2^>nul ^| findstr "="\') do (',
            '    echo   OS      : %%a',
            '    echo   OS: %%a >> "%LOGFILE%"',
            ')',
            'for /f "tokens=2 delims==" %%a in (\'wmic os get Version /value 2^>nul ^| findstr "="\') do (',
            '    echo   Version : %%a',
            '    echo   Version: %%a >> "%LOGFILE%"',
            ')',
            'for /f "tokens=2 delims==" %%a in (\'wmic os get OSArchitecture /value 2^>nul ^| findstr "="\') do (',
            '    echo   Arch    : %%a',
            '    echo   Arch: %%a >> "%LOGFILE%"',
            ')',
            'echo.',
            '',
            ':: ================================================================',
            ':: STEP 2 - VC++ Runtime Check',
            ':: ================================================================',
            'echo [2/6] VC++ Runtime Check',
            'echo ----------------------------------------',
            'echo --- VC++ Runtime --- >> "%LOGFILE%"',
            '',
            'set "VCRT_OK=0"',
            'if exist "%SystemRoot%\\System32\\vcruntime140.dll" (',
            '    echo   [OK] vcruntime140.dll',
            '    set "VCRT_OK=1"',
            ') else (',
            '    echo   [FAIL] vcruntime140.dll - MISSING!',
            '    echo          Download: https://aka.ms/vs/17/release/vc_redist.x64.exe',
            '    echo   [FAIL] vcruntime140.dll missing >> "%LOGFILE%"',
            ')',
            'if exist "%SystemRoot%\\System32\\vcruntime140_1.dll" (',
            '    echo   [OK] vcruntime140_1.dll',
            ') else (',
            '    echo   [WARN] vcruntime140_1.dll - MISSING',
            '    echo   [WARN] vcruntime140_1.dll missing >> "%LOGFILE%"',
            ')',
            '',
            'if "!VCRT_OK!"=="1" (',
            '    reg query "HKLM\\SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64" /v Major >nul 2>&1',
            '    if not errorlevel 1 (',
            '        echo   [OK] VC++ 2015-2022 Redistributable x64 installed',
            '        echo   [OK] VC++ 2015-2022 x64 >> "%LOGFILE%"',
            '    )',
            '    set /a PASS+=1',
            ') else (',
            '    set /a FAIL+=1',
            ')',
            'echo.',
            '',
            ':: ================================================================',
            ':: STEP 3 - GPU / CUDA Check',
            ':: ================================================================',
            'echo [3/6] GPU / CUDA Check',
            'echo ----------------------------------------',
            'echo --- GPU Check --- >> "%LOGFILE%"',
            '',
            'nvidia-smi >nul 2>&1',
            'if not errorlevel 1 (',
            '    for /f "tokens=*" %%g in (\'nvidia-smi --query-gpu^=name --format^=csv^,noheader 2^>nul\') do (',
            '        echo   [OK] GPU: %%g',
            '        echo   [OK] GPU: %%g >> "%LOGFILE%"',
            '    )',
            '    for /f "tokens=*" %%d in (\'nvidia-smi --query-gpu^=driver_version --format^=csv^,noheader 2^>nul\') do (',
            '        echo   Driver: %%d',
            '        echo   Driver: %%d >> "%LOGFILE%"',
            '    )',
            '    for /f "tokens=*" %%m in (\'nvidia-smi --query-gpu^=memory.total --format^=csv^,noheader 2^>nul\') do (',
            '        echo   VRAM  : %%m',
            '        echo   VRAM: %%m >> "%LOGFILE%"',
            '    )',
            '    for /f "tokens=2 delims=:" %%v in (\'nvidia-smi 2^>nul ^| findstr /C:"CUDA Version"\') do (',
            '        echo   CUDA  : %%v',
            '        echo   CUDA: %%v >> "%LOGFILE%"',
            '    )',
            '    set /a PASS+=1',
            ') else (',
            '    echo   [INFO] NVIDIA GPU not detected (CPU mode will be used)',
            '    echo   [INFO] No NVIDIA GPU >> "%LOGFILE%"',
            ')',
            'echo.',
            '',
            ':: ================================================================',
            ':: STEP 4 - CuPy External Env Check',
            ':: ================================================================',
            'echo [4/6] CuPy External Env Check',
            'echo ----------------------------------------',
            'echo --- CuPy Env Check --- >> "%LOGFILE%"',
            '',
            'set "CUPY_ENV=%LOCALAPPDATA%\\XGif\\env"',
            'if exist "!CUPY_ENV!\\Scripts\\python.exe" (',
            '    echo   [OK] External env found: !CUPY_ENV!',
            '    echo   [OK] External env: !CUPY_ENV! >> "%LOGFILE%"',
            '    for /f "tokens=*" %%v in (\'""!CUPY_ENV!\\Scripts\\python.exe"" -c "import cupy; print(cupy.__version__)" 2^>nul\') do (',
            '        echo   [OK] CuPy %%v installed',
            '        echo   [OK] CuPy %%v >> "%LOGFILE%"',
            '    )',
            '    if errorlevel 1 (',
            '        echo   [INFO] CuPy not installed in external env',
            '        echo   [INFO] CuPy not in env >> "%LOGFILE%"',
            '    )',
            '    set /a PASS+=1',
            ') else (',
            '    echo   [INFO] External env not created yet (install CuPy via app)',
            '    echo   [INFO] External env not found >> "%LOGFILE%"',
            ')',
            'echo.',
            '',
            ':: ================================================================',
            ':: STEP 5 - FFmpeg Check',
            ':: ================================================================',
            'echo [5/6] FFmpeg Check',
            'echo ----------------------------------------',
            'echo --- FFmpeg Check --- >> "%LOGFILE%"',
            '',
            'where ffmpeg >nul 2>&1',
            'if not errorlevel 1 (',
            '    echo   [OK] FFmpeg found in PATH',
            '    echo   [OK] FFmpeg in PATH >> "%LOGFILE%"',
            '    set /a PASS+=1',
            ') else (',
            '    if exist "%~dp0ffmpeg\\ffmpeg.exe" (',
            '        echo   [OK] Local ffmpeg found',
            '        echo   [OK] Local ffmpeg >> "%LOGFILE%"',
            '        set /a PASS+=1',
            '    ) else (',
            '        echo   [INFO] FFmpeg not found (app will download automatically)',
            '        echo   [INFO] FFmpeg not found >> "%LOGFILE%"',
            '    )',
            ')',
            'echo.',
            '',
            ':: ================================================================',
            ':: STEP 6 - XGif.exe Check',
            ':: ================================================================',
            'echo [6/6] XGif.exe Check',
            'echo ----------------------------------------',
            'echo --- EXE Check --- >> "%LOGFILE%"',
            '',
            'if not exist "%~dp0XGif.exe" (',
            '    echo   [FAIL] XGif.exe not found!',
            '    echo          Place this .bat in the same folder as XGif.exe',
            '    echo   [FAIL] XGif.exe not found >> "%LOGFILE%"',
            '    set /a FAIL+=1',
            '    goto :summary',
            ')',
            '',
            'echo   [OK] XGif.exe found',
            'echo   [OK] XGif.exe found >> "%LOGFILE%"',
            'for %%F in ("%~dp0XGif.exe") do (',
            '    set "FSIZE=%%~zF"',
            ')',
            'set /a FSIZE_MB=!FSIZE! / 1048576',
            'echo   Size: !FSIZE! bytes (!FSIZE_MB! MB)',
            'echo   Size: !FSIZE! bytes >> "%LOGFILE%"',
            'set /a PASS+=1',
            '',
            ':: Detect packaging mode',
            'if exist "%~dp0_internal" (',
            '    set "PKG_MODE=Directory (onedir)"',
            ') else (',
            '    set "PKG_MODE=Single EXE (onefile)"',
            ')',
            'echo   Mode: !PKG_MODE!',
            'echo   Mode: !PKG_MODE! >> "%LOGFILE%"',
            'echo.',
            '',
            ':: ================================================================',
            ':: Summary',
            ':: ================================================================',
            ':summary',
            'echo ================================================================',
            'echo   Diagnostic Summary',
            'echo ----------------------------------------------------------------',
            'echo   PASS: !PASS!   WARN: !WARN!   FAIL: !FAIL!',
            'echo   PASS: !PASS!  WARN: !WARN!  FAIL: !FAIL! >> "%LOGFILE%"',
            '',
            'if "!FAIL!" GTR "0" (',
            '    echo   Status: Issues found - see above for details',
            '    echo   Status: ISSUES >> "%LOGFILE%"',
            ') else if "!WARN!" GTR "0" (',
            '    echo   Status: OK with warnings',
            '    echo   Status: OK with warnings >> "%LOGFILE%"',
            ') else (',
            '    echo   Status: All checks passed',
            '    echo   Status: ALL PASS >> "%LOGFILE%"',
            ')',
            'echo ================================================================',
            'echo.',
            '',
            'if not exist "%~dp0XGif.exe" (',
            '    echo   Cannot launch - XGif.exe not found.',
            '    pause',
            '    exit /b 1',
            ')',
            '',
            'set /p LAUNCH="  Launch XGif now? (Y/N): "',
            'if /i not "%LAUNCH%"=="Y" (',
            '    echo.',
            '    echo   Log saved: %LOGFILE%',
            '    pause',
            '    exit /b 0',
            ')',
            '',
            'echo.',
            'echo   Launching XGif... (errors will be shown here)',
            'echo ----------------------------------------',
            'echo --- Launch --- >> "%LOGFILE%"',
            'echo   Time: %date% %time% >> "%LOGFILE%"',
            'echo.',
            '',
            '"%~dp0XGif.exe" 2> "%~dp0xgif_stderr.log"',
            'set "EXIT_CODE=!errorlevel!"',
            '',
            'echo   Exit code: !EXIT_CODE! >> "%LOGFILE%"',
            '',
            'if "!EXIT_CODE!"=="0" goto :normal_exit',
            '',
            'echo.',
            'echo ================================================================',
            'echo   [ERROR] XGif exited abnormally (code: !EXIT_CODE!)',
            'echo ================================================================',
            'echo.',
            '',
            'if "!EXIT_CODE!"=="-1073741515" (',
            '    echo   Cause: DLL not found [0xC0000135]',
            '    echo   Fix:   Install VC++ Runtime from https://aka.ms/vs/17/release/vc_redist.x64.exe',
            '    echo   0xC0000135 DLL not found >> "%LOGFILE%"',
            '    goto :show_stderr',
            ')',
            'if "!EXIT_CODE!"=="-1073741701" (',
            '    echo   Cause: DLL init failure [0xC000007B] - 32/64bit mismatch or corrupt DLL',
            '    echo   Fix:   Reinstall VC++ Redistributable',
            '    echo   0xC000007B DLL init fail >> "%LOGFILE%"',
            '    goto :show_stderr',
            ')',
            'if "!EXIT_CODE!"=="-1073740791" (',
            '    echo   Cause: Stack overflow [0xC00000FD]',
            '    echo   0xC00000FD Stack overflow >> "%LOGFILE%"',
            '    goto :show_stderr',
            ')',
            'if "!EXIT_CODE!"=="-1073741819" (',
            '    echo   Cause: Access violation [0xC0000005]',
            '    echo   0xC0000005 Access violation >> "%LOGFILE%"',
            '    goto :show_stderr',
            ')',
            'echo   Unknown exit code: !EXIT_CODE!',
            'echo   Common causes:',
            'echo     - Windows Defender blocked the exe (check quarantine)',
            'echo     - Missing VC++ Redistributable',
            'echo     - CUDA DLL load failure (GPU driver mismatch)',
            'echo     - Temp folder access denied',
            'goto :show_stderr',
            '',
            ':show_stderr',
            'echo.',
            'if not exist "%~dp0xgif_stderr.log" goto :done',
            'for %%S in ("%~dp0xgif_stderr.log") do (',
            '    if %%~zS GTR 0 (',
            '        echo   === stderr output ===',
            '        type "%~dp0xgif_stderr.log"',
            '        echo.',
            '        echo   --- stderr --- >> "%LOGFILE%"',
            '        type "%~dp0xgif_stderr.log" >> "%LOGFILE%"',
            '    )',
            ')',
            'goto :done',
            '',
            ':normal_exit',
            'echo   XGif exited normally (code: 0)',
            'echo   Normal exit >> "%LOGFILE%"',
            'goto :done',
            '',
            ':done',
            'echo.',
            'echo ================================================================',
            'echo   Done. Log saved: %LOGFILE%',
            'echo ================================================================',
            'pause',
            'exit /b !EXIT_CODE!',
        ]
        with open(diag_bat, "w", encoding="ascii", newline="") as f:
            for line in bat_lines:
                f.write(line + "\r\n")
        print(f"  Diagnostic launcher: {diag_bat}")

        if args.sign:
            run_sign(args.sign_pfx, args.sign_password, [exe_path])

        if args.installer:
            run_installer()

            # 인스톨러 EXE도 서명
            if args.sign:
                sys.path.insert(0, PROJECT_DIR)
                from core.version import APP_VERSION
                sys.path.pop(0)
                installer_exe = os.path.join(
                    PROJECT_DIR, "dist", f"XGif_Setup_{APP_VERSION}.exe"
                )
                if os.path.isfile(installer_exe):
                    run_sign(args.sign_pfx, args.sign_password, [installer_exe])

        print("\n=== All done! ===")

    except Exception as e:
        print(f"\nBuild failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
