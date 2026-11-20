"""
extract_utils.py – Staged Zip extraction with rollback on promotion failure.
"""

import os
import shutil
import tempfile
import zipfile
from logging_setup import log_and_ui, get_logger



def extract_zip(
    zip_path: str,
    final_dir: str,
    expected_file: str | tuple[str, ...] | None = None,
    flatten_single_root: bool = True,
    progress_cb=None,
    *,
    flatten_bin=False,
    check_staged=None,
) -> bool:
    """
    Extract and verify in a temp folder, then replace with rollback on failure.

    If *flatten_single_root* is True and the zip has a single top-level
    directory, move its contents up so they sit directly inside *final_dir*.

    *expected_file* (relative to *final_dir*) is checked after extraction
    to confirm success.

    Returns True on success.
    """
    logger = get_logger()
    final_dir = os.path.abspath(final_dir)
    workspace = None
    backup = None

    try:
        os.makedirs(os.path.dirname(final_dir), exist_ok=True)
        workspace = tempfile.mkdtemp(prefix=f".{os.path.basename(final_dir)}-", dir=os.path.dirname(final_dir))
        temp_extract = os.path.join(workspace, "extracted")
        os.mkdir(temp_extract)

        log_and_ui(f"압축 해제 중: {os.path.basename(zip_path)}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            total = len(members)
            for idx, member in enumerate(members, 1):
                zf.extract(member, temp_extract)
                if progress_cb and idx % max(1, total // 20) == 0:
                    progress_cb(idx, total)

        staged = temp_extract
        # Flatten single root directory if present
        if flatten_single_root:
            entries = os.listdir(temp_extract)
            if len(entries) == 1:
                single = os.path.join(temp_extract, entries[0])
                if os.path.isdir(single):
                    logger.debug("Flattening single root dir: %s", entries[0])
                    staged = single

        if flatten_bin:
            bin_dir = os.path.join(staged, "bin")
            for entry in os.scandir(bin_dir):
                os.rename(entry.path, os.path.join(staged, entry.name))
            os.rmdir(bin_dir)
        required = (expected_file,) if isinstance(expected_file, str) else expected_file or ()
        if not all(_verify(staged, name) for name in required):
            return False
        if check_staged:
            ok, detail = check_staged(staged)
            if not ok:
                log_and_ui(detail)
                return False

        if os.path.lexists(final_dir):
            previous = os.path.join(workspace, "previous")
            os.rename(final_dir, previous)
            backup = previous
        try:
            os.rename(staged, final_dir)
        except OSError:
            if backup is not None:
                os.rename(backup, final_dir)
                backup = None
            raise
        backup = None
        log_and_ui("압축 해제 완료")
        return True

    except (zipfile.BadZipFile, OSError) as e:
        logger.error("Extraction failed: %s", e)
        log_and_ui(f"압축 해제 실패: {e}")
        if backup is not None:
            log_and_ui(f"기존 설치 복원 실패 – 백업 보존: {backup}")
        return False
    finally:
        # A failed rollback must leave its only surviving installation intact.
        if workspace is not None and backup is None:
            shutil.rmtree(workspace, ignore_errors=True)


def _verify(final_dir: str, expected_file: str) -> bool:
    full = os.path.join(final_dir, expected_file)
    if os.path.isfile(full) and os.path.getsize(full) > 0:
        return True
    log_and_ui(f"압축 해제 후 확인 실패: {expected_file} 없음 또는 빈 파일")
    return False
