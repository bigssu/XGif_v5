from pathlib import Path

from PIL import Image

from core.version import APP_VERSION


def test_project_version_single_source_is_2_1_0():
    import tomllib

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert APP_VERSION == "2.1.0"
    assert pyproject["project"]["version"] == APP_VERSION


def test_installer_version_is_injected_not_hardcoded():
    script = Path("installer/xgif_setup.iss").read_text(encoding="utf-8")

    assert "0.56" not in script
    assert '#define MyAppVersion "0.56"' not in script
    assert "#ifndef MyAppVersion" in script
    assert 'GetEnv("XGIF_APP_VERSION")' in script
    assert "MyAppVersion is required" in script
    assert "OutputBaseFilename=XGif_Setup_{#MyAppVersion}" in script
    assert 'GetEnv("XGIF_APP_EXE_SOURCE")' in script
    assert "MyAppExeSource is required" in script
    assert 'Source: "..\\dist\\XGif.exe"' not in script
    assert 'Source: "{#MyAppExeSource}"' in script


def test_selfsign_script_does_not_ship_a_default_pfx_password():
    script = Path("scripts/create_selfsign_cert.ps1").read_text(encoding="utf-8")

    # 평문 [string]$Password 파라미터는 거부 — SecureString 만 허용
    assert '[string]$Password' not in script
    assert '[System.Security.SecureString]$Password' in script

    # 진행 로그에 평문 비밀번호가 노출되지 않아야 한다
    assert 'Password: $Password' not in script
    assert 'Password: [hidden]' in script


def test_selfsign_script_accepts_both_password_env_vars():
    """환경변수 alias 두 가지 모두 인식해야 사용자 혼동을 줄인다."""
    script = Path("scripts/create_selfsign_cert.ps1").read_text(encoding="utf-8")
    assert "XGIF_PFX_PASSWORD" in script
    assert "XGIF_SIGN_PASSWORD" in script


def test_sign_exe_script_requires_securestring_and_clears_plaintext():
    """sign_exe.ps1 — 평문 [string]$Password 파라미터 제거 + signtool 호출 시
    BSTR 추출 + ZeroFreeBSTR 패턴을 사용해야 한다."""
    script = Path("scripts/sign_exe.ps1").read_text(encoding="utf-8")

    assert '[System.Security.SecureString]$Password' in script, \
        "sign_exe.ps1 가 SecureString 파라미터를 강제하지 않음"
    # 평문 파라미터 선언은 없어야 한다
    assert '[string]$Password' not in script, \
        "sign_exe.ps1 에 평문 [string]$Password 파라미터가 남아 있음"

    # 환경변수 alias 인식
    assert 'XGIF_SIGN_PASSWORD' in script
    assert 'XGIF_PFX_PASSWORD' in script

    # signtool 호출 직전 BSTR 추출 + 즉시 ZeroFreeBSTR
    assert 'SecureStringToBSTR' in script, "SecureString → BSTR 변환 누락"
    assert 'ZeroFreeBSTR' in script, "BSTR 메모리 zero out 누락 (평문 잔류 위험)"


def test_setup_script_does_not_modify_windows_security_state():
    script = Path("BootStrapper/XGif_Setup.bat").read_text(encoding="utf-8")

    forbidden = [
        "Zone.Identifier",
        "-Stream",
        "Unblock-File",
        "Add-MpPreference",
        "Set-MpPreference",
        "Defender",
        "SmartScreen",
    ]
    lowered = script.lower()
    for token in forbidden:
        assert token.lower() not in lowered


def test_app_icon_background_is_transparent():
    image = Image.open("resources/Xgif_icon.png").convert("RGBA")
    alpha = image.getchannel("A")

    assert alpha.getextrema()[0] == 0
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((image.width - 1, image.height - 1))[3] == 0
