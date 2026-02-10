"""
공통 유틸리티 모듈
중복 코드를 제거하고 재사용 가능한 함수들을 제공
"""

import os
import sys
import logging
import shutil
import stat
import time
import gc
import subprocess
from typing import Tuple, Optional
import numpy as np
from PIL import Image, ImageFont

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 리소스 경로 유틸리티 (PyInstaller frozen 환경 대응)
# ═══════════════════════════════════════════════════════════════

def get_resource_path(relative_path: str) -> str:
    """리소스 파일의 절대 경로 반환 (frozen/개발 환경 모두 대응)"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def ensure_system_site_packages():
    """frozen 앱에서 시스템 Python site-packages를 sys.path에 추가.

    PyInstaller 빌드에서 제외된 패키지(CuPy 등)를
    시스템 Python에서 찾을 수 있게 합니다.
    소스 실행 시에는 아무 동작도 하지 않습니다.
    """
    _log = logging.getLogger(__name__)

    if not getattr(sys, 'frozen', False):
        return

    if getattr(sys, '_xgif_site_packages_added', False):
        return

    import shutil
    import subprocess

    python_exe = shutil.which('python') or shutil.which('python3')
    if not python_exe:
        _log.debug("[site-packages] system python not found in PATH")
        return

    _log.debug("[site-packages] system python: %s", python_exe)

    try:
        # site-packages + stdlib(Lib, DLLs) 경로를 한꺼번에 수집
        _script = (
            'import site, sysconfig, os, sys;'
            'ps = list(site.getsitepackages());'
            'ps.append(sysconfig.get_path("stdlib"));'
            'ps.append(sysconfig.get_path("purelib"));'
            'ps.append(sysconfig.get_path("platlib"));'
            'dll = os.path.join(sys.prefix, "DLLs");'
            'ps.append(dll) if os.path.isdir(dll) else None;'
            'print(chr(10).join(dict.fromkeys(ps)))'
        )
        result = subprocess.run(
            [python_exe, '-c', _script],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        added = []
        for p in result.stdout.strip().splitlines():
            if p and os.path.isdir(p) and p not in sys.path:
                sys.path.append(p)
                added.append(p)
        sys._xgif_site_packages_added = True
        if added:
            _log.info("[site-packages] added %d paths: %s", len(added), added)
            # frozen numpy는 submodule(numpy.testing 등)이 빠져 있을 수 있음
            # 시스템 numpy 경로를 numpy.__path__에 추가하여 CuPy가 필요로 하는
            # submodule을 찾을 수 있게 함
            _patch_frozen_numpy_path(added, _log)
        else:
            _log.debug("[site-packages] no new paths to add (stderr=%s)",
                       result.stderr.strip()[:200] if result.stderr else "")
    except Exception as exc:
        _log.debug("[site-packages] failed: %s", exc)


def _patch_frozen_numpy_path(site_dirs, _log):
    """frozen numpy에 시스템 numpy 경로를 추가 (numpy.testing 등 접근 가능하게)"""
    try:
        import numpy
        for sp in site_dirs:
            np_dir = os.path.join(sp, 'numpy')
            if os.path.isdir(np_dir) and np_dir not in numpy.__path__:
                numpy.__path__.append(np_dir)
                _log.debug("[site-packages] patched numpy.__path__ += %s", np_dir)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# 위치 계산 유틸리티
# ═══════════════════════════════════════════════════════════════

def calculate_overlay_position(
    frame_width: int,
    frame_height: int,
    overlay_width: int,
    overlay_height: int,
    position: str = 'bottom-right',
    margin: int = 10
) -> Tuple[int, int]:
    """오버레이 위치 계산 (웹캠, 워터마크, 키보드 공통)
    
    Args:
        frame_width: 프레임 너비
        frame_height: 프레임 높이
        overlay_width: 오버레이 너비
        overlay_height: 오버레이 높이
        position: 위치 ('top-left', 'top-right', 'bottom-left', 'bottom-right', 'center', 'top', 'bottom')
        margin: 여백 (픽셀)
        
    Returns:
        Tuple[int, int]: (x, y) 좌표
    """
    # 세로 위치
    if 'top' in position:
        y = margin
    elif 'bottom' in position:
        y = frame_height - overlay_height - margin
    else:  # center
        y = (frame_height - overlay_height) // 2
    
    # 가로 위치
    if 'left' in position:
        x = margin
    elif 'right' in position:
        x = frame_width - overlay_width - margin
    else:  # center
        x = (frame_width - overlay_width) // 2
    
    # 클리핑 (프레임 경계 내로)
    x = max(0, min(x, frame_width - overlay_width))
    y = max(0, min(y, frame_height - overlay_height))
    
    return (x, y)


# ═══════════════════════════════════════════════════════════════
# 알파 블렌딩 유틸리티
# ═══════════════════════════════════════════════════════════════

def apply_alpha_blend(
    background: np.ndarray,
    overlay: np.ndarray,
    x: int,
    y: int,
    opacity: float = 1.0
) -> np.ndarray:
    """알파 블렌딩을 사용하여 오버레이를 배경에 합성
    
    Args:
        background: 배경 프레임 (BGR/RGB)
        overlay: 오버레이 이미지 (RGB 또는 RGBA)
        x: 오버레이 X 좌표
        y: 오버레이 Y 좌표
        opacity: 투명도 (0.0 ~ 1.0)
        
    Returns:
        np.ndarray: 블렌딩된 프레임
    """
    try:
        overlay_h, overlay_w = overlay.shape[:2]
        bg_h, bg_w = background.shape[:2]
        
        # 영역 클리핑
        x = max(0, min(x, bg_w - overlay_w))
        y = max(0, min(y, bg_h - overlay_h))
        
        # ROI 추출
        roi = background[y:y+overlay_h, x:x+overlay_w]
        
        # ROI와 오버레이 크기가 다르면 스킵
        if roi.shape[:2] != overlay.shape[:2]:
            return background
        
        # 알파 채널 처리
        if overlay.shape[2] == 4:  # RGBA
            alpha = overlay[:, :, 3:4] / 255.0 * opacity
            rgb = overlay[:, :, :3]
            
            if roi.shape[2] == 3:
                blended = (roi * (1.0 - alpha) + rgb * alpha).astype(np.uint8)
                background[y:y+overlay_h, x:x+overlay_w] = blended
        else:  # RGB
            # 투명도만 적용
            blended = (roi * (1.0 - opacity) + overlay * opacity).astype(np.uint8)
            background[y:y+overlay_h, x:x+overlay_w] = blended
        
        return background
        
    except (ValueError, IndexError) as e:
        logger.debug(f"알파 블렌딩 실패: {e}")
        return background


# ═══════════════════════════════════════════════════════════════
# 폰트 로드 유틸리티
# ═══════════════════════════════════════════════════════════════

def load_system_font(font_size: int, preferred_fonts: Optional[list] = None) -> ImageFont.FreeTypeFont:
    """시스템 폰트 로드 (우선순위 순으로 시도)
    
    Args:
        font_size: 폰트 크기
        preferred_fonts: 선호 폰트 리스트 (경로 또는 이름)
        
    Returns:
        ImageFont: 로드된 폰트 (실패 시 기본 폰트)
    """
    # 기본 폰트 리스트 (비표준 Windows 설치 경로 대응)
    windir = os.environ.get('WINDIR', 'C:\\Windows')
    fonts_dir = os.path.join(windir, 'Fonts')
    default_fonts = [
        os.path.join(fonts_dir, "arial.ttf"),
        os.path.join(fonts_dir, "calibri.ttf"),
        os.path.join(fonts_dir, "consola.ttf"),
        os.path.join(fonts_dir, "segoeui.ttf"),
    ]
    
    # 선호 폰트가 있으면 앞에 추가
    fonts_to_try = (preferred_fonts or []) + default_fonts
    
    # 순서대로 시도
    for font_path in fonts_to_try:
        try:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, font_size)
        except (OSError, IOError):
            continue
    
    # 모두 실패하면 기본 폰트
    logger.warning(f"시스템 폰트를 찾을 수 없음, 기본 폰트 사용")
    return ImageFont.load_default()


# ═══════════════════════════════════════════════════════════════
# 해상도 파싱 유틸리티
# ═══════════════════════════════════════════════════════════════

def parse_resolution(text: str) -> Optional[Tuple[int, int]]:
    """해상도 문자열 파싱
    
    다양한 형식 지원:
    - "1920x1080"
    - "1920 x 1080"
    - "1920 × 1080"
    - "1920*1080"
    
    Args:
        text: 해상도 문자열
        
    Returns:
        Tuple[int, int]: (width, height) or None if parsing fails
    """
    if not text:
        return None
    
    try:
        # 모든 구분자를 'x'로 통일
        clean = text.replace(" ", "").replace("×", "x").replace("X", "x").replace("*", "x").lower()
        
        if "x" in clean:
            parts = clean.split("x")
            if len(parts) == 2:
                width = int(parts[0])
                height = int(parts[1])
                return (width, height)
    except (ValueError, IndexError):
        pass
    
    return None


def validate_resolution(width: int, height: int, min_res: int = 50, max_res: int = 3840) -> bool:
    """해상도 유효성 검증
    
    Args:
        width: 너비
        height: 높이
        min_res: 최소 해상도
        max_res: 최대 해상도
        
    Returns:
        bool: 유효한 해상도인지 여부
    """
    return (min_res <= width <= max_res and min_res <= height <= max_res)


def safe_delete_timer(timer):
    """wxPython 타이머를 안전하게 정리

    Args:
        timer: wx.Timer 객체
    """
    if timer is None:
        return

    try:
        timer.Stop()  # wxPython은 대문자 Stop()
    except (TypeError, RuntimeError, AttributeError):
        pass

    # wxPython Timer는 deleteLater()가 없음
    # 참조만 해제하면 됨


# ═══════════════════════════════════════════════════════════════
# 앱 설정 상수
# ═══════════════════════════════════════════════════════════════

# 앱 설정 식별자 (일관성을 위해 ui.constants.APP_NAME과 동일하게 유지)
APP_SETTINGS_ORG = "XGif"
APP_SETTINGS_NAME = "XGif"


# ═══════════════════════════════════════════════════════════════
# 파일 시스템 유틸리티
# ═══════════════════════════════════════════════════════════════


def safe_rmtree(path: str, max_retries: int = 3) -> bool:
    """Windows에서 안전하게 디렉토리 삭제 (파일 잠금 문제 해결)
    
    Args:
        path: 삭제할 디렉토리 경로
        max_retries: 최대 재시도 횟수
        
    Returns:
        bool: 삭제 성공 여부
    """
    def on_rm_error(func, path, exc_info):
        """읽기 전용 파일 삭제 실패 시 권한 변경 후 재시도"""
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except (OSError, PermissionError):
            pass
    
    for attempt in range(max_retries):
        try:
            if os.path.exists(path):
                # 가비지 컬렉션 실행 (파일 핸들 해제)
                gc.collect()
                time.sleep(0.1 * (attempt + 1))  # 점진적 대기
                shutil.rmtree(path, onerror=on_rm_error)
            return True
        except (OSError, PermissionError):
            if attempt < max_retries - 1:
                time.sleep(0.5)
            continue
    return False


# ═══════════════════════════════════════════════════════════════
# 서브프로세스 유틸리티
# ═══════════════════════════════════════════════════════════════


def run_subprocess_silent(cmd: list, timeout: int = 60, **kwargs) -> subprocess.CompletedProcess:
    """Windows에서 콘솔 창 없이 서브프로세스 실행
    
    Args:
        cmd: 명령어 리스트
        timeout: 타임아웃 (초)
        **kwargs: subprocess.run에 전달할 추가 인자
        
    Returns:
        subprocess.CompletedProcess: 실행 결과
    """
    # Windows에서 콘솔 창 숨김
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    
    # 기본 설정
    default_kwargs = {
        'capture_output': True,
        'text': True,
        'timeout': timeout,
        'creationflags': creation_flags
    }
    
    # 사용자 인자로 덮어쓰기
    default_kwargs.update(kwargs)
    
    return subprocess.run(cmd, **default_kwargs)

