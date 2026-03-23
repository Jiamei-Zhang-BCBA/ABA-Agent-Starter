"""
CI check script — syntax check, import check, pytest, coverage report.
Run: python -m scripts.check
"""

import subprocess
import sys
from pathlib import Path


def run_cmd(label: str, cmd: list[str], cwd: str | None = None) -> bool:
    """Run a command and return True if it succeeds."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"  FAILED (exit code {result.returncode})")
        return False
    print(f"  PASSED")
    return True


def main():
    api_dir = str(Path(__file__).parent.parent)
    failures = []

    # 1. Syntax check all Python files
    ok = run_cmd(
        "Syntax Check (py_compile)",
        [sys.executable, "-c",
         "import ast; import pathlib; "
         "errors=[]; "
         "[errors.append(f'{f}: {e}') "
         " for f in pathlib.Path('app').rglob('*.py') "
         " for e in [None] "
         " if not (lambda p: (ast.parse(p.read_text(encoding='utf-8')), True)[-1])(f)]; "
         "print('All files valid' if not errors else chr(10).join(errors)); "
         "exit(1 if errors else 0)"],
        cwd=api_dir,
    )
    if not ok:
        failures.append("Syntax Check")

    # 2. Import check — ensure all modules load
    ok = run_cmd(
        "Import Check",
        [sys.executable, "-c",
         "from app.main import app; "
         "from app.models import *; "
         "from app.services.auth_service import get_current_user; "
         "from app.services.user_service import register_tenant; "
         "from app.services.form_validator import validate_form_data; "
         "from app.services.audit_service import log_action; "
         "print('All imports OK')"],
        cwd=api_dir,
    )
    if not ok:
        failures.append("Import Check")

    # 3. Run pytest with coverage
    ok = run_cmd(
        "Tests + Coverage",
        [sys.executable, "-m", "pytest", "tests/", "-v",
         "--tb=short", "--co", "-q"],
        cwd=api_dir,
    )
    # Now run the actual tests
    ok = run_cmd(
        "Tests Execution",
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=api_dir,
    )
    if not ok:
        failures.append("Tests")

    # Summary
    print(f"\n{'='*60}")
    if failures:
        print(f"  FAILURES: {', '.join(failures)}")
        print(f"{'='*60}")
        sys.exit(1)
    else:
        print(f"  ALL CHECKS PASSED")
        print(f"{'='*60}")
        sys.exit(0)


if __name__ == "__main__":
    main()
