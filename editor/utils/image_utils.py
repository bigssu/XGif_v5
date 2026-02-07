"""
Image Utilities - 이미지 변환 유틸리티 함수

Provides conversion functions for both PyQt6 and wxPython image formats.
"""
from PIL import Image
from typing import Optional

# PyQt6는 선택적으로 import
try:
    from PyQt6.QtGui import QImage
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    QImage = None

# wxPython은 선택적으로 import
try:
    import wx
    WX_AVAILABLE = True
except ImportError:
    WX_AVAILABLE = False


def pil_to_qimage(pil_image: Image.Image) -> Optional['QImage']:
    """PIL Image를 QImage로 변환

    Args:
        pil_image: PIL Image 객체

    Returns:
        QImage 객체 또는 None (변환 실패 시 또는 PyQt6 미설치 시)
    """
    if not PYQT6_AVAILABLE:
        return None

    if pil_image is None:
        return None

    try:
        # RGBA 모드로 변환
        if pil_image.mode != 'RGBA':
            pil_image = pil_image.convert('RGBA')

        # 바이트 데이터 추출
        data = pil_image.tobytes('raw', 'RGBA')

        # QImage 생성
        qimage = QImage(
            data,
            pil_image.width,
            pil_image.height,
            pil_image.width * 4,
            QImage.Format.Format_RGBA8888
        )

        # 데이터 복사 (메모리 안전성)
        return qimage.copy()
    except Exception as e:
        print(f"PIL to QImage 변환 오류: {e}")
        return None


# =============================================================================
# wxPython Conversion Functions
# =============================================================================

def pil_to_wx_image(pil_image: Image.Image) -> Optional['wx.Image']:
    """
    PIL Image를 wx.Image로 변환

    Args:
        pil_image: PIL Image 객체

    Returns:
        wx.Image 객체 또는 None (변환 실패 시 또는 wxPython 미설치 시)
    """
    if not WX_AVAILABLE:
        return None

    if pil_image is None:
        return None

    try:
        # RGBA 모드로 변환
        if pil_image.mode != 'RGBA':
            pil_image = pil_image.convert('RGBA')

        width, height = pil_image.size

        # wx.Image 생성
        wx_image = wx.Image(width, height)

        # RGB 데이터 설정
        rgb_data = pil_image.convert('RGB').tobytes()
        wx_image.SetData(rgb_data)

        # 알파 채널 설정
        if pil_image.mode == 'RGBA':
            alpha_data = pil_image.split()[3].tobytes()
            wx_image.SetAlpha(alpha_data)

        return wx_image
    except Exception as e:
        print(f"PIL to wx.Image 변환 오류: {e}")
        return None


def pil_to_wx_bitmap(pil_image: Image.Image) -> Optional['wx.Bitmap']:
    """
    PIL Image를 wx.Bitmap으로 변환

    Args:
        pil_image: PIL Image 객체

    Returns:
        wx.Bitmap 객체 또는 None (변환 실패 시 또는 wxPython 미설치 시)
    """
    if not WX_AVAILABLE:
        return None

    wx_image = pil_to_wx_image(pil_image)
    if wx_image is None:
        return None

    try:
        return wx.Bitmap(wx_image)
    except Exception as e:
        print(f"wx.Image to wx.Bitmap 변환 오류: {e}")
        return None


def wx_image_to_pil(wx_image: 'wx.Image') -> Optional[Image.Image]:
    """
    wx.Image를 PIL Image로 변환

    Args:
        wx_image: wx.Image 객체

    Returns:
        PIL Image 객체 또는 None (변환 실패 시 또는 wxPython 미설치 시)
    """
    if not WX_AVAILABLE or wx_image is None:
        return None

    try:
        width = wx_image.GetWidth()
        height = wx_image.GetHeight()

        # RGB 데이터 가져오기
        rgb_data = bytes(wx_image.GetData())

        # PIL Image 생성
        pil_image = Image.frombytes('RGB', (width, height), rgb_data)

        # 알파 채널이 있으면 RGBA로 변환
        if wx_image.HasAlpha():
            alpha_data = bytes(wx_image.GetAlpha())
            alpha_image = Image.frombytes('L', (width, height), alpha_data)

            pil_image = pil_image.convert('RGBA')
            pil_image.putalpha(alpha_image)

        return pil_image
    except Exception as e:
        print(f"wx.Image to PIL 변환 오류: {e}")
        return None


def wx_bitmap_to_pil(wx_bitmap: 'wx.Bitmap') -> Optional[Image.Image]:
    """
    wx.Bitmap을 PIL Image로 변환

    Args:
        wx_bitmap: wx.Bitmap 객체

    Returns:
        PIL Image 객체 또는 None (변환 실패 시 또는 wxPython 미설치 시)
    """
    if not WX_AVAILABLE or wx_bitmap is None or not wx_bitmap.IsOk():
        return None

    try:
        wx_image = wx_bitmap.ConvertToImage()
        return wx_image_to_pil(wx_image)
    except Exception as e:
        print(f"wx.Bitmap to PIL 변환 오류: {e}")
        return None


def qimage_to_wx_image(qimage: QImage) -> Optional['wx.Image']:
    """
    QImage를 wx.Image로 변환 (PIL을 중간 매개체로 사용)

    Args:
        qimage: QImage 객체

    Returns:
        wx.Image 객체 또는 None (변환 실패 시)
    """
    if not WX_AVAILABLE or qimage is None:
        return None

    try:
        # QImage -> PIL
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.sizeInBytes())

        pil_image = Image.frombytes('RGBA', (width, height), ptr.asstring())

        # PIL -> wx.Image
        return pil_to_wx_image(pil_image)
    except Exception as e:
        print(f"QImage to wx.Image 변환 오류: {e}")
        return None


def wx_image_to_qimage(wx_image: 'wx.Image') -> Optional[QImage]:
    """
    wx.Image를 QImage로 변환 (PIL을 중간 매개체로 사용)

    Args:
        wx_image: wx.Image 객체

    Returns:
        QImage 객체 또는 None (변환 실패 시)
    """
    if not WX_AVAILABLE or wx_image is None:
        return None

    try:
        # wx.Image -> PIL
        pil_image = wx_image_to_pil(wx_image)

        # PIL -> QImage
        return pil_to_qimage(pil_image)
    except Exception as e:
        print(f"wx.Image to QImage 변환 오류: {e}")
        return None
