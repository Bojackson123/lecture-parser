import pytest

import lecturenotes
from lecturenotes import cli


def test_version_is_nonempty_string() -> None:
    assert isinstance(lecturenotes.__version__, str)
    assert lecturenotes.__version__


def test_cli_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"lecturenotes {lecturenotes.__version__}"
