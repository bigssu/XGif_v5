"""
download_utils.py – Robust HTTP downloader with progress callbacks and retry.
"""

import os
import time
import urllib.request
import urllib.error
from logging_setup import log_and_ui, get_logger

DEFAULT_TIMEOUT = 120  # seconds per request
MAX_RETRIES = 3
CHUNK_SIZE = 1024 * 256  # 256 KB


def download_file(
    url: str,
    dest_path: str,
    progress_cb=None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> bool:
    """
    Download *url* to *dest_path*.

    progress_cb(downloaded_bytes, total_bytes_or_none) is called periodically.
    Returns True on success.
    """
    logger = get_logger()
    dest_dir = os.path.dirname(dest_path)
    os.makedirs(dest_dir, exist_ok=True)

    for attempt in range(1, max_retries + 1):
        try:
            log_and_ui(f"다운로드 시작: {os.path.basename(dest_path)}  (시도 {attempt}/{max_retries})")
            logger.debug("URL: %s", url)

            req = urllib.request.Request(url, headers={"User-Agent": "EnvSetupApp/1.0"})
            resp = urllib.request.urlopen(req, timeout=timeout)

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
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            if attempt < max_retries:
                wait = 2 ** attempt
                log_and_ui(f"{wait}초 후 재시도합니다…")
                time.sleep(wait)

    log_and_ui("다운로드 실패: 최대 재시도 횟수 초과")
    return False
