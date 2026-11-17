import subprocess
from pathlib import Path

import pytest

from cli import EXIT_RUNTIME_ERROR, EXIT_SUCCESS
from cli.converter import run_convert
from cli.main import build_parser
from core.ffmpeg_installer import FFmpegManager


@pytest.fixture
def convert_args(tmp_path, monkeypatch):
    source = tmp_path / 'input.gif'
    source.write_bytes(b'input')
    monkeypatch.setattr(FFmpegManager, 'get_ffmpeg_executable', lambda: 'ffmpeg')
    monkeypatch.setattr(FFmpegManager, 'get_ffmpeg_env', lambda: {})
    from core.gif_encoder import GifEncoder
    monkeypatch.setattr(GifEncoder, '__init__', lambda self: None)
    monkeypatch.setattr(GifEncoder, '_get_best_encoder', lambda *args: 'libx264')
    return build_parser().parse_args(['convert', str(source), str(tmp_path / 'output.gif'), '-y'])


@pytest.mark.parametrize('failure', ['exit', 'timeout', 'spawn', 'empty', 'commit'])
def test_conversion_failure_preserves_destination(convert_args, monkeypatch, failure):
    destination = Path(convert_args.conv_output)
    destination.write_bytes(b'original')

    def run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b'' if failure == 'empty' else b'partial')
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(cmd, 600)
        if failure == 'spawn':
            raise OSError('cannot start encoder')
        return subprocess.CompletedProcess(cmd, 1 if failure == 'exit' else 0, stderr='error')

    monkeypatch.setattr(subprocess, 'run', run)
    if failure == 'commit':
        def locked(*args):
            raise PermissionError('locked')
        monkeypatch.setattr('cli.converter.os.replace', locked)
    assert run_convert(convert_args) == EXIT_RUNTIME_ERROR
    assert destination.read_bytes() == b'original'
    assert sorted(p.name for p in destination.parent.iterdir()) == ['input.gif', 'output.gif']


@pytest.mark.parametrize('explicit_output', [False, True])
def test_explicit_format_sets_staged_muxer_and_default_suffix(convert_args, monkeypatch, explicit_output):
    source = Path(convert_args.input).with_suffix('.avi')
    Path(convert_args.input).rename(source)
    convert_args.input = str(source)
    convert_args.format = 'mp4'
    convert_args.conv_output = str(source.parent / 'custom.gif') if explicit_output else None
    target = Path(convert_args.conv_output) if explicit_output else source.with_suffix('.mp4')
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        staged = Path(cmd[-1])
        assert staged.suffix == '.mp4'
        assert staged.parent == target.parent
        assert staged != target
        staged.write_bytes(b'converted')
        return subprocess.CompletedProcess(cmd, 0, stderr='')

    monkeypatch.setattr(subprocess, 'run', run)
    assert run_convert(convert_args) == EXIT_SUCCESS
    assert target.read_bytes() == b'converted'
    assert len(calls) == 1
    assert sorted(source.parent.iterdir()) == sorted([source, target])


def test_real_explicit_mp4_conversion_decodes_expected_color(tmp_path):
    import numpy as np
    from PIL import Image

    ffmpeg = FFmpegManager.get_ffmpeg_executable()
    if not ffmpeg:
        pytest.skip('FFmpeg not installed')
    source = tmp_path / 'red.png'
    Image.new('RGB', (32, 32), (255, 0, 0)).save(source)
    args = build_parser().parse_args(['convert', str(source), '--format', 'mp4', '--encoder', 'cpu'])
    assert run_convert(args) == EXIT_SUCCESS
    output = source.with_suffix('.mp4')
    result = subprocess.run([ffmpeg, '-v', 'error', '-i', str(output),
                             '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                            capture_output=True, check=True, timeout=10)
    decoded = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, 32, 32, 3)
    assert len(decoded) == 1
    assert np.max(np.abs(decoded.astype(int) - (255, 0, 0))) < 10
    assert sorted(tmp_path.iterdir()) == sorted([source, output])


@pytest.mark.parametrize('codec', ['h264', 'h265'])
@pytest.mark.parametrize('mode', ['auto', 'explicit', 'cpu_failure'])
def test_convert_auto_retries_hardware_failure_once(convert_args, monkeypatch, codec, mode, capsys, caplog):
    from core.gif_encoder import GifEncoder

    convert_args.format = 'mp4'
    convert_args.codec = codec
    convert_args.encoder = 'nvenc' if mode == 'explicit' else None
    hardware = 'h264_nvenc' if codec == 'h264' else 'hevc_nvenc'
    cpu = 'libx264' if codec == 'h264' else 'libx265'
    monkeypatch.setattr(GifEncoder, '_get_best_encoder', lambda *args: hardware)
    output = Path(convert_args.conv_output)
    output.write_bytes(b'original')
    attempts = []

    def run(cmd, **kwargs):
        assert output.read_bytes() == b'original'
        selected = cmd[cmd.index('-c:v') + 1]
        attempts.append(selected)
        Path(cmd[-1]).write_bytes(b'partial' if selected == hardware else b'complete')
        if selected == cpu:
            assert '-cq' not in cmd and '-crf' in cmd
        return subprocess.CompletedProcess(cmd, 7 if selected == hardware else 9 if mode == 'cpu_failure' else 0,
                                           stderr=('banner' * 100 + '\nInitializeEncoder failed: frame too small')
                                           if selected == hardware else 'CPU error')

    monkeypatch.setattr(subprocess, 'run', run)
    assert run_convert(convert_args) == (EXIT_SUCCESS if mode == 'auto' else EXIT_RUNTIME_ERROR)
    assert attempts == ([hardware] if mode == 'explicit' else [hardware, cpu])
    assert output.read_bytes() == (b'complete' if mode == 'auto' else b'original')
    if mode != 'auto':
        error = capsys.readouterr().err
        assert 'frame too small' in error
        if mode == 'cpu_failure':
            assert 'CPU error' in error and 'exit 9' in error
            assert 'exit 7' in caplog.text and 'frame too small' in caplog.text
    assert sorted(p.name for p in output.parent.iterdir()) == ['input.gif', 'output.gif']


def test_real_small_gif_default_auto_mp4(tmp_path):
    import numpy as np
    from PIL import Image

    ffmpeg = FFmpegManager.get_ffmpeg_executable()
    if not ffmpeg:
        pytest.skip('FFmpeg not installed')
    source = tmp_path / 'small.gif'
    Image.new('RGB', (64, 48), (255, 0, 0)).save(source)
    args = build_parser().parse_args(['convert', str(source)])
    assert run_convert(args) == EXIT_SUCCESS
    result = subprocess.run([ffmpeg, '-v', 'error', '-i', str(source.with_suffix('.mp4')),
                             '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                            capture_output=True, check=True, timeout=10)
    pixels = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, 48, 64, 3)
    assert len(pixels) == 1
    assert np.max(np.abs(pixels.astype(int) - (255, 0, 0))) < 10


@pytest.mark.parametrize('message', ['No space left on device', 'Invalid data found when processing input',
                                   'Error opening output file: Permission denied'])
def test_converter_does_not_retry_nonencoder_errors(convert_args, monkeypatch, message, capsys):
    from core.gif_encoder import GifEncoder

    convert_args.format = 'mp4'
    monkeypatch.setattr(GifEncoder, '_get_best_encoder', lambda *args: 'h264_nvenc')
    attempts = []

    def run(cmd, **kwargs):
        attempts.append(cmd)
        return subprocess.CompletedProcess(cmd, 77, stderr=message)

    monkeypatch.setattr(subprocess, 'run', run)
    output = Path(convert_args.conv_output)
    output.write_bytes(b'original')
    assert run_convert(convert_args) == EXIT_RUNTIME_ERROR
    assert len(attempts) == 1
    assert output.read_bytes() == b'original'
    error = capsys.readouterr().err
    assert message in error and 'exit 77' in error
