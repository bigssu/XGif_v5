"""Bootstrap — 환경 진단 (Environment Diagnostic)

사용법:
    from bootstrap.app_entry import run
    run()
"""
from .app_entry import run as bootstrap_run
from .env_diagnostic_ui import EnvDiagnosticDialog
from .dependency_specs import get_dependencies, Dependency, DepStatus
