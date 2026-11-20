import subprocess
from pathlib import Path

import pytest

from cli import EXIT_RUNTIME_ERROR, EXIT_SUCCESS, EXIT_USER_ERROR
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


def test_gif_metadata_read_failure_preserves_existing_output(convert_args, monkeypatch):
    from PIL import Image

    Image.new('RGB', (4, 4)).save(convert_args.input)
    destination = Path(convert_args.conv_output)
    destination.write_bytes(b'original')

    def reject_image(*args, **kwargs):
        raise Image.DecompressionBombError('Image exceeds the pixel limit')

    monkeypatch.setattr(Image, 'open', reject_image)
    assert run_convert(convert_args) == EXIT_RUNTIME_ERROR
    assert destination.read_bytes() == b'original'


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


def test_output_created_during_conversion_survives(convert_args, monkeypatch):
    destination = Path(convert_args.conv_output)
    convert_args.overwrite = False
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            destination.write_bytes(b'finished by another process')
        Path(cmd[-1]).write_bytes(b'converted')
        return subprocess.CompletedProcess(cmd, 0, stderr='')

    monkeypatch.setattr(subprocess, 'run', run)
    assert run_convert(convert_args) == EXIT_USER_ERROR
    assert destination.read_bytes() == b'finished by another process'
    assert len(calls) == 2
    assert not Path(calls[0][-1]).exists()
    assert sorted(p.name for p in destination.parent.iterdir()) == ['input.gif', 'output.gif']


def test_real_gif_two_pass_preserves_frames_timing_and_size(tmp_path):
    from PIL import Image

    if not FFmpegManager.get_ffmpeg_executable():
        pytest.skip('FFmpeg not installed')
    source = tmp_path / 'source.gif'
    dest = tmp_path / 'resized.gif'
    colors = ['red', 'blue', 'green']
    frames = [Image.new('RGB', (64, 32), color) for color in colors]
    frames[0].save(source, save_all=True, append_images=frames[1:], duration=100, loop=0)
    args = build_parser().parse_args(['convert', str(source), str(dest), '--resize', '32x16', '--fps', '10'])
    assert run_convert(args) == EXIT_SUCCESS
    with Image.open(dest) as out:
        assert out.n_frames == 3 and out.size == (32, 16)
        for index, original in enumerate(frames):
            out.seek(index)
            assert out.convert('RGB').getpixel((0, 0)) == original.getpixel((0, 0))
            assert out.info['duration'] == 100


@pytest.mark.parametrize('rate', [30, 120, 240])
def test_real_gif_default_rate_keeps_one_second(tmp_path, rate):
    from PIL import Image, ImageSequence

    ffmpeg = FFmpegManager.get_ffmpeg_executable()
    if not ffmpeg:
        pytest.skip('FFmpeg not installed')
    source, target = tmp_path / 'fast.mp4', tmp_path / 'fast.gif'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=size=64x64:rate={rate}:duration=1',
                    '-c:v', 'libx264', str(source)], check=True, timeout=10)
    assert run_convert(build_parser().parse_args(['convert', str(source), str(target)])) == EXIT_SUCCESS
    with Image.open(target) as out:
        delays = [frame.info['duration'] for frame in ImageSequence.Iterator(out)]
    assert len(delays) == min(rate, 100) and sum(delays) == 1000 and min(delays) >= 10


@pytest.mark.parametrize("loop", [None, 0, 2])
def test_real_gif_default_rate_keeps_variable_frame_durations(tmp_path, loop):
    from PIL import Image, ImageSequence

    if not FFmpegManager.get_ffmpeg_executable():
        pytest.skip('FFmpeg not installed')
    source, target = tmp_path / 'variable.gif', tmp_path / 'roundtrip.gif'
    frames = [Image.new('RGB', (32, 32), color) for color in ['red', 'blue', 'green']]
    delays = [100, 200, 4000]
    frames[0].save(source, save_all=True, append_images=frames[1:], duration=delays,
                   **({} if loop is None else {"loop": loop}))
    assert run_convert(build_parser().parse_args(['convert', str(source), str(target)])) == EXIT_SUCCESS
    with Image.open(target) as out:
        assert out.info.get('loop') == loop
        assert [frame.info['duration'] for frame in ImageSequence.Iterator(out)] == delays


@pytest.mark.parametrize('resize', [False, True])
def test_real_mp4_pads_odd_dimensions(tmp_path, resize):
    import numpy as np
    from PIL import Image

    ffmpeg = FFmpegManager.get_ffmpeg_executable()
    if not ffmpeg:
        pytest.skip('FFmpeg not installed')
    source, target = tmp_path / 'odd.gif', tmp_path / 'odd.mp4'
    Image.new('RGB', (31, 29), 'white').save(source)
    width, height = (15, 13) if resize else (31, 29)
    cmd = ['convert', str(source), str(target), '--encoder', 'cpu']
    if resize:
        cmd.extend(['--resize', f'{width}x{height}'])
    assert run_convert(build_parser().parse_args(cmd)) == EXIT_SUCCESS
    pixels = subprocess.check_output([ffmpeg, '-v', 'error', '-i', str(target), '-f', 'rawvideo',
                                      '-pix_fmt', 'gray', '-'], timeout=10)
    image = np.frombuffer(pixels, dtype=np.uint8).reshape(height + 1, width + 1)
    assert image[:height, :width].min() > 200
    assert image[height, :].max() < 50 and image[:, width].max() < 50


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
