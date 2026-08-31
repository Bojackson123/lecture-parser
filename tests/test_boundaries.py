"""Package-boundary rules (plan §5), enforced from plain ``pytest``.

Runs import-linter against the contracts in ``pyproject.toml`` so a boundary violation
fails the one command every session runs, not only the separate ``uv run lint-imports``.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def _lint_imports_executable() -> str:
    """``lint-imports`` from the interpreter's own environment, falling back to PATH."""
    scripts_dir = str(Path(sys.executable).parent)
    found = shutil.which("lint-imports", path=scripts_dir) or shutil.which("lint-imports")
    assert found, "lint-imports is not installed; run `uv sync --all-groups`"
    return found


def test_import_linter_contracts_hold(repo_root: Path) -> None:
    result = subprocess.run(
        [_lint_imports_executable()],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"import-linter found a boundary violation (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "0 broken" in result.stdout, result.stdout
