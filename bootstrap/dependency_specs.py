"""
dependency_specs.py — 의존성 선언 (Single Source of Truth)

새 의존성을 추가하려면:
  1) get_dependencies() 리스트에 Dependency 항목 추가
  2) dependency_checker.py 의 _CHECKERS 에 _check_{id} 등록
  3) dependency_installer.py 의 _INSTALLERS 에 _install_{id} 등록 (자동 설치 시)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, List


# ── 앱 이름 (로그 · 마커 경로에 사용) ─────────────────────
APP_NAME = "YourApp"


# ── 상태 Enum ─────────────────────────────────────────────

class DepStatus(str, Enum):
    UNCHECKED = "unchecked"
    CHECKING = "checking"
    PASS = "pass"
    MISSING = "missing"
    SKIPPED = "skipped"          # 사용자가 선택 항목을 건너뜀
    INSTALLING = "installing"
    INSTALL_OK = "install_ok"
    INSTALL_FAIL = "install_fail"
    ERROR = "error"


STATUS_LABELS: dict[DepStatus, str] = {
    DepStatus.UNCHECKED: "확인 대기",
    DepStatus.CHECKING: "확인 중\u2026",
    DepStatus.PASS: "설치됨",
    DepStatus.MISSING: "미설치",           # 실제 표시는 UI에서 필수/선택에 따라 분기
    DepStatus.SKIPPED: "건너뜀",
    DepStatus.INSTALLING: "설치 중\u2026",
    DepStatus.INSTALL_OK: "설치 완료",
    DepStatus.INSTALL_FAIL: "설치 실패",
    DepStatus.ERROR: "오류",
}


# ── 데이터 모델 ───────────────────────────────────────────

@dataclass
class Dependency:
    """의존성 항목.

    Attributes:
        id:           고유 식별자 (_check_{id} / _install_{id} 매핑)
        display_name: UI 표시 이름
        required:     필수 여부
        description:  설명
        help_url:     수동 설치 안내 URL
        pip_name:     pip install 패키지 이름
        import_name:  import 모듈 이름
    """
    id: str
    display_name: str
    required: bool = True
    description: str = ""
    help_url: str = ""
    pip_name: str = ""
    import_name: str = ""

    # 런타임 상태 (mutable)
    status: DepStatus = field(default=DepStatus.UNCHECKED)
    detail: str = field(default="", repr=False)

    @property
    def required_label(self) -> str:
        return "필수" if self.required else "선택"

    @property
    def is_satisfied(self) -> bool:
        return self.status in (DepStatus.PASS, DepStatus.INSTALL_OK, DepStatus.SKIPPED)


# ── 의존성 목록 ──────────────────────────────────────────

def get_dependencies() -> List[Dependency]:
    """의존성 목록을 반환합니다 (Single Source of Truth).

    새 항목을 추가하려면 이 리스트에 Dependency 를 추가하세요.
    """
    return [
        # ── 런타임 ────────────────────────────────────
        Dependency(
            id="python",
            display_name="Python 3.11",
            required=True,
            description="Python 3.11 이상 런타임",
            help_url="https://www.python.org/downloads/",
        ),
        Dependency(
            id="pip",
            display_name="pip",
            required=True,
            description="Python 패키지 관리자",
        ),

        # ── 시스템 구성요소 ────────────────────────────
        Dependency(
            id="vcredist",
            display_name="Visual C++ Redistributable",
            required=True,
            description="Microsoft VC++ 2015-2022 (x64)",
            help_url="https://aka.ms/vs/17/release/vc_redist.x64.exe",
        ),

        # ── GPU (선택) ────────────────────────────────
        Dependency(
            id="cupy",
            display_name="CuPy (GPU 가속)",
            required=False,
            description="CUDA GPU 가속 라이브러리",
            pip_name="cupy-cuda12x",
            import_name="cupy",
            help_url="https://docs.cupy.dev/en/stable/install.html",
        ),
    ]
