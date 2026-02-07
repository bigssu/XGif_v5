"""
키보드 입력 표시 모듈
키 입력을 감지하고 화면에 텍스트로 표시
"""

import threading
import time
import logging
from typing import Optional, List, Tuple, TYPE_CHECKING
import numpy as np
from .utils import calculate_overlay_position, load_system_font

logger = logging.getLogger(__name__)

# 키보드 후킹 라이브러리 (선택적)
try:
    from pynput import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

# 타입 체크 시에만 import
if TYPE_CHECKING:
    from pynput.keyboard import Listener


class KeyboardDisplay:
    """키보드 입력 표시 (Context Manager 지원)
    
    사용 예:
        with KeyboardDisplay() as kbd:
            kbd.set_enabled(True)
            frame = kbd.apply_keyboard_display(frame)
    """
    
    def __init__(self):
        self.enabled = False
        self.position = 'bottom'  # 'top', 'bottom'
        self.font_size = 20
        self.text_color = (255, 255, 255)  # RGB
        self.bg_color = (0, 0, 0, 180)  # RGBA
        self.display_duration = 2.0  # 초

        # 키 입력 추적
        self._key_events: List[Tuple[str, float]] = []  # (key_text, timestamp)
        self._lock = threading.Lock()
        self._listener: Optional[keyboard.Listener] = None
        self._pressed_keys = set()

        # 폰트 캐시 (매 프레임 로드 방지)
        self._cached_font = None
        # 렌더링 결과 캐시 (텍스트 미변경 시 재사용)
        self._cached_key_text: Optional[str] = None
        self._cached_text_array: Optional[np.ndarray] = None
        self._cached_text_size: Optional[Tuple[int, int]] = None
    
    def __enter__(self):
        """Context Manager 진입"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager 종료"""
        self.stop_listening()
        return False
    
    def is_available(self) -> bool:
        """키보드 입력 감지 가능 여부"""
        return HAS_KEYBOARD
    
    def set_enabled(self, enabled: bool):
        """키보드 입력 표시 활성화/비활성화"""
        self.enabled = enabled
        if enabled:
            self.start_listening()
        else:
            self.stop_listening()
    
    def start_listening(self):
        """키보드 리스너 시작"""
        if not HAS_KEYBOARD or self._listener is not None:
            return
        
        try:
            if not HAS_KEYBOARD:
                return
            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._listener.start()
        except (ImportError, AttributeError) as e:
            logger.warning("키보드 리스너 시작 실패 (의존성 문제): %s", e)
        except Exception as e:
            logger.warning("키보드 리스너 시작 실패: %s", e)
    
    def stop_listening(self):
        """키보드 리스너 중지"""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        
        with self._lock:
            self._key_events = []
            self._pressed_keys = set()
    
    def _on_key_press(self, key):
        """키 누름 이벤트"""
        if not self.enabled:
            return

        try:
            key_str = self._key_to_string(key)
            with self._lock:
                if key_str and key_str not in self._pressed_keys:
                    self._pressed_keys.add(key_str)
                    current_time = time.perf_counter()
                    self._key_events.append((key_str, current_time))
                    # 오래된 이벤트 제거
                    cutoff_time = current_time - self.display_duration
                    self._key_events = [(k, t) for k, t in self._key_events if t > cutoff_time]
        except (AttributeError, ValueError, KeyError):
            pass

    def _on_key_release(self, key):
        """키 놓음 이벤트"""
        if not self.enabled:
            return

        try:
            key_str = self._key_to_string(key)
            with self._lock:
                if key_str in self._pressed_keys:
                    self._pressed_keys.discard(key_str)
        except Exception:
            pass
    
    def _key_to_string(self, key) -> Optional[str]:
        """키를 문자열로 변환"""
        try:
            if hasattr(key, 'char') and key.char:
                return key.char
            elif hasattr(key, 'name'):
                # 특수 키 처리
                special_keys = {
                    'space': 'Space',
                    'enter': 'Enter',
                    'tab': 'Tab',
                    'backspace': 'Backspace',
                    'delete': 'Delete',
                    'esc': 'Esc',
                    'shift': 'Shift',
                    'ctrl': 'Ctrl',
                    'alt': 'Alt',
                    'cmd': 'Cmd',
                    'up': '↑',
                    'down': '↓',
                    'left': '←',
                    'right': '→',
                }
                return special_keys.get(key.name, key.name.capitalize())
            return None
        except Exception:
            return None
    
    def _get_current_key_text(self) -> str:
        """현재 표시할 키 텍스트"""
        with self._lock:
            current_time = time.perf_counter()
            cutoff_time = current_time - self.display_duration
            
            # 최근 키 이벤트만 필터링
            recent_events = [(k, t) for k, t in self._key_events if t > cutoff_time]
            
            if not recent_events:
                return ""
            
            # 키 조합 생성 (Ctrl+C 등)
            if len(recent_events) > 1:
                # 최근 이벤트들을 조합
                keys = [k for k, t in recent_events[-5:]]  # 최근 5개만
                return " + ".join(keys)
            else:
                return recent_events[-1][0]
    
    def apply_keyboard_display(self, frame: np.ndarray) -> np.ndarray:
        """프레임에 키보드 입력 표시 적용"""
        # 안전 검증
        if not self.enabled:
            return frame
        
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return frame
        
        key_text = self._get_current_key_text()
        if not key_text:
            return frame
        
        try:
            from PIL import Image, ImageDraw

            h, w = frame.shape[:2]

            # 폰트 캐시 (최초 1회만 로드)
            if self._cached_font is None:
                self._cached_font = load_system_font(
                    self.font_size,
                    preferred_fonts=["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/courier.ttf"]
                )
            font = self._cached_font

            # 텍스트 미변경 시 이전 렌더링 결과 재사용
            if key_text == self._cached_key_text and self._cached_text_array is not None:
                text_array = self._cached_text_array
                img_width, img_height = self._cached_text_size
            else:
                # 텍스트 크기 측정
                temp_img = Image.new('RGB', (1, 1))
                draw = ImageDraw.Draw(temp_img)
                bbox = draw.textbbox((0, 0), key_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # 패딩
                padding = 10
                img_width = text_width + padding * 2
                img_height = text_height + padding * 2

                # 텍스트 이미지 생성
                text_img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(text_img)

                if self.bg_color:
                    draw.rectangle([0, 0, img_width, img_height], fill=self.bg_color)

                draw.text((padding, padding), key_text, font=font, fill=self.text_color)

                text_array = np.array(text_img)
                # 캐시 갱신
                self._cached_key_text = key_text
                self._cached_text_array = text_array
                self._cached_text_size = (img_width, img_height)
            
            # 공통 유틸리티로 위치 계산 (중앙 정렬을 위해 position 조정)
            position = 'top' if self.position == 'top' else 'bottom'
            x, y = calculate_overlay_position(w, h, img_width, img_height, position, margin=20)
            # 가로 중앙 정렬
            x = (w - img_width) // 2
            x = max(0, min(x, w - img_width))
            
            # 알파 블렌딩 적용 (RGBA 자동 처리)
            roi = frame[y:y+img_height, x:x+img_width]
            roi_h, roi_w = roi.shape[:2]
            if roi_h <= 0 or roi_w <= 0:
                return frame
            ta = text_array[:roi_h, :roi_w]
            if ta.shape[2] == 4:  # RGBA
                alpha = ta[:, :, 3:4] / 255.0
                rgb = ta[:, :, :3]
                blended = (roi * (1.0 - alpha) + rgb * alpha).astype(np.uint8)
                frame[y:y+roi_h, x:x+roi_w] = blended
            
            return frame
        except (ImportError, OSError, ValueError, IndexError) as e:
            import logging
            logging.debug(f"키보드 표시 적용 실패: {e}")
            return frame
    
    def __del__(self):
        """소멸자"""
        try:
            self.stop_listening()
        except Exception:
            pass  # 소멸자에서 예외 무시
