"""App settings from ``config.yaml`` and filesystem locations for local app data.

Settings are read once at import from ``config.yaml`` (or the file named by the
``FV_CONFIG`` environment variable) into frozen dataclasses, exposed as the
module-level ``config`` object::

    from familiar_voice.core.config import config

    config.synthesis.device  # "cpu" or "cuda"

All voice samples, generated audio, and logs live under one data root so they
stay private and git-ignored. The root comes from the ``FV_DATA_DIR``
environment variable and defaults to ``./data``; the developer console
defaults to ``./data_dev_tools`` instead. Directory helpers create
their directory on demand; file helpers create the parent directory only.
"""

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

import yaml

DATA_DIR_ENV_VAR = "FV_DATA_DIR"
DEFAULT_DATA_DIR = Path("data")
DEV_TOOLS_DATA_DIR = Path("data_dev_tools")  # default for the dev console


def _ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """Return the data root directory, creating it if needed.

    Returns
    -------
    Path
        The value of ``FV_DATA_DIR`` if set, otherwise ``./data``.
    """
    root = os.environ.get(DATA_DIR_ENV_VAR)
    return _ensure_dir(Path(root) if root else DEFAULT_DATA_DIR)


def samples_dir() -> Path:
    """Return the directory holding the caregiver's voice samples.

    Returns
    -------
    Path
        ``<data root>/samples``, created if needed.
    """
    return _ensure_dir(data_dir() / "samples")


def library_dir() -> Path:
    """Return the directory holding pre-generated phrase audio.

    Returns
    -------
    Path
        ``<data root>/library``, created if needed.
    """
    return _ensure_dir(data_dir() / "library")


def phrases_path() -> Path:
    """Return the path of the caregiver's phrase file.

    Returns
    -------
    Path
        ``<data root>/phrases.json``. The file itself is not created.
    """
    return data_dir() / "phrases.json"


def log_path() -> Path:
    """Return the path of the interaction log.

    Returns
    -------
    Path
        ``<data root>/log.jsonl``. The file itself is not created.
    """
    return data_dir() / "log.jsonl"


def checkins_path() -> Path:
    """Return the path of the scheduled check-in file.

    Returns
    -------
    Path
        ``<data root>/checkins.json``. The file itself is not created.
    """
    return data_dir() / "checkins.json"


# --- Settings from config.yaml ---------------------------------------------

CONFIG_PATH_ENV_VAR = "FV_CONFIG"
DEFAULT_CONFIG_PATH = Path("config.yaml")
DEVICES = ("cpu", "cuda")  # where voice synthesis runs

_T = TypeVar("_T")


@dataclass(frozen=True)
class SynthesisConfig:
    """Settings for voice synthesis.

    Attributes
    ----------
    device : str
        Where the voice model runs: ``"cpu"`` or ``"cuda"`` (Nvidia GPU).

    Raises
    ------
    ValueError
        If `device` is not one of ``DEVICES``.
    """

    device: str = "cpu"

    def __post_init__(self) -> None:
        """Reject unsupported devices."""
        if self.device not in DEVICES:
            raise ValueError(
                f"synthesis.device must be one of {DEVICES}, got {self.device!r}."
            )


@dataclass(frozen=True)
class ServerConfig:
    """Settings for serving the web apps.

    Attributes
    ----------
    host : str
        Address to listen on: ``"127.0.0.1"`` serves this PC only,
        ``"0.0.0.0"`` accepts connections from other machines.
    port : int
        Port for the main Caregiver/User app.
    dev_port : int
        Port for the developer console, so both apps can run at once.
    https : bool
        Serve over HTTPS with a self-signed certificate. Browsers allow mic
        recording only over HTTPS or on localhost.

    Raises
    ------
    ValueError
        If a port is outside 1-65535 or both ports are the same.
    """

    host: str = "127.0.0.1"
    port: int = 7860
    dev_port: int = 7861
    https: bool = False

    def __post_init__(self) -> None:
        """Reject invalid or clashing ports."""
        for name in ("port", "dev_port"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"server.{name} must be an integer, got {value!r}.")
            if not 1 <= value <= 65535:
                raise ValueError(f"server.{name} must be 1-65535, got {value}.")
        if self.port == self.dev_port:
            raise ValueError("server.port and server.dev_port must differ.")
        if not isinstance(self.https, bool):
            raise ValueError(f"server.https must be true or false, got {self.https!r}.")


@dataclass(frozen=True)
class Config:
    """All app settings, one attribute per ``config.yaml`` section.

    Attributes
    ----------
    synthesis : SynthesisConfig
        The ``synthesis:`` section.
    server : ServerConfig
        The ``server:`` section.
    """

    synthesis: SynthesisConfig = field(default_factory=SynthesisConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


def config_path() -> Path:
    """Return the path of the settings file.

    Returns
    -------
    Path
        The value of ``FV_CONFIG`` if set, otherwise ``./config.yaml``.
    """
    path = os.environ.get(CONFIG_PATH_ENV_VAR)
    return Path(path) if path else DEFAULT_CONFIG_PATH


def _check_keys(cls: type, data: dict, section: str) -> None:
    """Raise ``ValueError`` if `data` has keys that `cls` has no field for."""
    unknown = sorted(set(data) - {f.name for f in fields(cls)})
    if unknown:
        raise ValueError(f"Unknown keys in config section {section!r}: {unknown}")


def _build(cls: type[_T], data: Any, section: str) -> _T:
    """Construct dataclass `cls` from mapping `data`, rejecting unknown keys."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"Config section {section!r} must be a mapping.")
    _check_keys(cls, data, section)
    return cls(**data)


def load_config(path: Path | None = None) -> Config:
    """Read settings from a YAML file.

    Parameters
    ----------
    path : Path, optional
        The file to read. Defaults to :func:`config_path`.

    Returns
    -------
    Config
        The parsed settings. Keys missing from the file, or a missing or
        empty file, fall back to the dataclass defaults.

    Raises
    ------
    ValueError
        If the file has an unknown key, a section that is not a mapping, or
        an invalid value.
    """
    path = config_path() if path is None else Path(path)
    if not path.is_file():
        return Config()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return Config()
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping of sections.")
    _check_keys(Config, data, "<top level>")
    return Config(
        synthesis=_build(SynthesisConfig, data.get("synthesis"), "synthesis"),
        server=_build(ServerConfig, data.get("server"), "server"),
    )


config: Config = load_config()
"""App settings, loaded once at import."""
