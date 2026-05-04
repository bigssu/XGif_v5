from pathlib import Path

import build_optimized


def test_generated_pyinstaller_spec_keeps_size_guards(tmp_path, monkeypatch):
    resources = tmp_path / "resources"
    resources.mkdir()
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("wxPython>=4.2.5\n", encoding="utf-8")
    main_script = tmp_path / "main.py"
    main_script.write_text("print('xgif')\n", encoding="utf-8")

    monkeypatch.setattr(build_optimized, "PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(build_optimized, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(build_optimized, "MAIN_SCRIPT", str(main_script))

    spec_path = build_optimized._generate_spec_file(
        icon_ico=None,
        version_file=None,
        onefile=True,
        use_upx=True,
    )

    spec = Path(spec_path).read_text(encoding="utf-8")

    assert "optimize=1" in spec
    assert "'_avif'" in spec
    assert "'cv2'" in spec
    assert "'skimage'" in spec
    assert "upx=True" in spec
    assert "upx_exclude=['vcruntime*.dll', 'msvcp*.dll', 'wx*.dll']" in spec
