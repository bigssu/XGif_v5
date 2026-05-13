"""BootStrapper download integrity 회귀 테스트.

BootStrapper/ 는 별도 패키지로 동작하며 본체 sys.path 에서 import 되지 않는다.
함수 자체는 hashlib + os 만 사용하므로 source 를 직접 로드해 격리 검증한다.
download_file() 의 retry/네트워크 분기는 BAT 스모크 검증 영역 (수동).
"""
import ast
import hashlib
import types
from pathlib import Path


def _load_verify_sha256():
    """download_utils.py 에서 verify_sha256 만 stand-alone 로 로드."""
    src = Path("BootStrapper/download_utils.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    func = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "verify_sha256"
    )
    module = types.ModuleType("verify_sha256_isolated")
    module.__dict__.update({
        "hashlib": hashlib,
        "CHUNK_SIZE": 1024 * 256,
    })
    code = compile(ast.Module(body=[func], type_ignores=[]), "<verify>", "exec")
    exec(code, module.__dict__)
    return module.verify_sha256


def test_verify_sha256_returns_true_on_match(tmp_path):
    verify_sha256 = _load_verify_sha256()
    payload = b"vc_redist mock payload"
    expected = hashlib.sha256(payload).hexdigest()
    target = tmp_path / "installer.exe"
    target.write_bytes(payload)

    assert verify_sha256(str(target), expected) is True
    # case-insensitive
    assert verify_sha256(str(target), expected.upper()) is True


def test_verify_sha256_returns_false_on_mismatch(tmp_path):
    verify_sha256 = _load_verify_sha256()
    target = tmp_path / "installer.exe"
    target.write_bytes(b"actual payload")

    bogus = "0" * 64
    assert verify_sha256(str(target), bogus) is False


def test_verify_sha256_skips_when_expected_empty(tmp_path):
    verify_sha256 = _load_verify_sha256()
    target = tmp_path / "installer.exe"
    target.write_bytes(b"any")
    # 빈 expected 는 backwards-compat 를 위해 무조건 True (verification skipped)
    assert verify_sha256(str(target), "") is True


def test_verify_sha256_handles_missing_file_gracefully(tmp_path):
    verify_sha256 = _load_verify_sha256()
    missing = tmp_path / "not-here.exe"
    assert verify_sha256(str(missing), "0" * 64) is False


def test_download_file_signature_accepts_expected_sha256():
    """download_file() 의 시그니처에 expected_sha256 키워드가 노출돼야 한다.

    호출자(deps_installer 등) 가 향후 무결성 검증을 활성화할 때
    이 키워드를 통해 점진적으로 적용한다.
    """
    src = Path("BootStrapper/download_utils.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    func = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "download_file"
    )
    arg_names = {arg.arg for arg in func.args.args} | {arg.arg for arg in func.args.kwonlyargs}
    assert "expected_sha256" in arg_names, "download_file 시그니처에 expected_sha256 누락"


def test_download_file_expected_sha256_is_keyword_only():
    """`expected_sha256` 은 정확성 가드라 positional 6번째로 새는 것을 막는다."""
    src = Path("BootStrapper/download_utils.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    func = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "download_file"
    )
    positional = {arg.arg for arg in func.args.args}
    kwonly = {arg.arg for arg in func.args.kwonlyargs}
    assert "expected_sha256" in kwonly, \
        "expected_sha256 가 keyword-only 가 아님 — positional 잠재 오용 위험"
    assert "expected_sha256" not in positional, \
        "expected_sha256 가 positional 인자에 노출됨"


def test_setup_bat_advises_verifying_microsoft_signature():
    """BAT 가 vc_redist 다운로드 후 코드 서명 검증을 안내해야 한다."""
    bat = Path("BootStrapper/XGif_Setup.bat").read_text(encoding="utf-8")
    # 실제 BAT 는 한글 + ASCII 혼용. 핵심 신뢰 단어만 검증.
    assert "Microsoft" in bat
    # 다운로드 페이지 URL 은 그대로 유지
    assert "aka.ms/vs/17/release/vc_redist.x64.exe" in bat
