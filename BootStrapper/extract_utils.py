"""
extract_utils.py – Zip extraction with atomic move.
"""

import os
import shutil
import zipfile
from logging_setup import log_and_ui, get_logger



def extract_zip(
    zip_path: str,
    final_dir: str,
    expected_file: str | None = None,
    flatten_single_root: bool = True,
    progress_cb=None,
) -> bool:
    """
    Extract *zip_path* into *final_dir* via a temp folder (atomic).

    If *flatten_single_root* is True and the zip has a single top-level
    directory, move its contents up so they sit directly inside *final_dir*.

    *expected_file* (relative to *final_dir*) is checked after extraction
    to confirm success.

    Returns True on success.
    """
    logger = get_logger()
    temp_extract = final_dir + "_tmp_extract"

    try:
        # Clean up any previous partial extraction
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract, ignore_errors=True)
        os.makedirs(temp_extract, exist_ok=True)

        log_and_ui(f"압축 해제 중: {os.path.basename(zip_path)}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            total = len(members)
            for idx, member in enumerate(members, 1):
                zf.extract(member, temp_extract)
                if progress_cb and idx % max(1, total // 20) == 0:
                    progress_cb(idx, total)

        # Flatten single root directory if present
        if flatten_single_root:
            entries = os.listdir(temp_extract)
            if len(entries) == 1:
                single = os.path.join(temp_extract, entries[0])
                if os.path.isdir(single):
                    logger.debug("Flattening single root dir: %s", entries[0])
                    temp_extract_inner = single

                    # Replace final_dir atomically
                    if os.path.exists(final_dir):
                        shutil.rmtree(final_dir, ignore_errors=True)
                        if os.path.exists(final_dir):
                            raise OSError(f"기존 폴더를 삭제할 수 없습니다: {final_dir}")
                    shutil.move(temp_extract_inner, final_dir)
                    # Remove the now-empty outer temp dir
                    shutil.rmtree(temp_extract, ignore_errors=True)

                    return _verify(final_dir, expected_file)

        # No flattening needed – move temp → final
        if os.path.exists(final_dir):
            shutil.rmtree(final_dir, ignore_errors=True)
            if os.path.exists(final_dir):
                raise OSError(f"기존 폴더를 삭제할 수 없습니다: {final_dir}")
        shutil.move(temp_extract, final_dir)

        return _verify(final_dir, expected_file)

    except (zipfile.BadZipFile, OSError) as e:
        logger.error("Extraction failed: %s", e)
        log_and_ui(f"압축 해제 실패: {e}")
        # Cleanup: temp_extract와 불완전한 final_dir 모두 정리
        for d in (temp_extract, final_dir):
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)
        return False


def _verify(final_dir: str, expected_file: str | None) -> bool:
    if expected_file is None:
        log_and_ui("압축 해제 완료")
        return True
    full = os.path.join(final_dir, expected_file)
    if os.path.isfile(full):
        log_and_ui("압축 해제 완료 – 확인 파일 존재")
        return True
    else:
        log_and_ui(f"압축 해제 후 확인 실패: {expected_file} 없음")
        return False
