import os
import subprocess
import sys
import venv
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_VENV = os.path.join(PROJECT_DIR, "build_venv")
REQ_MINIMAL = os.path.join(PROJECT_DIR, "requirements_minimal.txt")
MAIN_SCRIPT = os.path.join(PROJECT_DIR, "main.py")

def setup_venv():
    """Build를 위한 깨끗한 가상환경 구축"""
    if os.path.exists(BUILD_VENV):
        print(f"Removing existing venv: {BUILD_VENV}")
        shutil.rmtree(BUILD_VENV)
    
    print("Creating clean virtual environment for build...")
    venv.create(BUILD_VENV, with_pip=True)
    
    # Pip upgrades and installation
    pip_exe = os.path.join(BUILD_VENV, "Scripts", "pip.exe") if os.name == 'nt' else os.path.join(BUILD_VENV, "bin", "pip")
    
    print("Installing minimal dependencies...")
    # pip 업그레이드는 선택적 (실패해도 계속 진행)
    try:
        subprocess.run([pip_exe, "install", "--upgrade", "pip"], check=False)
    except Exception:
        pass
    subprocess.run([pip_exe, "install", "-r", REQ_MINIMAL], check=True)
    
    # Install Nuitka for smaller build
    print("Installing Nuitka for optimized build...")
    subprocess.run([pip_exe, "install", "nuitka", "zstandard"], check=True)

def run_nuitka_build():
    """Nuitka를 사용한 최적화된 빌드 실행"""
    python_exe = os.path.join(BUILD_VENV, "Scripts", "python.exe") if os.name == 'nt' else os.path.join(BUILD_VENV, "bin", "python")
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
    python_exe = os.path.join(BUILD_VENV, "Scripts", "python.exe") if os.name == 'nt' else os.path.join(BUILD_VENV, "bin", "python")
    try:
        subprocess.run([python_exe, script, png_path, ico_path], check=True, cwd=PROJECT_DIR)
        print(f"Created {ico_path}")
        return ico_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Warning: Could not create .ico: {e}")
        return None


def run_pyinstaller_build():
    """PyInstaller를 사용한 빌드 (Nuitka가 너무 느릴 경우 대안)"""
    pip_exe = os.path.join(BUILD_VENV, "Scripts", "pip.exe") if os.name == 'nt' else os.path.join(BUILD_VENV, "bin", "pip")
    subprocess.run([pip_exe, "install", "pyinstaller"], check=True)
    
    # 앱 아이콘 .ico 생성 (빌드된 exe 아이콘용)
    icon_ico = create_ico_from_png()
    
    # ffmpeg 폴더 경로 확인
    ffmpeg_dir = os.path.join(PROJECT_DIR, "ffmpeg")
    if os.path.exists(ffmpeg_dir):
        # Windows: 세미콜론(;) 구분자, Linux/Mac: 콜론(:) 구분자
        path_separator = ";" if os.name == 'nt' else ":"
        add_data_arg = f"ffmpeg{path_separator}ffmpeg"
        print(f"Including ffmpeg folder: {ffmpeg_dir}")
    else:
        print(f"Warning: ffmpeg folder not found at {ffmpeg_dir}, skipping...")
        add_data_arg = None
    
    pyinstaller_exe = os.path.join(BUILD_VENV, "Scripts", "pyinstaller.exe")
    cmd = [
        pyinstaller_exe,
        "--noconfirm",
        "--windowed",
        "--onefile",
        "--name", "XGif",
        "--copy-metadata", "imageio",
        
        # GPU 및 선택적 의존성 제외
        "--exclude-module", "cupy",
        "--exclude-module", "scipy",
        "--exclude-module", "cv2",
        "--exclude-module", "numba",
        "--exclude-module", "llvmlite",
        
        # 개발 도구 제외
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "IPython",
        "--exclude-module", "jupyter",
        "--exclude-module", "pytest",
        "--exclude-module", "setuptools",
        "--exclude-module", "distutils",
        "--exclude-module", "email",
        "--exclude-module", "http",
        "--exclude-module", "xmlrpc",
        "--exclude-module", "unittest",
        "--exclude-module", "doctest",
        "--exclude-module", "pdb",
        
        # 최적화 옵션
        "--strip",  # 디버그 정보 제거 (크기 감소)
    ]
    
    # ffmpeg 폴더가 있으면 추가
    if add_data_arg:
        cmd.extend(["--add-data", add_data_arg])
    
    # exe 아이콘 지정
    if icon_ico and os.path.exists(icon_ico):
        cmd.extend(["--icon", icon_ico])
    
    cmd.append(MAIN_SCRIPT)
    
    print("Starting PyInstaller build process...")
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    try:
        setup_venv()
        # 기본적으로 PyInstaller 방식 사용 (빠른 빌드)
        print("\nBuild system comparison:")
        print("1. PyInstaller: Faster build, medium size")
        print("2. Nuitka: Much slower build, smaller size, faster performance")
        
        # 환경 변수로 빌드 도구 선택 가능, 기본값은 PyInstaller
        build_tool = os.environ.get("XGIF_BUILD_TOOL", "1").strip()
        if build_tool not in ["1", "2"]:
            build_tool = "1"
        
        print(f"\nUsing build tool: {'PyInstaller' if build_tool == '1' else 'Nuitka'}")
        
        if build_tool == "2":
            run_nuitka_build()
        else:
            run_pyinstaller_build()
            
        print("\nBuild finished successfully!")
    except Exception as e:
        print(f"\nBuild failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)