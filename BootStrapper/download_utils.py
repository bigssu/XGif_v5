"""
download_utils.py – Robust HTTP downloader with progress callbacks and retry.
"""

import hashlib
import os
import socket
import ssl
import time
import urllib.request
import urllib.error
from logging_setup import log_and_ui, get_logger
import contextlib

DEFAULT_TIMEOUT = 120  # seconds per request
MAX_RETRIES = 3
CHUNK_SIZE = 1024 * 256  # 256 KB


def _get_ssl_context() -> ssl.SSLContext:
    """certifi CA 번들이 있으면 사용, 없으면 시스템 기본 SSL 컨텍스트 반환"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def check_connectivity(timeout: int = 5) -> bool:
    """
    인터넷 연결 상태를 빠르게 확인.
    DNS 해석 + HTTPS HEAD 요청으로 확인한다.
    """
    test_hosts = [
        ("https://www.google.com", "www.google.com"),
        ("https://pypi.org", "pypi.org"),
    ]
    for url, host in test_hosts:
        try:
            # 1차: DNS 확인
            socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
            # 2차: HEAD 요청
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "EnvSetupApp/1.0"})
            ctx = _get_ssl_context()
            urllib.request.urlopen(req, timeout=timeout, context=ctx)
            return True
        except Exception:
            continue
    return False


def verify_sha256(path: str, expected_hex: str, *, chunk_size: int = CHUNK_SIZE) -> bool:
    """Return True if *path* hashes to *expected_hex* (case-insensitive SHA-256).

    Reads in CHUNK_SIZE blocks so large installers (50–100 MB) don't load
    fully into memory. Returns False on missing file or hash mismatch.
    """
    if not expected_hex:
        return True
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                block = f.read(chunk_size)
                if not block:
                    break
                digest.update(block)
        actual = digest.hexdigest().lower()
        return actual == expected_hex.lower()
    except (OSError, ValueError):
        return False


def download_file(
    url: str,
    dest_path: str,
    progress_cb=None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    expected_sha256: str = "",
) -> bool:
    """
    Download *url* to *dest_path*.

    progress_cb(downloaded_bytes, total_bytes_or_none) is called periodically.
    If *expected_sha256* is provided, the downloaded file is hash-verified and
    deleted on mismatch (treated as a failed attempt — retried up to
    *max_retries* times). Returns True on success.
    """
    logger = get_logger()
    dest_dir = os.path.dirname(dest_path)
    os.makedirs(dest_dir, exist_ok=True)

    for attempt in range(1, max_retries + 1):
        try:
            log_and_ui(f"다운로드 시작: {os.path.basename(dest_path)}  (시도 {attempt}/{max_retries})")
            logger.debug("URL: %s", url)

            req = urllib.request.Request(url, headers={"User-Agent": "EnvSetupApp/1.0"})
            ctx = _get_ssl_context()
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)

            total = resp.headers.get("Content-Length")
            total = int(total) if total else None

            downloaded = 0
            tmp_path = dest_path + ".part"
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)

            # SHA-256 검증: 부분 다운로드를 .part 상태에서 검증, 불일치 시 폐기
            if expected_sha256 and not verify_sha256(tmp_path, expected_sha256):
                logger.warning("SHA-256 mismatch for %s (expected %s)", url, expected_sha256)
                log_and_ui(f"다운로드 무결성 검증 실패: {os.path.basename(dest_path)}")
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)
                raise OSError(f"SHA-256 mismatch (expected {expected_sha256[:12]}…)")

            # Atomic rename
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(tmp_path, dest_path)

            size_mb = downloaded / (1024 * 1024)
            log_and_ui(f"다운로드 완료: {os.path.basename(dest_path)} ({size_mb:.1f} MB)")
            return True

        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
            logger.warning("Download attempt %d failed: %s", attempt, e)
            log_and_ui(f"다운로드 실패 (시도 {attempt}): {e}")
            # Clean up partial
            for p in (dest_path + ".part", dest_path):
                if os.path.exists(p):
                    with contextlib.suppress(OSError):
                        os.remove(p)
            if attempt < max_retries:
                wait = 2 ** attempt
                log_and_ui(f"{wait}초 후 재시도합니다…")
                time.sleep(wait)

    log_and_ui("다운로드 실패: 최대 재시도 횟수 초과")
    return False
