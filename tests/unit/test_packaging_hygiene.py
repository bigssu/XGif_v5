from pathlib import Path

from PIL import Image


def test_selfsign_script_does_not_ship_a_default_pfx_password():
    script = Path("scripts/create_selfsign_cert.ps1").read_text(encoding="utf-8")

    assert '[string]$Password = ""' in script
    assert 'Password: $Password' not in script
    assert 'Password: [hidden]' in script


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
