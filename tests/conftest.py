"""공통 pytest fixture."""

import os
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    """임시 디렉토리 fixture."""
    d = tempfile.mkdtemp(prefix="xgif_test_")
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def tmp_ini(tmp_dir):
    """임시 config.ini 경로 fixture."""
    return os.path.join(tmp_dir, "config.ini")
