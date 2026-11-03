"""Clean caregiver voice samples into the format voice-cloning engines expect.

Recordings arrive from a browser microphone or a file upload in any format,
channel count, and sample rate, often with silence at each end. Voice cloning
works best on short, clean, consistently leveled clips, so every sample is
converted to a mono, 24 kHz, 16-bit WAV with the silence trimmed and the peak
normalized before it is saved under ``samples/``.
"""

import logging
from collections.abc import Iterable
from pathlib import Path

import soundfile as sf
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.silence import detect_leading_silence

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 24_000  # Hz, matches the XTTS-v2 output rate
TARGET_SAMPLE_WIDTH = 2  # bytes per sample, i.e. 16-bit PCM
PEAK_HEADROOM_DB = 1.0  # loudest sample sits this far below full scale
SILENCE_THRESHOLD_DB = 40.0  # quieter than (peak - this) counts as silence
SILENCE_CHUNK_MS = 10  # resolution of the silence scan
KEEP_SILENCE_MS = 100  # padding kept at each end so word onsets are not cut

MIN_TOTAL_SECONDS = 6.0  # XTTS-v2 needs at least ~6 s of reference speech
MAX_TOTAL_SECONDS = 60.0  # more audio slows cloning without improving it


def preprocess(in_path: str | Path, out_path: str | Path) -> Path:
    """Convert one recording to a trimmed, normalized mono 24 kHz WAV.

    Parameters
    ----------
    in_path : str or Path
        The source recording, in any format ffmpeg can read.
    out_path : str or Path
        Where to write the cleaned WAV. Parent folders are created.

    Returns
    -------
    Path
        `out_path` as a ``Path``.

    Raises
    ------
    FileNotFoundError
        If `in_path` does not exist.
    ValueError
        If the recording contains no sound above silence.
    """
    in_path, out_path = Path(in_path), Path(out_path)
    if not in_path.is_file():
        raise FileNotFoundError(f"Voice sample not found: {in_path}")

    audio = AudioSegment.from_file(in_path)
    if audio.max == 0:
        raise ValueError(f"Voice sample is silent: {in_path}")

    audio = (
        audio.set_channels(1)
        .set_frame_rate(TARGET_SAMPLE_RATE)
        .set_sample_width(TARGET_SAMPLE_WIDTH)
    )
    audio = normalize(_trim_silence(audio), headroom=PEAK_HEADROOM_DB)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(out_path, format="wav")
    return out_path


def total_duration(paths: Iterable[str | Path]) -> float:
    """Return the combined length of WAV samples and warn if it is off target.

    A warning is logged when the total is under ``MIN_TOTAL_SECONDS`` (too
    little speech to clone) or over ``MAX_TOTAL_SECONDS`` (slower builds with
    no quality gain).

    Parameters
    ----------
    paths : Iterable[str or Path]
        Preprocessed sample WAVs.

    Returns
    -------
    float
        Total duration in seconds.
    """
    total = sum(sf.info(path).duration for path in paths)
    if total < MIN_TOTAL_SECONDS:
        logger.warning(
            "Voice samples total %.1f s; record at least %.0f s for cloning.",
            total,
            MIN_TOTAL_SECONDS,
        )
    elif total > MAX_TOTAL_SECONDS:
        logger.warning(
            "Voice samples total %.1f s; more than %.0f s slows cloning.",
            total,
            MAX_TOTAL_SECONDS,
        )
    return total


def _trim_silence(audio: AudioSegment) -> AudioSegment:
    """Cut silence from both ends, keeping ``KEEP_SILENCE_MS`` of padding."""
    # The threshold is relative to the peak, so quiet and loud recordings
    # trim the same way.
    threshold = audio.max_dBFS - SILENCE_THRESHOLD_DB
    start = detect_leading_silence(audio, threshold, SILENCE_CHUNK_MS)
    end = len(audio) - detect_leading_silence(
        audio.reverse(), threshold, SILENCE_CHUNK_MS
    )
    return audio[max(start - KEEP_SILENCE_MS, 0) : end + KEEP_SILENCE_MS]
