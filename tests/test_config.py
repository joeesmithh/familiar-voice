# pytest finds tests by name: files named test_*.py and functions named
# test_*. Each test passes if it finishes without an exception; a failed
# `assert` raises one, and pytest reports the values on both sides.

from collections.abc import Callable
from pathlib import Path

import pytest

from familiar_voice.core import config


# `data_dir` is not imported: pytest sees the parameter name, finds the
# fixture of that name in conftest.py, and passes in its return value.
def test_data_dir_uses_env_var_and_creates_it(data_dir: Path) -> None:
    # The fixture only sets the env var; the folder should not exist yet.
    assert not data_dir.exists()

    result = config.data_dir()

    assert result == data_dir
    assert result.is_dir()


def test_data_dir_defaults_to_local_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Remove FV_DATA_DIR in case it is set in the shell running the tests.
    # raising=False means "don't fail if it was not set in the first place".
    monkeypatch.delenv(config.DATA_DIR_ENV_VAR, raising=False)
    # Run from the temp dir so the default ./data is created there, not in the
    # repo. monkeypatch restores the original working directory afterwards.
    monkeypatch.chdir(tmp_path)

    result = config.data_dir()

    # The default is the relative path "data", so resolve() both sides to
    # absolute paths before comparing.
    assert result.resolve() == (tmp_path / "data").resolve()
    assert result.is_dir()


# @pytest.mark.parametrize runs the same test once per item in the list.
# The first argument names the test parameters; each tuple in the list fills
# them in. Here the test runs twice: once with (samples_dir, "samples") and
# once with (library_dir, "library"), each reported as a separate test.
# `helper` is the function itself (not called yet), so the test calls it.
@pytest.mark.parametrize(
    ("helper", "name"),
    [(config.samples_dir, "samples"), (config.library_dir, "library")],
)
def test_subdirectories_are_created_under_data_dir(
    data_dir: Path, helper: Callable[[], Path], name: str
) -> None:
    # Fixtures (data_dir) and parametrize values (helper, name) can be mixed
    # in one parameter list; pytest fills in each by name.
    result = helper()

    assert result == data_dir / name
    assert result.is_dir()


# Same pattern as above, run three times, for helpers that return file paths.
@pytest.mark.parametrize(
    ("helper", "name"),
    [
        (config.phrases_path, "phrases.json"),
        (config.log_path, "log.jsonl"),
        (config.checkins_path, "checkins.json"),
    ],
)
def test_file_paths_resolve_under_data_dir(
    data_dir: Path, helper: Callable[[], Path], name: str
) -> None:
    result = helper()

    assert result == data_dir / name
    # File helpers create the parent folder but leave the file itself for the
    # caller to write.
    assert result.parent.is_dir()
    assert not result.exists()
