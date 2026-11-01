# conftest.py is a special file that pytest loads automatically before running
# any test in this directory. Fixtures defined here are available to every
# test file without importing them.

from pathlib import Path

import pytest

from familiar_voice.core.config import DATA_DIR_ENV_VAR


# @pytest.fixture turns this function into reusable setup code.
# A test asks for it by naming `data_dir` as a parameter, and pytest calls this
# function and passes in the return value. A fresh copy runs for each test.
#
# This fixture's own parameters are built-in pytest fixtures:
#   - tmp_path: a new, empty temporary directory unique to this test.
#   - monkeypatch: changes env vars, attributes, or the working directory, and
#     un-does every change automatically when the test finishes.
@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``FV_DATA_DIR`` at a fresh temporary directory for one test."""
    # A subfolder that does not exist yet, so tests can check that the code
    # under test creates it.
    root = tmp_path / "data"
    # Set FV_DATA_DIR for this test only, so tests never touch the real data/.
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(root))
    return root
