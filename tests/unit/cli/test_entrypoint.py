import ast
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(('argv', 'frozen', 'executable', 'expected'), [
    (['main.py'], False, 'python.exe', False),
    (['main.py', '--quiet', 'record'], False, 'python.exe', True),
    (['main.py', '--quiet', '--version'], False, 'python.exe', True),
    (['main.py', 'doctor'], False, 'python.exe', True),
    (['XGif-cli.exe'], True, 'C:/apps/XGif-cli.exe', True),
    (['XGif-cli.exe', '--bad-option'], True, 'C:/apps/XGif-cli.exe', True),
    (['XGif.exe'], True, 'C:/apps/XGif.exe', False),
])
def test_cli_routing_before_gui_import(argv, frozen, executable, expected):
    module = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == '_is_cli_mode')
    namespace = dict(sys=SimpleNamespace(argv=argv, frozen=frozen, executable=executable), os=os)
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'main.py', 'exec'), namespace)
    assert namespace['_is_cli_mode']() is expected


def test_source_cli_redirected_stdout_with_global_quiet():
    result = subprocess.run([sys.executable, 'main.py', '--quiet', '--version'],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0
    assert result.stdout.startswith('XGif ')
    assert result.stderr == ''


def test_cli_uses_console_when_log_directory_is_unavailable(tmp_path, monkeypatch):
    from cli import main
    from unittest.mock import Mock

    blocked = tmp_path / "file-not-directory"
    blocked.write_text("test")
    monkeypatch.setenv("APPDATA", str(blocked))
    configure = Mock()
    monkeypatch.setattr(main.logging, "basicConfig", configure)
    main.setup_cli_logging(quiet=True)
    handlers = configure.call_args.kwargs["handlers"]
    assert len(handlers) == 1 and type(handlers[0]) is main.logging.StreamHandler
    assert handlers[0].level == main.logging.ERROR
