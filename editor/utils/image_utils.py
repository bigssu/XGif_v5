"""
Image Utilities - wxPython 이미지 변환 유틸리티 함수
"""
from PIL import Image
from typing import Optional

try:
    import wx
    WX_AVAILABLE = True
except ImportError:
    WX_AVAILABLE = False


def pil_to_wx_image(pil_image: Image.Image) -> Optional['wx.Image']:
    """PIL Image를 wx.Image로 변환"""
    if not WX_AVAILABLE:
        return None

    if pil_image is None:
        return None

    try:
        if pil_image.mode != 'RGBA':
            pil_image = pil_image.convert('RGBA')

        width, height = pil_image.size

        wx_image = wx.Image(width, height)

        rgb_data = pil_image.convert('RGB').tobytes()
        wx_image.SetData(rgb_data)

        if pil_image.mode == 'RGBA':
            alpha_data = pil_image.split()[3].tobytes()
            wx_image.SetAlpha(alpha_data)

        return wx_image
    except Exception:
        return None


def pil_to_wx_bitmap(pil_image: Image.Image) -> Optional['wx.Bitmap']:
    """PIL Image를 wx.Bitmap으로 변환"""
    if not WX_AVAILABLE:
        return None

    wx_image = pil_to_wx_image(pil_image)
    if wx_image is None:
        return None

    try:
        return wx.Bitmap(wx_image)
    except Exception:
        return None


def wx_image_to_pil(wx_image: 'wx.Image') -> Optional[Image.Image]:
    """wx.Image를 PIL Image로 변환"""
    if not WX_AVAILABLE or wx_image is None:
        return None

    try:
        width = wx_image.GetWidth()
        height = wx_image.GetHeight()

        rgb_data = bytes(wx_image.GetData())

        pil_image = Image.frombytes('RGB', (width, height), rgb_data)

        if wx_image.HasAlpha():
            alpha_data = bytes(wx_image.GetAlpha())
            alpha_image = Image.frombytes('L', (width, height), alpha_data)

            pil_image = pil_image.convert('RGBA')
            pil_image.putalpha(alpha_image)

        return pil_image
    except Exception:
        return None


def wx_bitmap_to_pil(wx_bitmap: 'wx.Bitmap') -> Optional[Image.Image]:
    """wx.Bitmap을 PIL Image로 변환"""
    if not WX_AVAILABLE or wx_bitmap is None or not wx_bitmap.IsOk():
        return None

    try:
        wx_image = wx_bitmap.ConvertToImage()
        return wx_image_to_pil(wx_image)
    except Exception:
        return None
