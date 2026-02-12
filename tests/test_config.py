"""
CLI 설정 관리 테스트
"""

import pytest
import os
import tempfile
from unittest.mock import patch


class TestConfigDefaults:
    """기본 설정값 테스트"""

    def test_default_settings_exist(self):
        from cli.config import DEFAULT_SETTINGS
        assert isinstance(DEFAULT_SETTINGS, dict)
        assert len(DEFAULT_SETTINGS) > 0

    def test_required_keys(self):
        from cli.config import DEFAULT_SETTINGS
        required = ['language', 'capture_backend', 'encoder', 'codec', 'memory_limit_mb']
        for key in required:
            assert key in DEFAULT_SETTINGS, f"'{key}' 누락"

    def test_default_language(self):
        from cli.config import DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS['language'] in ('ko', 'en')

    def test_default_backend(self):
        from cli.config import DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS['capture_backend'] in ('gdi', 'dxcam', 'auto')


class TestConfigPath:
    """설정 파일 경로 테스트"""

    def test_config_path_not_empty(self):
        from cli.config import get_config_path
        path = get_config_path()
        assert path is not None
        assert len(path) > 0

    def test_config_path_ends_with_ini(self):
        from cli.config import get_config_path
        path = get_config_path()
        assert path.endswith('config.ini')

    def test_config_path_contains_app_name(self):
        from cli.config import get_config_path
        path = get_config_path()
        assert 'XGif' in path


class TestConfigLoadSave:
    """설정 로드/저장 테스트"""

    def test_load_returns_defaults_when_no_file(self):
        from cli.config import load_config, DEFAULT_SETTINGS
        with patch('cli.config.get_config_path', return_value='/nonexistent/config.ini'):
            config = load_config()
            for key, value in DEFAULT_SETTINGS.items():
                assert config[key] == value

    def test_save_and_load(self):
        from cli.config import save_config, load_config, DEFAULT_SETTINGS
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'XGif', 'config.ini')
            with patch('cli.config.get_config_path', return_value=config_path):
                settings = dict(DEFAULT_SETTINGS)
                settings['language'] = 'en'
                save_config(settings)
                loaded = load_config()
                assert loaded['language'] == 'en'

    def test_set_config_value_valid_key(self):
        from cli.config import set_config_value, get_config_value
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'XGif', 'config.ini')
            with patch('cli.config.get_config_path', return_value=config_path):
                result = set_config_value('language', 'en')
                assert result is True
                assert get_config_value('language') == 'en'

    def test_set_config_value_invalid_key(self):
        from cli.config import set_config_value
        result = set_config_value('nonexistent_key', 'value')
        assert result is False

    def test_reset_config(self):
        from cli.config import reset_config, load_config, DEFAULT_SETTINGS
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'XGif', 'config.ini')
            with patch('cli.config.get_config_path', return_value=config_path):
                reset_config()
                config = load_config()
                for key, value in DEFAULT_SETTINGS.items():
                    assert config[key] == value


class TestCLIParser:
    """CLI 인자 파서 테스트"""

    def test_build_parser(self):
        from cli.main import build_parser
        parser = build_parser()
        assert parser is not None

    def test_version_flag(self):
        from cli.main import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['--version'])
        assert exc_info.value.code == 0

    def test_record_command(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(['record', '-o', 'test.gif'])
        assert args.command == 'record'
        assert args.output_opt == 'test.gif'

    def test_config_list_command(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(['config', 'list'])
        assert args.command == 'config'
        assert args.config_action == 'list'

    def test_doctor_command(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(['doctor'])
        assert args.command == 'doctor'

    def test_convert_command(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(['convert', 'input.gif', '-F', 'mp4'])
        assert args.command == 'convert'
        assert args.input == 'input.gif'
        assert args.format == 'mp4'

    def test_record_fps_option(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(['record', '-f', '30', '-o', 'test.gif'])
        assert args.fps == 30

    def test_record_no_cursor_flag(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(['record', '--no-cursor', '-o', 'test.gif'])
        assert args.cursor is False
