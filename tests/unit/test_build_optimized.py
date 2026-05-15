from pathlib import Path

import build_optimized


def test_run_installer_injects_app_version_and_source_exe(tmp_path, monkeypatch):
    from core.version import APP_VERSION

    exe_path = tmp_path / "XGif.exe"
    exe_path.write_bytes(b"fake exe")
    calls = []

    def fake_run(cmd, check, cwd, env):
        calls.append({"cmd": cmd, "check": check, "cwd": cwd, "env": env})

    monkeypatch.setattr(build_optimized, "_find_iscc", lambda: "ISCC.exe")
    monkeypatch.setattr(build_optimized.subprocess, "run", fake_run)

    installer_path = build_optimized.run_installer(str(exe_path))

    assert calls
    assert f"/DMyAppVersion={APP_VERSION}" in calls[0]["cmd"]
    assert f"/DMyAppExeSource={exe_path.resolve()}" in calls[0]["cmd"]
    assert calls[0]["env"]["XGIF_APP_VERSION"] == APP_VERSION
    assert calls[0]["env"]["XGIF_APP_EXE_SOURCE"] == str(exe_path.resolve())
    assert calls[0]["cmd"][-1].endswith("installer\\xgif_setup.iss")
    assert installer_path.endswith(f"dist\\XGif_Setup_{APP_VERSION}.exe")


def test_nuitka_build_output_name_matches_release_contract(monkeypatch):
    calls = []

    monkeypatch.setattr(build_optimized, "_get_python_exe", lambda venv: "python.exe")
    monkeypatch.setattr(build_optimized.subprocess, "run", lambda cmd, check: calls.append(cmd))

    build_optimized.run_nuitka_build()

    assert calls
    assert "--output-filename=XGif.exe" in calls[0]


def test_build_keeps_debug_launcher_opt_in_only():
    source = Path("build_optimized.py").read_text(encoding="utf-8")

    assert "--diagnostic-launcher" in source
    assert "os.remove(diag_bat)" in source
    assert "if args.diagnostic_launcher:" in source


def test_windows_version_tuple_preserves_patch_versions():
    assert build_optimized._parse_windows_version_tuple("2.1.3") == (2, 1, 3, 0)
    assert build_optimized._parse_windows_version_tuple("2.1.3.4") == (2, 1, 3, 4)
    assert build_optimized._parse_windows_version_tuple("2.1.3-beta") == (2, 1, 3, 0)


def test_create_version_file_uses_full_app_version(tmp_path, monkeypatch):
    import core.version

    monkeypatch.setattr(build_optimized, "PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(core.version, "APP_VERSION", "2.1.3")

    version_file = build_optimized.create_version_file()
    content = Path(version_file).read_text(encoding="utf-8")

    assert "filevers=(2, 1, 3, 0)" in content
    assert "prodvers=(2, 1, 3, 0)" in content
    assert "StringStruct('FileVersion', '2.1.3')" in content
    assert "StringStruct('ProductVersion', '2.1.3')" in content


def test_generated_pyinstaller_spec_keeps_size_guards(tmp_path, monkeypatch):
    resources = tmp_path / "resources"
    resources.mkdir()
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("wxPython>=4.2.5\n", encoding="utf-8")
    requirements_gpu = tmp_path / "requirements-gpu.txt"
    requirements_gpu.write_text("cupy-cuda13x[ctk]==14.0.1\n", encoding="utf-8")
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
    assert "requirements-gpu.txt" in spec
    assert "'cv2'" in spec
    assert "'skimage'" in spec
    assert "upx=True" in spec
    assert "upx_exclude=['vcruntime*.dll', 'msvcp*.dll', 'wx*.dll']" in spec
