"""Pluggable text-to-speech interface for voice-cloning engines.

Every engine turns one piece of text plus the caregiver's reference samples
into a WAV file. Callers use :func:`synthesize` and never import an engine
class directly, so XTTS-v2, Tortoise, or a test double can be swapped by
name. The engine is chosen by the ``engine`` argument, else by the
``FV_ENGINE`` environment variable, else ``xtts``. XTTS-v2 needs coqui-tts; it
accepts the Coqui model license itself and loads its model only when first
used, on the device set by ``synthesis.device`` in ``config.yaml`` (``cpu`` or
``cuda``).
"""

import logging
import os
import tempfile
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import numpy as np
import soundfile as sf

from familiar_voice.core.config import config, data_dir

if TYPE_CHECKING:
    from TTS.api import TTS

logger = logging.getLogger(__name__)

ENGINE_ENV_VAR = "FV_ENGINE"
DEFAULT_ENGINE = "xtts"
TOS_ENV_VAR = "COQUI_TOS_AGREED"  # coqui-tts reads this to skip its license prompt


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
    """Coqui XTTS-v2 zero-shot voice-cloning engine, on the CPU or an Nvidia GPU.

    The model (about 1.8 GB) downloads on first use and loads lazily on the
    first call to :meth:`synthesize` or :meth:`load`, then stays in memory.
    Loading accepts the Coqui Public Model License by setting
    ``COQUI_TOS_AGREED=1``, so coqui-tts never blocks on an interactive prompt.

    Parameters
    ----------
    device : str or None, optional
        ``"cpu"`` or ``"cuda"``. ``None`` uses ``synthesis.device`` from
        ``config.yaml``.
    """

    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self, device: str | None = None) -> None:
        self.device = device or config.synthesis.device
        self._tts: TTS | None = None

    def load(self) -> None:
        """Load the XTTS-v2 model onto `device` if it is not loaded yet.

        Raises
        ------
        ImportError
            If coqui-tts is not installed.
        RuntimeError
            If `device` is ``"cuda"`` but PyTorch cannot use a CUDA GPU.
        """
        if self._tts is not None:
            return
        # This project accepts the Coqui Public Model License (non-commercial
        # use, which covers coursework). coqui-tts reads this variable to skip
        # its interactive license prompt.
        os.environ.setdefault(TOS_ENV_VAR, "1")
        self._tts = _load_xtts(self.MODEL_NAME, self.device)

    def synthesize(
        self, text: str, ref_wavs: Sequence[Path], lang: str, out_path: Path
    ) -> None:
        """Write `text` spoken in the cloned voice of `ref_wavs` to `out_path`.

        Parameters
        ----------
        text : str
            The phrase to speak.
        ref_wavs : Sequence[Path]
            Preprocessed caregiver samples; XTTS-v2 needs about 6 s in total.
        lang : str
            XTTS-v2 language code, such as ``"en"`` or ``"es"``.
        out_path : Path
            Where to write the 24 kHz WAV file.

        Raises
        ------
        ValueError
            If `ref_wavs` is empty.
        FileNotFoundError
            If a reference sample does not exist.
        """
        if not ref_wavs:
            raise ValueError("XTTS-v2 needs at least one reference sample.")
        missing = [str(p) for p in ref_wavs if not Path(p).is_file()]
        if missing:
            raise FileNotFoundError(f"Reference samples not found: {missing}")

        self.load()
        self._tts.tts_to_file(
            text=text,
            speaker_wav=[str(p) for p in ref_wavs],
            language=lang,
            file_path=str(out_path),
        )


def _load_xtts(model_name: str, device: str) -> "TTS":
    """Import coqui-tts and load `model_name` onto `device`."""
    # Imported here so the app and tests start without torch installed.
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "synthesis.device is 'cuda', but PyTorch cannot use a CUDA GPU "
            f"(torch {torch.__version__}, built for CUDA {torch.version.cuda}). "
            "Install the CUDA build of torch (see 'Optional: Nvidia GPU (CUDA) "
            "support' in the README) or set synthesis.device: cpu in config.yaml."
        )

    from TTS.api import TTS

    logger.info("Loading %s on %s (first run downloads ~1.8 GB)", model_name, device)
    return TTS(model_name, progress_bar=False).to(device)


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
