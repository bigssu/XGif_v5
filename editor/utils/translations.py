"""
Translations - 다국어 지원 시스템 (통합 모듈 래퍼)
기존 코드와의 호환성을 위해 ui.i18n 모듈을 래핑합니다.
"""
from typing import Dict

# 통합 번역 모듈에서 가져오기
from ui.i18n import EditorTranslations as Translations, get_trans_manager, tr

__all__ = ['Translations', 'get_trans_manager', 'tr']
