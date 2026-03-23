"""
Database migration helper.
Run: python -m scripts.migrate [upgrade|downgrade|current|history]

For production Docker: python -m scripts.migrate upgrade
"""

import subprocess
import sys
from pathlib import Path


def main():
    api_dir = str(Path(__file__).parent.parent)
    action = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    revision = sys.argv[2] if len(sys.argv) > 2 else "head"

    if action == "upgrade":
        cmd = ["alembic", "upgrade", revision]
    elif action == "downgrade":
        cmd = ["alembic", "downgrade", revision]
    elif action == "current":
        cmd = ["alembic", "current"]
    elif action == "history":
        cmd = ["alembic", "history", "--verbose"]
    elif action == "generate":
        msg = revision if revision != "head" else "auto migration"
        cmd = ["alembic", "revision", "--autogenerate", "-m", msg]
    else:
        print(f"Unknown action: {action}")
        print("Usage: python -m scripts.migrate [upgrade|downgrade|current|history|generate] [revision]")
        sys.exit(1)

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=api_dir)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
