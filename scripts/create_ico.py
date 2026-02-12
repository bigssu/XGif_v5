"""PNG to ICO 변환 (빌드 시 호출). usage: python create_ico.py <png_path> <ico_path>"""
import sys
from PIL import Image

def main():
    if len(sys.argv) != 3:
        sys.exit(1)
    png_path, ico_path = sys.argv[1], sys.argv[2]
    
    # 원본 이미지 열기
    original_img = Image.open(png_path)
    if original_img.mode not in ("RGBA", "RGB"):
        original_img = original_img.convert("RGBA" if original_img.mode in ("RGBA", "P") else "RGB")
    
    # 각 크기로 리사이즈하여 ICO 파일에 포함
    sizes = [(256, 256), (48, 48), (32, 32), (16, 16)]
    
    # 가장 큰 이미지(256x256)를 기본으로 사용하고, sizes 파라미터로 여러 크기 포함
    # PIL의 ICO 저장은 sizes 파라미터로 자동 리사이즈하여 포함함
    original_img.save(ico_path, format="ICO", sizes=sizes)

if __name__ == "__main__":
    main()
