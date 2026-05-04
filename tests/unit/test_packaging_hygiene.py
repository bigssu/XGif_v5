from pathlib import Path


def test_selfsign_script_does_not_ship_a_default_pfx_password():
    script = Path("scripts/create_selfsign_cert.ps1").read_text(encoding="utf-8")

    assert '[string]$Password = ""' in script
    assert 'Password: $Password' not in script
    assert 'Password: [hidden]' in script
