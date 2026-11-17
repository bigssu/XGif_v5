"""CLI 인자 파싱 테스트."""

import pytest

from cli.main import build_parser, cli_main
from core.settings import AppSettings


class TestSettingsValidKeys:
    def test_common_keys_exist(self):
        keys = AppSettings.valid_keys()
        assert "language" in keys
        assert "capture_backend" in keys
        assert "encoder" in keys
        assert "codec" in keys
        assert "memory_limit_mb" in keys

    def test_ui_keys_exist(self):
        keys = AppSettings.valid_keys()
        assert "preview_enabled" in keys
        assert "skip_ffmpeg_check" in keys

    def test_state_keys_exist(self):
        keys = AppSettings.valid_keys()
        assert "fps" in keys
        assert "resolution_preset" in keys
        assert "last_save_dir" in keys


@pytest.mark.parametrize(("option", "value"), [
    ("--delay", "inf"), ("--delay", "nan"), ("--delay", "-1"),
    ("--duration", "inf"), ("--duration", "nan"), ("--duration", "0"), ("--duration", "-1"),
    ("--monitor", "-1"), ("--fps", "0"), ("--fps", "121"),
    ("--region", "0,0,49x50"), ("--region", "0,0,100x100,extra"),
])
def test_record_rejects_invalid_numeric_inputs_before_initialization(monkeypatch, option, value):
    import cli.main as module
    monkeypatch.setattr(module, "setup_cli_logging", lambda **kwargs: pytest.fail("initialized before validation"))
    with pytest.raises(SystemExit) as exc:
        cli_main(["record", f"{option}={value}"])
    assert exc.value.code == 2


@pytest.mark.parametrize("argv", [
    ["convert", "input.gif", "--fps=0"],
    ["convert", "input.gif", "--fps=121"],
    ["convert", "input.gif", "--resize=100x100,other"],
])
def test_convert_rejects_invalid_numeric_inputs(argv):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(argv)
    assert exc.value.code == 2


def test_record_accepts_numeric_boundaries_and_negative_monitor_coordinates():
    args = build_parser().parse_args([
        "record", "--delay=0", "--duration=0.1", "--monitor=0", "--fps=120", "--region=-100,-50,50x50",
    ])
    assert args.delay == 0
    assert args.duration == 0.1
    assert args.monitor == 0
    assert args.fps == 120
    assert args.region == "-100,-50,50x50"
