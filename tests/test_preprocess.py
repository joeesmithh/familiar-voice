import logging
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from familiar_voice.voice import preprocess as pp
from familiar_voice.voice.preprocess import preprocess, total_duration

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg is not installed"
)

SOURCE_RATE = 44_100
PAD_SECONDS = 1.0
TONE_SECONDS = 2.0


def write_padded_stereo_tone(path: Path, amplitude: float = 0.25) -> None:
    """Write a stereo 44.1 kHz tone with silence before and after it."""
    t = np.arange(round(TONE_SECONDS * SOURCE_RATE)) / SOURCE_RATE
    tone = amplitude * np.sin(2 * np.pi * 220.0 * t)
    silence = np.zeros(round(PAD_SECONDS * SOURCE_RATE))
    mono = np.concatenate([silence, tone, silence])
    sf.write(path, np.column_stack([mono, mono]).astype(np.float32), SOURCE_RATE)


def write_mono(path: Path, seconds: float, rate: int = pp.TARGET_SAMPLE_RATE) -> None:
    sf.write(path, np.zeros(round(seconds * rate), dtype=np.float32), rate)


# --- preprocess ---


@needs_ffmpeg
def test_preprocess_makes_mono_24khz_trimmed_normalized_wav(tmp_path: Path) -> None:
    src = tmp_path / "raw.wav"
    write_padded_stereo_tone(src)

    out = preprocess(src, tmp_path / "samples" / "sample_1.wav")

    audio, rate = sf.read(out)
    assert out.exists()
    assert rate == pp.TARGET_SAMPLE_RATE
    assert audio.ndim == 1
    assert sf.info(out).subtype == "PCM_16"
    original_seconds = TONE_SECONDS + 2 * PAD_SECONDS
    assert len(audio) / rate < original_seconds
    assert len(audio) / rate == pytest.approx(
        TONE_SECONDS + 2 * pp.KEEP_SILENCE_MS / 1000, abs=0.05
    )
    expected_peak = 10 ** (-pp.PEAK_HEADROOM_DB / 20)
    assert np.max(np.abs(audio)) == pytest.approx(expected_peak, abs=0.01)


@needs_ffmpeg
@pytest.mark.parametrize("amplitude", [0.02, 0.9])
def test_preprocess_levels_quiet_and_loud_input_alike(
    tmp_path: Path, amplitude: float
) -> None:
    src = tmp_path / "raw.wav"
    write_padded_stereo_tone(src, amplitude=amplitude)

    audio, _ = sf.read(preprocess(src, tmp_path / "out.wav"))

    expected_peak = 10 ** (-pp.PEAK_HEADROOM_DB / 20)
    assert np.max(np.abs(audio)) == pytest.approx(expected_peak, abs=0.01)


@needs_ffmpeg
def test_preprocess_reads_non_wav_input(tmp_path: Path) -> None:
    src = tmp_path / "raw.flac"
    write_padded_stereo_tone(src)

    out = preprocess(src, tmp_path / "out.wav")

    assert sf.info(out).samplerate == pp.TARGET_SAMPLE_RATE


@needs_ffmpeg
def test_preprocess_rejects_silent_recording(tmp_path: Path) -> None:
    src = tmp_path / "silent.wav"
    write_mono(src, 1.0)

    with pytest.raises(ValueError, match="silent"):
        preprocess(src, tmp_path / "out.wav")
    assert not (tmp_path / "out.wav").exists()


def test_preprocess_missing_input_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing.wav"):
        preprocess(tmp_path / "missing.wav", tmp_path / "out.wav")


# --- total_duration ---


def test_total_duration_sums_samples(tmp_path: Path) -> None:
    paths = [tmp_path / "a.wav", tmp_path / "b.wav"]
    write_mono(paths[0], 4.0)
    write_mono(paths[1], 6.5)

    assert total_duration(paths) == pytest.approx(10.5)


@pytest.mark.parametrize(
    ("seconds", "message"), [(3.0, "at least"), (61.0, "slows cloning")]
)
def test_total_duration_warns_outside_range(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, seconds: float, message: str
) -> None:
    path = tmp_path / "a.wav"
    write_mono(path, seconds)

    with caplog.at_level(logging.WARNING, logger=pp.__name__):
        total_duration([path])

    assert message in caplog.text


@pytest.mark.parametrize("seconds", [6.0, 30.0, 60.0])
def test_total_duration_quiet_inside_range(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, seconds: float
) -> None:
    path = tmp_path / "a.wav"
    write_mono(path, seconds)

    with caplog.at_level(logging.WARNING, logger=pp.__name__):
        total_duration([path])

    assert not caplog.records


def test_total_duration_of_no_samples_is_zero_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=pp.__name__):
        assert total_duration([]) == 0.0

    assert "at least" in caplog.text
