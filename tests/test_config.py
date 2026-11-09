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


# --- Settings from config.yaml ---


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_config_file_uses_defaults(tmp_path: Path) -> None:
    result = config.load_config(tmp_path / "missing.yaml")

    assert result == config.Config()
    assert result.synthesis.device == "cpu"


def test_empty_config_file_uses_defaults(tmp_path: Path) -> None:
    assert config.load_config(write_config(tmp_path, "")) == config.Config()


def test_config_file_sets_device(tmp_path: Path) -> None:
    path = write_config(tmp_path, "synthesis:\n  device: cuda\n")

    assert config.load_config(path).synthesis.device == "cuda"


def test_empty_section_uses_defaults(tmp_path: Path) -> None:
    path = write_config(tmp_path, "synthesis:\n")

    assert config.load_config(path).synthesis.device == "cpu"


@pytest.mark.parametrize(
    "text",
    [
        "synthesis:\n  device: tpu\n",  # invalid value
        "synthesis:\n  devise: cuda\n",  # unknown key in a section
        "synthesis_typo:\n  device: cuda\n",  # unknown section
        "synthesis: cuda\n",  # section is not a mapping
        "- cuda\n",  # top level is not a mapping
    ],
)
def test_invalid_config_raises(tmp_path: Path, text: str) -> None:
    with pytest.raises(ValueError):
        config.load_config(write_config(tmp_path, text))


def test_config_path_env_var_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_config(tmp_path, "synthesis:\n  device: cuda\n")
    monkeypatch.setenv(config.CONFIG_PATH_ENV_VAR, str(path))

    assert config.config_path() == path
    assert config.load_config().synthesis.device == "cuda"


def test_module_config_is_loaded() -> None:
    assert isinstance(config.config, config.Config)


# --- server: section ---


def test_server_defaults_are_local_http() -> None:
    server = config.Config().server

    assert (server.host, server.port, server.dev_port, server.https) == (
        "127.0.0.1",
        7860,
        7861,
        False,
    )


def test_config_file_sets_server(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        "server:\n  host: 0.0.0.0\n  port: 8000\n  dev_port: 8001\n  https: true\n",
    )

    assert config.load_config(path).server == config.ServerConfig(
        host="0.0.0.0", port=8000, dev_port=8001, https=True
    )


@pytest.mark.parametrize(
    "text",
    [
        "server:\n  port: 0\n",  # port out of range
        "server:\n  dev_port: 70000\n",  # dev port out of range
        "server:\n  port: 7861\n",  # clashes with the default dev_port
        "server:\n  port: '7860'\n",  # not an integer
        "server:\n  https: yes please\n",  # not a boolean
        "server:\n  hots: 0.0.0.0\n",  # unknown key
    ],
)
def test_invalid_server_config_raises(tmp_path: Path, text: str) -> None:
    with pytest.raises(ValueError):
        config.load_config(write_config(tmp_path, text))
