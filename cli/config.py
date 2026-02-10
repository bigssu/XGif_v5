"""CLI 설정 관리 -- config.ini를 GUI와 공유"""
import configparser
import os
import sys
from typing import Dict, Optional

# core.utils에서 앱 이름 가져오기
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.utils import APP_SETTINGS_NAME
from core.defaults import COMMON_DEFAULTS

DEFAULT_SETTINGS = dict(COMMON_DEFAULTS)


def get_config_path() -> str:
    """config.ini 경로 반환 (GUI와 동일한 위치)"""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, APP_SETTINGS_NAME, "config.ini")


def load_config() -> Dict[str, str]:
    """config.ini에서 설정 로드"""
    config = configparser.ConfigParser()
    config_path = get_config_path()

    result = dict(DEFAULT_SETTINGS)

    if os.path.exists(config_path):
        config.read(config_path, encoding="utf-8")
        if config.has_section("General"):
            for key in DEFAULT_SETTINGS:
                val = config.get("General", key, fallback=None)
                if val is not None:
                    result[key] = val

    return result


def save_config(settings: Dict[str, str]):
    """config.ini에 설정 저장"""
    config_path = get_config_path()
    config_dir = os.path.dirname(config_path)
    os.makedirs(config_dir, exist_ok=True)

    config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path, encoding="utf-8")

    if not config.has_section("General"):
        config.add_section("General")

    for key, value in settings.items():
        config.set("General", key, value)

    with open(config_path, "w", encoding="utf-8") as f:
        config.write(f)


def get_config_value(key: str) -> Optional[str]:
    """특정 설정 값 조회"""
    settings = load_config()
    return settings.get(key)


def set_config_value(key: str, value: str) -> bool:
    """특정 설정 값 변경. 유효한 키이면 True 반환."""
    if key not in DEFAULT_SETTINGS:
        return False
    settings = load_config()
    settings[key] = value
    save_config(settings)
    return True


def reset_config():
    """모든 설정을 기본값으로 복원"""
    save_config(DEFAULT_SETTINGS)


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
            print(f"       사용 가능한 키: {', '.join(sorted(DEFAULT_SETTINGS.keys()))}")
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
