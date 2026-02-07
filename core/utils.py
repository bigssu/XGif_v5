"""
공통 유틸리티 모듈
중복 코드를 제거하고 재사용 가능한 함수들을 제공
"""

import os
import logging
from typing import Tuple, Optional
import numpy as np
from PIL import Image, ImageFont

logger = logging.getLogger(__name__)


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


# ═══════════════════════════════════════════════════════════════
# Qt 리소스 정리 유틸리티
# ═══════════════════════════════════════════════════════════════

def safe_disconnect_signal(signal, slot):
    """Qt 시그널을 안전하게 연결 해제
    
    Args:
        signal: Qt 시그널
        slot: 연결된 슬롯
    """
    try:
        signal.disconnect(slot)
    except (TypeError, RuntimeError):
        pass  # 이미 연결 해제됨


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


def safe_delete_animation(animation):
    """Qt 애니메이션을 안전하게 정리
    
    Args:
        animation: QPropertyAnimation 객체
    """
    if animation is None:
        return
    
    try:
        animation.stop()
    except (TypeError, RuntimeError):
        pass
    
    try:
        animation.deleteLater()
    except (RuntimeError, AttributeError):
        pass


class BlockSignals:
    """Qt 위젯의 시그널을 일시적으로 차단하는 Context Manager
    
    사용 예:
        with BlockSignals(widget):
            widget.setValue(10)  # 시그널 발생 안 함
        # 자동으로 시그널 복원
    """
    
    def __init__(self, *widgets):
        """
        Args:
            *widgets: 시그널을 차단할 Qt 위젯들
        """
        self.widgets = widgets
        self.original_states = []
    
    def __enter__(self):
        """시그널 차단"""
        for widget in self.widgets:
            if widget is not None:
                self.original_states.append(widget.signalsBlocked())
                widget.blockSignals(True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """시그널 복원"""
        for widget, original_state in zip(self.widgets, self.original_states):
            if widget is not None:
                try:
                    widget.blockSignals(original_state)
                except RuntimeError:
                    pass  # 위젯이 이미 삭제됨
        return False


# ═══════════════════════════════════════════════════════════════
# 앱 설정 상수
# ═══════════════════════════════════════════════════════════════

# 앱 설정 식별자 (일관성을 위해 ui.constants.APP_NAME과 동일하게 유지)
APP_SETTINGS_ORG = "XGif"
APP_SETTINGS_NAME = "XGif"


# ═══════════════════════════════════════════════════════════════
# 파일 시스템 유틸리티
# ═══════════════════════════════════════════════════════════════

import shutil
import stat
import time
import gc


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

import subprocess


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

