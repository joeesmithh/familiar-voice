"""Filesystem locations for local app data.

All voice samples, generated audio, and logs live under one data root so they
stay private and git-ignored. The root comes from the ``FV_DATA_DIR``
environment variable and defaults to ``./data``. Directory helpers create
their directory on demand; file helpers create the parent directory only.
"""

import os
from pathlib import Path

DATA_DIR_ENV_VAR = "FV_DATA_DIR"
DEFAULT_DATA_DIR = Path("data")


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
