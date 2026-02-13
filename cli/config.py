"""CLI 설정 관리 -- AppSettings 기반으로 config.ini를 GUI와 공유"""
import sys
from typing import Dict, Optional

from core.settings import AppSettings, get_config_path

# 하위 호환: 기존 코드가 DEFAULT_SETTINGS dict를 참조
_defaults = AppSettings()
DEFAULT_SETTINGS = _defaults.to_dict()


def load_config() -> Dict[str, str]:
    """config.ini에서 설정 로드"""
    settings = AppSettings.load()
    return settings.to_dict()


def save_config(settings_dict: Dict[str, str]):
    """config.ini에 설정 저장"""
    settings = AppSettings.load()
    for key, value in settings_dict.items():
        settings.set(key, value)
    settings.save()


def get_config_value(key: str) -> Optional[str]:
    """특정 설정 값 조회"""
    settings = AppSettings.load()
    if not settings.has_key(key):
        return None
    return settings.get(key)


def set_config_value(key: str, value: str) -> bool:
    """특정 설정 값 변경. 유효한 키이면 True 반환."""
    if key not in AppSettings.valid_keys():
        return False
    settings = AppSettings.load()
    settings.set(key, value)
    settings.save()
    return True


def reset_config():
    """모든 설정을 기본값으로 복원"""
    settings = AppSettings()
    settings.save()


def handle_config_command(args) -> int:
    """config 서브커맨드 처리. 반환값: 종료 코드."""
    if args.config_action == "path":
        print(get_config_path())
        return 0

    if args.config_action == "reset":
        reset_config()
        print("모든 설정이 기본값으로 복원되었습니다.")
        return 0

    if args.config_action == "get":
        if not args.key:
            print("xgif: 에러: 'get' 명령에는 KEY가 필요합니다.", file=sys.stderr)
            return 1
        value = get_config_value(args.key)
        if value is None:
            print(f"xgif: 에러: 알 수 없는 설정 키 '{args.key}'", file=sys.stderr)
            return 1
        print(f"{args.key}={value}")
        return 0

    if args.config_action == "set":
        if not args.key or not args.value:
            print("xgif: 에러: 'set' 명령에는 KEY와 VALUE가 필요합니다.", file=sys.stderr)
            return 1
        if set_config_value(args.key, args.value):
            print(f"{args.key}={args.value}")
            return 0
        else:
            print(f"xgif: 에러: 알 수 없는 설정 키 '{args.key}'", file=sys.stderr)
            print(f"       사용 가능한 키: {', '.join(sorted(AppSettings.valid_keys()))}")
            return 1

    # list (기본 동작)
    settings = load_config()
    config_path = get_config_path()
    print(f"설정 파일: {config_path}\n")
    max_key_len = max(len(k) for k in settings)
    for key, value in sorted(settings.items()):
        default = DEFAULT_SETTINGS.get(key, "")
        marker = "" if value == default else " (변경됨)"
        print(f"  {key:<{max_key_len}}  = {value}{marker}")
    return 0
