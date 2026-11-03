"""Pluggable text-to-speech interface for voice-cloning engines.

Every engine turns one piece of text plus the caregiver's reference samples
into a WAV file. Callers use :func:`synthesize` and never import an engine
class directly, so XTTS-v2, Tortoise, or a test double can be swapped by
name. The engine is chosen by the ``engine`` argument, else by the
``FV_ENGINE`` environment variable, else ``xtts``.
"""

import os
import tempfile
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Protocol

import numpy as np
import soundfile as sf

from familiar_voice.core.config import data_dir

ENGINE_ENV_VAR = "FV_ENGINE"
DEFAULT_ENGINE = "xtts"


class Engine(Protocol):
    """Anything that can speak text in a cloned voice."""

    def synthesize(
        self, text: str, ref_wavs: Sequence[Path], lang: str, out_path: Path
    ) -> None:
        """Write `text` spoken in the voice of `ref_wavs` to `out_path`."""
        ...


class FakeEngine:
    """Test engine that writes a sine tone instead of speech.

    The tone lasts longer for longer text, so code that depends on audio
    length behaves realistically. It needs no model weights and runs in
    milliseconds, and it ignores `ref_wavs` and `lang`.
    """

    SAMPLE_RATE = 24_000  # Hz, matches the XTTS-v2 output rate
    FREQUENCY = 440.0  # Hz
    AMPLITUDE = 0.3  # well below full scale to avoid clipping
    SECONDS_PER_CHAR = 0.02
    MIN_SECONDS = 0.2
    MAX_SECONDS = 5.0

    def duration(self, text: str) -> float:
        """Return the tone length in seconds for `text`.

        Parameters
        ----------
        text : str
            The text being "spoken".

        Returns
        -------
        float
            Seconds, growing with text length and clamped to
            ``[MIN_SECONDS, MAX_SECONDS]``.
        """
        seconds = len(text) * self.SECONDS_PER_CHAR
        return min(max(seconds, self.MIN_SECONDS), self.MAX_SECONDS)

    def synthesize(
        self, text: str, ref_wavs: Sequence[Path], lang: str, out_path: Path
    ) -> None:
        """Write a mono sine-tone WAV whose length scales with `text`.

        Parameters
        ----------
        text : str
            The text being "spoken".
        ref_wavs : Sequence[Path]
            Ignored.
        lang : str
            Ignored.
        out_path : Path
            Where to write the WAV file.
        """
        n_samples = round(self.duration(text) * self.SAMPLE_RATE)
        t = np.arange(n_samples) / self.SAMPLE_RATE
        tone = self.AMPLITUDE * np.sin(2 * np.pi * self.FREQUENCY * t)
        sf.write(out_path, tone.astype(np.float32), self.SAMPLE_RATE)


class XTTSEngine:
    """Coqui XTTS-v2 zero-shot voice-cloning engine (not implemented yet)."""

    def synthesize(
        self, text: str, ref_wavs: Sequence[Path], lang: str, out_path: Path
    ) -> None:
        """Raise, because the XTTS-v2 engine is not implemented yet.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError(
            f"The XTTS-v2 engine is not implemented yet; set {ENGINE_ENV_VAR}=fake."
        )


ENGINES: dict[str, type[Engine]] = {
    "fake": FakeEngine,
    "xtts": XTTSEngine,
}


@cache
def get_engine(name: str) -> Engine:
    """Return the shared instance of the engine registered as `name`.

    Instances are cached, so a heavy engine loads its model only once per
    process.

    Parameters
    ----------
    name : str
        A key of `ENGINES`, such as ``"fake"`` or ``"xtts"``.

    Returns
    -------
    Engine
        The engine instance.

    Raises
    ------
    ValueError
        If no engine is registered under `name`.
    """
    try:
        engine_class = ENGINES[name]
    except KeyError:
        raise ValueError(
            f"Unknown engine {name!r}; expected one of {sorted(ENGINES)}."
        ) from None
    return engine_class()


def synthesize(
    text: str,
    ref_wavs: Sequence[Path],
    lang: str = "en",
    out_path: Path | None = None,
    engine: str | Engine | None = None,
) -> Path:
    """Speak `text` in the voice of `ref_wavs` and save it as a WAV file.

    Parameters
    ----------
    text : str
        The phrase to speak. Must contain non-whitespace characters.
    ref_wavs : Sequence[Path]
        The caregiver's preprocessed voice samples.
    lang : str, optional
        Language code of `text`, such as ``"en"`` or ``"es"``.
    out_path : Path or None, optional
        Where to write the WAV. Parent directories are created. ``None``
        writes a new uniquely named file in the data root.
    engine : str, Engine, or None, optional
        A registered engine name, an engine instance, or ``None`` to use
        the ``FV_ENGINE`` environment variable (default ``xtts``).

    Returns
    -------
    Path
        The path of the written WAV file.

    Raises
    ------
    ValueError
        If `text` is blank or the engine name is unknown.
    """
    if not text.strip():
        raise ValueError("text must not be blank.")
    resolved = _resolve_engine(engine)

    if out_path is None:
        out_path = _new_temp_wav()
    else:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

    resolved.synthesize(text, [Path(p) for p in ref_wavs], lang, out_path)
    return out_path


def _resolve_engine(engine: str | Engine | None) -> Engine:
    """Turn a name, instance, or ``None`` into an engine instance."""
    if engine is None:
        engine = os.environ.get(ENGINE_ENV_VAR) or DEFAULT_ENGINE
    if isinstance(engine, str):
        return get_engine(engine)
    return engine


def _new_temp_wav() -> Path:
    """Create an empty, uniquely named WAV file in the data root."""
    # Kept inside the data root (not the system temp dir) so generated
    # caregiver-voice audio stays in the private, git-ignored folder.
    fd, name = tempfile.mkstemp(suffix=".wav", prefix="synth_", dir=data_dir())
    os.close(fd)
    return Path(name)
