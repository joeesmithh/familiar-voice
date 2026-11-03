from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from familiar_voice.voice import engine
from familiar_voice.voice.engine import TOS_ENV_VAR, XTTSEngine, synthesize

REF_SECONDS = 8.0  # above the ~6 s XTTS-v2 needs
REF_SAMPLE_RATE = 24_000


@pytest.fixture
def ref_wav(data_dir: Path) -> Path:
    """Write a stand-in reference sample (a warbling tone, not real speech)."""
    t = np.arange(round(REF_SECONDS * REF_SAMPLE_RATE)) / REF_SAMPLE_RATE
    pitch = 160 + 40 * np.sin(2 * np.pi * 3 * t)  # wobble like a voice
    audio = 0.3 * np.sin(2 * np.pi * np.cumsum(pitch) / REF_SAMPLE_RATE)
    path = data_dir / "samples" / "sample_1.wav"
    path.parent.mkdir(parents=True)
    sf.write(path, audio.astype(np.float32), REF_SAMPLE_RATE)
    return path


class StubTTS:
    """Records `tts_to_file` calls instead of running the model."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def tts_to_file(self, **kwargs: object) -> None:
        self.calls.append(kwargs)
        Path(str(kwargs["file_path"])).write_bytes(b"RIFF")


@pytest.fixture
def stub_tts(monkeypatch: pytest.MonkeyPatch) -> list[StubTTS]:
    """Replace model loading with a stub; the list holds each loaded stub."""
    loaded: list[StubTTS] = []

    def fake_load(model_name: str, device: str) -> StubTTS:
        loaded.append(StubTTS())
        return loaded[-1]

    monkeypatch.setattr(engine, "_load_xtts", fake_load)
    monkeypatch.setenv(TOS_ENV_VAR, "1")
    return loaded


# --- Fast tests (no model weights) ---


def test_xtts_passes_text_samples_and_language_to_model(
    stub_tts: list[StubTTS], ref_wav: Path, data_dir: Path
) -> None:
    out_path = data_dir / "out.wav"

    synthesize("Hola.", [ref_wav], lang="es", out_path=out_path, engine=XTTSEngine())

    assert stub_tts[0].calls == [
        {
            "text": "Hola.",
            "speaker_wav": [str(ref_wav)],
            "language": "es",
            "file_path": str(out_path),
        }
    ]


def test_xtts_loads_model_once(
    stub_tts: list[StubTTS], ref_wav: Path, data_dir: Path
) -> None:
    xtts = XTTSEngine()

    for i in range(3):
        synthesize("Hi.", [ref_wav], out_path=data_dir / f"{i}.wav", engine=xtts)

    assert len(stub_tts) == 1
    assert len(stub_tts[0].calls) == 3


def test_xtts_requires_license_agreement(
    stub_tts: list[StubTTS], ref_wav: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TOS_ENV_VAR)

    with pytest.raises(RuntimeError, match=TOS_ENV_VAR):
        XTTSEngine().load()
    assert stub_tts == []


def test_xtts_rejects_missing_samples(stub_tts: list[StubTTS], data_dir: Path) -> None:
    xtts = XTTSEngine()

    with pytest.raises(ValueError, match="reference sample"):
        xtts.synthesize("Hi.", [], "en", data_dir / "a.wav")
    with pytest.raises(FileNotFoundError, match="nope.wav"):
        xtts.synthesize("Hi.", [data_dir / "nope.wav"], "en", data_dir / "a.wav")
    assert stub_tts == []


# --- Slow test (downloads and runs the real model) ---


@pytest.mark.slow
def test_xtts_synthesizes_non_empty_wav(
    ref_wav: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("TTS")
    monkeypatch.setenv(TOS_ENV_VAR, "1")
    out_path = data_dir / "hello.wav"

    synthesize("Hello, I'm right here.", [ref_wav], out_path=out_path, engine="xtts")

    info = sf.info(out_path)
    assert info.frames > 0
    assert info.samplerate == REF_SAMPLE_RATE
