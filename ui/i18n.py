"""
I18N (Internationalization) Manager - 통합 번역 모듈
JSON 파일 기반 번역 데이터 로드.
메인 앱 및 GIF 에디터 모두 지원.
Supports Korean (default) and English.
"""

import json
import logging
import os
import sys
from typing import Callable, Dict

logger = logging.getLogger(__name__)


def _get_i18n_dir() -> str:
    """i18n JSON 파일이 위치한 디렉토리 경로 반환."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'resources', 'i18n')


def _load_json(lang_code: str) -> Dict[str, str]:
    """JSON 파일에서 번역 데이터를 로드하여 flat dict로 반환."""
    i18n_dir = _get_i18n_dir()
    json_path = os.path.join(i18n_dir, f'{lang_code}.json')

    if not os.path.exists(json_path):
        logger.warning("i18n 파일을 찾을 수 없음: %s", json_path)
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("i18n JSON 로드 실패 (%s): %s", json_path, e)
        return {}

    # "main" + "editor" 섹션을 단일 flat dict로 병합
    merged: Dict[str, str] = {}
    for section in ('main', 'editor'):
        section_data = data.get(section, {})
        merged.update(section_data)
    return merged


class TranslationManager:
    """Translation manager with callback to notify UI of language changes"""

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = TranslationManager()
        return cls._instance

    def __init__(self):
        self._current_lang = 'ko'
        self._initialized = True
        self._callbacks = []

        # JSON에서 번역 데이터 로드
        self._translations: Dict[str, Dict[str, str]] = {
            'ko': _load_json('ko'),
            'en': _load_json('en'),
        }

    def load_language(self, lang_code: str) -> None:
        """추가 언어를 동적으로 로드."""
        if lang_code not in self._translations:
            data = _load_json(lang_code)
            if data:
                self._translations[lang_code] = data

    def set_language(self, lang: str):
        """언어 설정 (ko 또는 en)"""
        if lang in self._translations and lang != self._current_lang:
            self._current_lang = lang
            for callback in list(self._callbacks):
                try:
                    callback(lang)
                except Exception:
                    pass

    def register_callback(self, callback: Callable[[str], None]):
        """언어 변경 콜백 등록"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[str], None]):
        """언어 변경 콜백 제거"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    @property
    def current_lang(self) -> str:
        return self._current_lang

    def get_language(self) -> str:
        return self._current_lang

    @property
    def is_korean(self) -> bool:
        """현재 언어가 한국어인지 반환 (에디터 호환)"""
        return self._current_lang == 'ko'

    def get(self, key: str, default: str = None, **kwargs) -> str:
        """Get translated string for the current language

        Args:
            key: 번역 키
            default: 키가 없을 때 기본값
            **kwargs: 포맷 문자열에 사용할 인자들

        Returns:
            번역된 텍스트
        """
        text = self._translations.get(self._current_lang, {}).get(
            key, default if default is not None else key
        )

        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass

        return text


# ═══════════════════════════════════════════════════════════════
# 공용 함수 및 싱글톤 접근자
# ═══════════════════════════════════════════════════════════════

def get_trans_manager() -> TranslationManager:
    """TranslationManager 싱글톤 인스턴스 반환"""
    return TranslationManager.instance()


def tr(key: str, default: str = None, **kwargs) -> str:
    """번역 함수 (메인 앱용)

    Args:
        key: 번역 키
        default: 키가 없을 때 기본값
        **kwargs: 포맷 문자열에 사용할 인자들

    Returns:
        번역된 텍스트
    """
    return TranslationManager.instance().get(key, default, **kwargs)


# ═══════════════════════════════════════════════════════════════
# 에디터 호환 래퍼 클래스
# ═══════════════════════════════════════════════════════════════

class EditorTranslations:
    """GIF 에디터 호환용 래퍼 클래스

    기존 editor/utils/translations.py의 Translations 클래스와
    동일한 인터페이스를 제공합니다.
    """

    def __init__(self, is_korean: bool = True):
        self._manager = get_trans_manager()
        if is_korean:
            self._manager.set_language('ko')
        else:
            self._manager.set_language('en')

    def tr(self, key: str, **kwargs) -> str:
        return self._manager.get(key, **kwargs)

    def set_language(self, is_korean: bool):
        self._manager.set_language('ko' if is_korean else 'en')

    @property
    def is_korean(self) -> bool:
        return self._manager.is_korean


# 하위 호환성을 위한 별칭
Translations = EditorTranslations
