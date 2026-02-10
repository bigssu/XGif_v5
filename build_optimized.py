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


def _generate_spec_file(icon_ico, version_file):
    """PyInstaller spec 파일 생성 (바이너리 필터링 포함)"""
    resources_data = os.path.join(PROJECT_ROOT, "resources")

    icon_line = f"icon=r'{icon_ico}'," if icon_ico and os.path.exists(icon_ico) else ""
    version_line = f"version=r'{version_file}'," if version_file and os.path.exists(version_file) else ""

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import copy_metadata

# 제외할 바이너리 패턴 (wx html DLL ~0.7MB)
EXCLUDE_BINARIES = [
    'wxmsw32u_html',
]

a = Analysis(
    [r'{MAIN_SCRIPT}'],
    pathex=[r'{PROJECT_ROOT}'],
    binaries=[],
    datas=[(r'{resources_data}', 'resources')] + copy_metadata('imageio'),
    hiddenimports=[
        'comtypes',
        'pynput.keyboard',
        'pynput.mouse',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'sounddevice',
        'soundfile',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        # GPU 및 선택적 의존성
        'cupy', 'scipy', 'cv2', 'numba', 'llvmlite',
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
        'xmlrpc', 'unittest', 'doctest', 'pdb',
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='XGif',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
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
    spec_path = os.path.join(PROJECT_DIR, "XGif.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)
    return spec_path


def run_pyinstaller_build():
    """PyInstaller를 사용한 빌드 (spec 파일 기반, 바이너리 필터링 포함)"""
    print("\n=== Build Tool Check ===")
    _ensure_build_tool("PyInstaller", ["pyinstaller"])

    icon_ico = create_ico_from_png()
    version_file = create_version_file()

    spec_path = _generate_spec_file(icon_ico, version_file)
    print(f"  Spec file: {spec_path}")

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
        "-Password", pfx_password,
        "-ExePaths", ",".join(exe_paths),
    ]

    print(f"\n=== Code Signing ===")
    subprocess.run(cmd, check=True, cwd=PROJECT_DIR)


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

    print(f"\n=== Building Installer ===")
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
            run_pyinstaller_build()

        print("\nBuild finished successfully!")

        # 빌드 후 단계: 서명 → 인스톨러 (인스톨러에 서명된 EXE 포함)
        exe_path = os.path.join(PROJECT_DIR, "dist", "XGif.exe")

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
