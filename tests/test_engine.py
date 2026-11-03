from collections.abc import Sequence
from pathlib import Path

import pytest
import soundfile as sf

from familiar_voice.voice import engine
from familiar_voice.voice.engine import FakeEngine, XTTSEngine, synthesize


@pytest.fixture
def fake_env(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Select the fake engine through ``FV_ENGINE`` for one test."""
    monkeypatch.setenv(engine.ENGINE_ENV_VAR, "fake")
    return data_dir


# --- Fake engine output ---


def test_fake_engine_writes_readable_wav_at_out_path(fake_env: Path) -> None:
    out_path = fake_env / "library" / "worried" / "worried-1.wav"

    result = synthesize("I'm right here with you.", [], out_path=out_path)

    assert result == out_path
    audio, sample_rate = sf.read(result)
    assert sample_rate == FakeEngine.SAMPLE_RATE
    assert audio.ndim == 1
    assert len(audio) > 0


def test_fake_engine_length_scales_with_text(fake_env: Path) -> None:
    short = synthesize("Hi there, friend.", [], out_path=fake_env / "short.wav")
    long = synthesize("Hi there. " * 10, [], out_path=fake_env / "long.wav")

    assert sf.info(long).frames > sf.info(short).frames


def test_fake_engine_duration_is_clamped() -> None:
    fake = FakeEngine()

    assert fake.duration("") == FakeEngine.MIN_SECONDS
    assert fake.duration("x" * 10_000) == FakeEngine.MAX_SECONDS


def test_synthesize_without_out_path_writes_unique_file_in_data_dir(
    fake_env: Path,
) -> None:
    first = synthesize("Hello.", [])
    second = synthesize("Hello.", [])

    assert first != second
    assert first.parent == fake_env
    assert sf.info(first).frames > 0


# --- Engine selection ---


def test_engine_argument_overrides_env_var(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(engine.ENGINE_ENV_VAR, "xtts")

    path = synthesize("Hello.", [], out_path=data_dir / "a.wav", engine="fake")

    assert path.exists()


def test_synthesize_accepts_engine_instance(data_dir: Path) -> None:
    calls: list[tuple[str, list[Path], str]] = []

    class RecordingEngine:
        def synthesize(
            self, text: str, ref_wavs: Sequence[Path], lang: str, out_path: Path
        ) -> None:
            calls.append((text, list(ref_wavs), lang))
            out_path.write_bytes(b"")

    sample = data_dir / "sample_1.wav"
    synthesize("Hola.", [str(sample)], lang="es", engine=RecordingEngine())

    assert calls == [("Hola.", [sample], "es")]


def test_default_engine_is_xtts(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(engine.ENGINE_ENV_VAR, raising=False)
    called: list[str] = []
    monkeypatch.setattr(
        XTTSEngine, "synthesize", lambda self, text, *args: called.append(text)
    )

    synthesize("Hello.", [], out_path=data_dir / "a.wav")

    assert called == ["Hello."]


def test_get_engine_returns_cached_instance() -> None:
    assert engine.get_engine("fake") is engine.get_engine("fake")


@pytest.mark.parametrize("name", ["tortoise", "", "FAKE"])
def test_unknown_engine_raises(data_dir: Path, name: str) -> None:
    with pytest.raises(ValueError, match="Unknown engine"):
        synthesize("Hello.", [], out_path=data_dir / "a.wav", engine=name)


def test_unknown_engine_from_env_var_raises(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(engine.ENGINE_ENV_VAR, "nope")

    with pytest.raises(ValueError, match="Unknown engine"):
        synthesize("Hello.", [], out_path=data_dir / "a.wav")


# --- Input validation ---


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_synthesize_rejects_blank_text(fake_env: Path, text: str) -> None:
    with pytest.raises(ValueError, match="blank"):
        synthesize(text, [], out_path=fake_env / "a.wav")
    assert not (fake_env / "a.wav").exists()
