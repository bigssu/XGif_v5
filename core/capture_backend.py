"""
캡처 백엔드 추상화 모듈
dxcam (DXGI Desktop Duplication), GDI BitBlt (색상 정확, Windows 전용)
"""

import atexit
import sys
import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Windows GDI (색상 정확 캡처, FireGif 방식)
HAS_GDI = sys.platform == "win32"

# dxcam 사용 가능 여부
try:
    import dxcam
    HAS_DXCAM = True
except ImportError:
    HAS_DXCAM = False



class CaptureBackend(ABC):
    """캡처 백엔드 추상 클래스"""

    @abstractmethod
    def start(self, region: Tuple[int, int, int, int], target_fps: int = 30) -> bool:
        """캡처 시작

        Args:
            region: (x, y, width, height) 캡처 영역
            target_fps: 목표 FPS

        Returns:
            bool: 시작 성공 여부
        """
        pass

    @abstractmethod
    def stop(self):
        """캡처 중지"""
        pass

    @abstractmethod
    def grab(self) -> Optional[np.ndarray]:
        """프레임 캡처

        Returns:
            np.ndarray: BGR 형식의 프레임 (없으면 None)
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """백엔드 이름 반환"""
        pass

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """캡처 중인지 여부"""
        pass

    # P1-4: 백엔드별 워밍업을 ABC에서 흡수. 기본은 no-op.
    # DXCam처럼 첫 start()가 느린 백엔드는 override하여 카메라 초기화를 선행한다.
    def warm_up(self) -> bool:
        """백엔드 미리 준비 (앱 시작 시 호출).

        기본 구현은 no-op (즉시 준비됨). 백엔드별로 first-start latency가
        큰 경우 override 하여 리소스를 선행 초기화한다.

        Returns:
            bool: 워밍업 성공 여부 (실패해도 예외를 올리지 않는다).
        """
        return True

    # P1-6: HDR 보정 우회 판단을 polymorphic 속성으로. backend_name 문자열 비교 제거.
    @property
    def supports_managed_color(self) -> bool:
        """Windows 색상 관리(ICC, HDR→SDR)가 백엔드 내부에서 자동 적용되는지.

        True면 caller는 HDR 보정을 스킵해야 한다 (이중 처리 방지).
        예: GDI 계열은 PIL ImageGrab / GetDIBits 경로에서 OS가 색상 관리 수행.
        dxcam은 DXGI raw buffer라 보정 미포함 → False 반환.
        """
        return False

    # P0-4: backend.stop() 실패 시 호출되는 강제 해제 폴백. 기본은 no-op.
    def force_release(self) -> None:
        """stop() 이 예외로 실패했을 때 호출되는 강제 리소스 해제.

        기본 구현은 no-op. DXGI duplicator 같이 OS 핸들을 소유하는 백엔드는
        override 하여 핸들 해제를 시도한다.
        """
        return None


class DXCamBackend(CaptureBackend):
    """dxcam 기반 고성능 캡처 백엔드 (DXGI Desktop Duplication)
    
    GPU 가속 사용: DXGI Desktop Duplication API (DirectX)
    - Windows 8 이상에서 가장 빠른 캡처 방법
    - GPU 복사 사용으로 CPU 부하 최소화
    """

    # 클래스 레벨 카메라 (재사용)
    _shared_camera: Optional['dxcam.DXCamera'] = None
    _camera_lock = threading.Lock()
    _instance_count = 0  # 활성 인스턴스 수 추적

    @classmethod
    def cleanup_shared_camera(cls):
        """앱 종료 시 공유 카메라 명시적 정리 (메모리 누수 방지)"""
        with cls._camera_lock:
            if cls._shared_camera is not None:
                try:
                    cls._shared_camera.stop()
                except Exception:
                    pass
                try:
                    del cls._shared_camera
                except Exception:
                    pass
                cls._shared_camera = None
                logger.info("[DXCamBackend] Shared camera cleaned up")

    def __init__(self):
        self._camera: Optional[dxcam.DXCamera] = None
        self._region: Optional[Tuple[int, int, int, int]] = None
        self._running = False
        self._target_fps = 30
        self._using_shared = False

        # 인스턴스 수 추적
        with DXCamBackend._camera_lock:
            DXCamBackend._instance_count += 1

    def __del__(self):
        """소멸자: 인스턴스 수 감소"""
        try:
            with DXCamBackend._camera_lock:
                DXCamBackend._instance_count = max(0, DXCamBackend._instance_count - 1)
        except Exception:
            pass

    def start(self, region: Tuple[int, int, int, int], target_fps: int = 30) -> bool:
        """캡처 시작 (GPU 가속, 빠른 시작)"""
        if not HAS_DXCAM:
            return False

        try:
            self.stop()  # 기존 카메라 정리

            x, y, w, h = region
            # dxcam은 (left, top, right, bottom) 형식 사용
            self._region = (x, y, x + w, y + h)
            self._target_fps = target_fps

            # 공유 카메라 재사용 시도 (빠른 시작)
            with DXCamBackend._camera_lock:
                if DXCamBackend._shared_camera is not None:
                    # 기존 카메라 재사용 (매우 빠름 - GPU 이미 초기화됨)
                    self._camera = DXCamBackend._shared_camera
                    self._using_shared = True
                    logger.info("[DXCamBackend] Reusing shared camera (instant start)")
                else:
                    # 새 카메라 생성 (처음만 느림)
                    logger.info("[DXCamBackend] Creating new camera (first time, may take ~500ms)")
                    self._camera = dxcam.create(output_color="BGR")

                    if self._camera is None:
                        return False

                    # 공유 카메라로 저장 (다음 번에 재사용)
                    DXCamBackend._shared_camera = self._camera
                    self._using_shared = True

            # 캡처 시작 (region과 fps만 변경 - 빠름)
            # video_mode=True: 연속 캡처 모드 (성능 향상)
            # 락 내에서 start 호출하여 동시 start 레이스 컨디션 방지
            with DXCamBackend._camera_lock:
                try:
                    self._camera.start(region=self._region, target_fps=target_fps, video_mode=True)
                except TypeError:
                    # video_mode 파라미터 미지원 시 기본 모드
                    self._camera.start(region=self._region, target_fps=target_fps)
                self._running = True

            # 빠른 워밍업 (짧게)
            import time
            warmup_start = time.time()
            max_warmup_time = 0.1  # 100ms만 (카메라 재사용 시 매우 빠름)

            while time.time() - warmup_start < max_warmup_time:
                test_frame = self._camera.get_latest_frame()
                if test_frame is not None:
                    logger.debug(f"[DXCamBackend] First frame ready in {(time.time() - warmup_start)*1000:.0f}ms")
                    break
                time.sleep(0.005)  # 5ms 체크

            return True

        except (RuntimeError, OSError, AttributeError) as e:
            logger.error(f"[DXCamBackend] 시작 실패: {e}")
            self._running = False
            return False

    def stop(self):
        """캡처 중지 (카메라는 유지 - 재사용 위해)"""
        # 먼저 running 플래그 해제 (새 캡처 방지)
        self._running = False

        if self._camera is not None:
            with DXCamBackend._camera_lock:
                try:
                    self._camera.stop()  # 캡처만 중지
                    logger.debug("[DXCamBackend] Capture stopped (camera kept for reuse)")
                    # 카메라는 삭제하지 않음 - 공유 카메라로 유지
                except (RuntimeError, OSError) as e:
                    logger.debug(f"[DXCamBackend] 중지 오류: {e}")

    def grab(self) -> Optional[np.ndarray]:
        """프레임 캡처"""
        if not self._running or self._camera is None:
            return None

        try:
            # get_latest_frame()은 새 프레임이 없으면 None 반환
            frame = self._camera.get_latest_frame()
            return frame
        except (RuntimeError, AttributeError) as e:
            logger.debug(f"[DXCamBackend] 캡처 오류: {e}")
            return None

    def get_name(self) -> str:
        return "dxcam"

    @property
    def is_running(self) -> bool:
        return self._running

    # P1-4: DXCam은 첫 dxcam.create()가 ~500ms 걸리므로 워밍업 이득이 큼.
    # 100x100 영역으로 짧게 start→grab→stop 해서 공유 카메라를 선행 초기화한다.
    def warm_up(self) -> bool:
        if not HAS_DXCAM:
            return False
        try:
            if not self.start((0, 0, 100, 100), target_fps=30):
                return False
            time.sleep(0.1)
            test_frame = self.grab()
            self.stop()
            return test_frame is not None
        except (ImportError, OSError, RuntimeError, AttributeError) as exc:
            logger.warning(f"[DXCamBackend] warm_up failed: {exc}")
            try:
                self.stop()
            except (RuntimeError, OSError):
                pass
            return False

    # P0-4: stop() 이 실패했을 때 DXGI duplicator 를 GC 가능 상태로 강제 해제.
    # 내부 _camera 참조를 끊어 다음 recording에서 핸들 충돌이 일어나지 않도록.
    def force_release(self) -> None:
        try:
            self._running = False
            self._camera = None
            logger.warning("[DXCamBackend] force_release: _camera cleared")
        except Exception as exc:
            logger.error(f"[DXCamBackend] force_release error: {exc}")


# 앱 종료 시 공유 DXCam 카메라 자동 정리 (리소스 누수 방지)
atexit.register(DXCamBackend.cleanup_shared_camera)


class DXCamPool:
    """DXCam 인스턴스 풀 — 레퍼런스 카운팅 기반.

    DXCamBackend의 기존 _shared_camera 로직을 정리한 래퍼.
    """

    _ref_count: int = 0
    _lock = threading.Lock()

    @classmethod
    def acquire(cls) -> Optional["dxcam.DXCamera"]:
        """DXCam 카메라 인스턴스를 획득. 없으면 생성."""
        if not HAS_DXCAM:
            return None
        with cls._lock:
            cls._ref_count += 1
            if DXCamBackend._shared_camera is None:
                try:
                    DXCamBackend._shared_camera = dxcam.create(output_color="BGR")
                    logger.info("[DXCamPool] Created new camera (refcount=%d)", cls._ref_count)
                except Exception as e:
                    logger.error("[DXCamPool] Failed to create camera: %s", e)
                    cls._ref_count -= 1
                    return None
            else:
                logger.debug("[DXCamPool] Reusing camera (refcount=%d)", cls._ref_count)
            return DXCamBackend._shared_camera

    @classmethod
    def release(cls) -> None:
        """레퍼런스 카운트 감소. 0이 되면 카메라 해제."""
        with cls._lock:
            cls._ref_count = max(0, cls._ref_count - 1)
            if cls._ref_count == 0:
                DXCamBackend.cleanup_shared_camera()
                logger.info("[DXCamPool] Camera released (refcount=0)")
            else:
                logger.debug("[DXCamPool] Release (refcount=%d)", cls._ref_count)

    @classmethod
    def ref_count(cls) -> int:
        return cls._ref_count


class FastGdiBackend(CaptureBackend):
    """고속 GDI 캡처 (ctypes 직접 사용, DC 재사용).
    DC와 비트맵을 재사용하여 30fps 달성.
    Windows 색상 관리가 자동 적용되어 HDR 환경에서도 색상 정확.
    """

    def __init__(self):
        if not HAS_GDI:
            raise RuntimeError("GDI backend requires Windows")

        self._running = False
        self._region: Optional[Tuple[int, int, int, int]] = None

        # GDI 핸들
        self._hdc_screen = None
        self._hdc_mem = None
        self._hbitmap = None
        self._old_bitmap = None
        self._bitmap_buffer = None

        # ctypes 로드
        import ctypes
        from ctypes import wintypes
        self.gdi32 = ctypes.windll.gdi32
        self.user32 = ctypes.windll.user32
        self.ctypes = ctypes
        self.wintypes = wintypes

        # BITMAPINFOHEADER 구조체
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)
            ]

        self.BITMAPINFOHEADER = BITMAPINFOHEADER

    def start(self, region: Tuple[int, int, int, int], target_fps: int = 30) -> bool:
        """DC 한 번만 생성 (재사용)"""
        try:
            self.stop()  # 기존 정리

            x, y, w, h = region
            if w <= 0 or h <= 0:
                return False

            self._region = (x, y, w, h)

            # 리소스 생성 - 실패 시 부분 생성된 리소스를 확실히 정리
            try:
                self._hdc_screen = self.user32.GetDC(0)
                if not self._hdc_screen:
                    return False

                self._hdc_mem = self.gdi32.CreateCompatibleDC(self._hdc_screen)
                if not self._hdc_mem:
                    return False

                self._hbitmap = self.gdi32.CreateCompatibleBitmap(self._hdc_screen, w, h)
                if not self._hbitmap:
                    return False

                self._old_bitmap = self.gdi32.SelectObject(self._hdc_mem, self._hbitmap)
                if self._bitmap_buffer is None or self._bitmap_buffer.shape != (h, w, 4):
                    self._bitmap_buffer = np.zeros((h, w, 4), dtype=np.uint8)
            except Exception:
                self.stop()
                raise

            self._running = True
            logger.info("[FastGdiBackend] Initialized with DC reuse")
            return True

        except Exception as e:
            logger.error(f"[FastGdiBackend] start failed: {e}")
            self.stop()
            return False

    def stop(self):
        """DC 정리"""
        self._running = False

        try:
            if self._old_bitmap and self._hdc_mem:
                self.gdi32.SelectObject(self._hdc_mem, self._old_bitmap)

            if self._hbitmap:
                self.gdi32.DeleteObject(self._hbitmap)

            if self._hdc_mem:
                self.gdi32.DeleteDC(self._hdc_mem)

            if self._hdc_screen:
                self.user32.ReleaseDC(0, self._hdc_screen)
        except Exception:
            pass

        self._hdc_screen = None
        self._hdc_mem = None
        self._hbitmap = None
        self._old_bitmap = None
        # _bitmap_buffer는 유지하여 동일 해상도 재시작 시 재사용

    def grab(self) -> Optional[np.ndarray]:
        """BitBlt + GetDIBits로 고속 캡처 (DC 재사용). 실패 시 PIL 폴백."""
        if not self._running or not self._region:
            return None

        x, y, w, h = self._region
        ctypes = self.ctypes
        gdi32 = self.gdi32
        SRCCOPY = 0x00CC0020
        DIB_RGB_COLORS = 0
        BI_RGB = 0

        try:
            # 1) BitBlt: 화면 DC -> 메모리 DC
            if not gdi32.BitBlt(
                self._hdc_mem, 0, 0, w, h,
                self._hdc_screen, x, y, SRCCOPY
            ):
                raise RuntimeError("BitBlt failed")

            # 2) BITMAPINFO (top-down, 32bpp)
            Bmi = self.BITMAPINFOHEADER
            bmi = Bmi()
            bmi.biSize = ctypes.sizeof(Bmi)
            bmi.biWidth = w
            bmi.biHeight = -h  # top-down (numpy 호환)
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = BI_RGB
            bmi.biSizeImage = w * h * 4
            bmi.biXPelsPerMeter = 0
            bmi.biYPelsPerMeter = 0
            bmi.biClrUsed = 0
            bmi.biClrImportant = 0

            # 3) GetDIBits: 비트맵 -> 버퍼 (BGRA)
            nlines = gdi32.GetDIBits(
                self._hdc_mem, self._hbitmap, 0, h,
                self._bitmap_buffer.ctypes.data_as(ctypes.c_void_p),
                ctypes.byref(bmi), DIB_RGB_COLORS
            )
            if nlines == 0:
                raise RuntimeError("GetDIBits returned 0")

            # 4) BGRA -> BGR (3채널, 호출부 기대 형식)
            frame_bgr = self._bitmap_buffer[:, :, :3].copy()
            return frame_bgr

        except Exception as e:
            logger.debug(f"[FastGdiBackend] GetDIBits path failed: {e}, using PIL fallback")
            try:
                from PIL import ImageGrab
                bbox = (x, y, x + w, y + h)
                img = ImageGrab.grab(bbox, all_screens=True)
                if img is None:
                    return None
                frame_rgb = np.asarray(img, dtype=np.uint8)
                return frame_rgb[:, :, ::-1].copy()
            except Exception as e2:
                logger.debug(f"[FastGdiBackend] grab failed: {e2}")
                return None

    def get_name(self) -> str:
        return "gdi"

    @property
    def is_running(self) -> bool:
        return self._running

    # P1-6: GetDIBits 경로는 GDI+/Windows 색상 관리가 자동 적용되므로 HDR 보정 스킵.
    @property
    def supports_managed_color(self) -> bool:
        return True

    # P1-4: PIL ImageGrab 을 즉시 호출하여 PIL lazy-import 를 선행. 100x100 smoke.
    def warm_up(self) -> bool:
        if not HAS_GDI:
            return False
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab((0, 0, 100, 100))
            return img is not None
        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning(f"[FastGdiBackend] warm_up failed: {exc}")
            return False


class GdiBackend(CaptureBackend):
    """GDI+ 기반 캡처 백엔드 (Windows 전용, PIL ImageGrab 사용).
    Windows 색상 관리(ICC, HDR→SDR)가 적용된 픽셀을 받아 색상 정확도가 높음 (FireGif 방식).
    PIL ImageGrab은 내부적으로 GDI+ Image.FromHbitmap을 사용하여 Windows 색상 관리를 거칩니다.
    레거시 폴백용.
    """

    def __init__(self):
        self._region: Optional[Tuple[int, int, int, int]] = None
        self._running = False
        self._target_fps = 30

    def start(self, region: Tuple[int, int, int, int], target_fps: int = 30) -> bool:
        """캡처 시작 (GDI는 별도 초기화 없음)"""
        if not HAS_GDI:
            return False
        x, y, w, h = region
        self._region = (x, y, w, h)
        self._target_fps = target_fps
        self._running = True
        return True

    def stop(self):
        self._running = False
        self._region = None

    def grab(self) -> Optional[np.ndarray]:
        """PIL ImageGrab으로 화면 복사 후 BGR numpy 반환 (Windows 색상 관리 적용)"""
        if not HAS_GDI or not self._running or not self._region:
            return None
        x, y, w, h = self._region
        if w <= 0 or h <= 0:
            return None
        try:
            from PIL import ImageGrab
            # PIL ImageGrab.grab은 (left, top, right, bottom) 형식
            bbox = (x, y, x + w, y + h)
            img = ImageGrab.grab(bbox, all_screens=True)
            # PIL Image를 numpy로 변환 (RGB -> BGR)
            frame_rgb = np.array(img)
            frame_bgr = frame_rgb[:, :, ::-1].copy()
            return frame_bgr
        except Exception as e:
            logger.debug("GdiBackend grab failed: %s", e)
            return None

    def get_name(self) -> str:
        return "gdi"

    @property
    def is_running(self) -> bool:
        return self._running

    # P1-6: PIL ImageGrab 은 GDI+ 를 통해 Windows 색상 관리를 수행하므로 True.
    @property
    def supports_managed_color(self) -> bool:
        return True

    # P1-4: FastGdiBackend 와 동일하게 PIL ImageGrab 을 선행 호출한다.
    def warm_up(self) -> bool:
        if not HAS_GDI:
            return False
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab((0, 0, 100, 100))
            return img is not None
        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning(f"[GdiBackend] warm_up failed: {exc}")
            return False


def create_capture_backend(preferred: str = "auto") -> CaptureBackend:
    """캡처 백엔드 생성
    
    Args:
        preferred: "auto", "dxcam", "gdi" 중 선택
        
    Returns:
        CaptureBackend: 사용 가능한 캡처 백엔드
        
    Raises:
        RuntimeError: 사용 가능한 백엔드가 없을 때
    """
    if preferred == "dxcam":
        if HAS_DXCAM:
            return DXCamBackend()
        else:
            raise RuntimeError("dxcam이 설치되지 않았습니다.")
    elif preferred == "gdi":
        if HAS_GDI:
            return FastGdiBackend()
        else:
            raise RuntimeError("GDI 백엔드는 Windows에서만 사용 가능합니다.")
    else:  # auto
        if HAS_DXCAM:
            return DXCamBackend()
        elif HAS_GDI:
            return FastGdiBackend()
        else:
            raise RuntimeError("사용 가능한 캡처 백엔드가 없습니다. dxcam을 설치하거나 Windows에서 GDI를 사용하세요.")


def test_capture_backend(backend: CaptureBackend, region: Tuple[int, int, int, int]) -> bool:
    """캡처 백엔드 테스트
    
    Args:
        backend: 테스트할 백엔드
        region: 테스트 영역
        
    Returns:
        bool: 테스트 성공 여부
    """
    try:
        if not backend.start(region, target_fps=10):
            return False

        # 짧은 대기 후 프레임 캡처 테스트
        time.sleep(0.2)
        frame = backend.grab()

        return frame is not None and frame.size > 0

    except (RuntimeError, OSError, ValueError) as e:
        logger.debug(f"[test_capture_backend] 테스트 실패: {e}")
        return False
    finally:
        try:
            backend.stop()
        except (RuntimeError, OSError):
            pass


def get_available_backends() -> list:
    """사용 가능한 백엔드 목록 반환"""
    available = []
    if HAS_DXCAM:
        available.append("dxcam")
    if HAS_GDI:
        available.append("gdi")
    return available


def is_dxcam_available() -> bool:
    """dxcam 사용 가능 여부"""
    return HAS_DXCAM


def is_gdi_available() -> bool:
    """GDI 백엔드 사용 가능 여부 (Windows 전용)"""
    return HAS_GDI
