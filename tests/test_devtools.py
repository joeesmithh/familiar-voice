import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from familiar_voice.app import devtools
from familiar_voice.core.config import DATA_DIR_ENV_VAR, samples_dir
from familiar_voice.core.log import log_event
from familiar_voice.core.phrases import default_phrases
from familiar_voice.voice.build_library import build_library

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg is not installed"
)


def _write_tone(path: Path, seconds: float = 1.0, rate: int = 44_100) -> Path:
    t = np.arange(int(seconds * rate)) / rate
    tone = 0.5 * np.sin(2 * np.pi * 220 * t)
    sf.write(path, np.stack([tone, tone], axis=1).astype(np.float32), rate)
    return path


def test_build_console_constructs(data_dir):
    assert devtools.build_console() is not None


class _StubConsole:
    def launch(self) -> None:
        pass


def test_main_defaults_to_dev_tools_data_dir(monkeypatch):
    monkeypatch.setenv(DATA_DIR_ENV_VAR, "x")  # record the original so it is restored
    monkeypatch.delenv(DATA_DIR_ENV_VAR)
    monkeypatch.setattr(devtools, "build_console", _StubConsole)
    devtools.main()
    assert os.environ[DATA_DIR_ENV_VAR] == "data_dev_tools"


def test_main_keeps_existing_data_dir(data_dir, monkeypatch):
    monkeypatch.setattr(devtools, "build_console", _StubConsole)
    devtools.main()
    assert os.environ[DATA_DIR_ENV_VAR] == str(data_dir)


def test_next_sample_path_skips_existing(data_dir):
    assert devtools.next_sample_path().name == "sample_1.wav"
    (samples_dir() / "sample_1.wav").touch()
    (samples_dir() / "sample_3.wav").touch()
    assert devtools.next_sample_path().name == "sample_4.wav"


def test_save_sample_requires_consent(data_dir, tmp_path):
    source = _write_tone(tmp_path / "in.wav")
    message = devtools.save_sample(source, consented=False)
    assert "consent" in message
    assert list(samples_dir().iterdir()) == []


def test_save_sample_without_audio(data_dir):
    assert "Record" in devtools.save_sample(None, consented=True)


@needs_ffmpeg
def test_save_sample_preprocesses_with_consent(data_dir, tmp_path):
    source = _write_tone(tmp_path / "in.wav")
    message = devtools.save_sample(source, consented=True)
    out = samples_dir() / "sample_1.wav"
    assert "Saved sample_1.wav" in message
    info = sf.info(out)
    assert info.samplerate == 24_000
    assert info.channels == 1
    assert "under" in message  # 1 s total is below the cloning minimum


def test_validate_json_reports_errors(data_dir):
    assert devtools.validate_json("{not json")[0].startswith("Invalid JSON")
    assert devtools.validate_json("[]") == ["Phrase data must be a JSON object."]
    assert devtools.validate_json('{"categories": []}')
    assert devtools.validate_json(json.dumps(default_phrases())) == []


def test_manifest_rows_after_fake_build(data_dir):
    sf.write(samples_dir() / "sample_1.wav", np.zeros(2400, np.float32), 24_000)
    build_library(engine="fake")
    rows = devtools.manifest_rows()
    n_phrases = sum(len(c["phrases"]) for c in default_phrases()["categories"])
    assert len(rows) == n_phrases
    assert all(row[3] is True for row in rows)


def test_event_rows_newest_first_with_limit(data_dir):
    log_event("button", category="worried")
    log_event("checkin", category="routine", note="lunch")
    rows = devtools.event_rows(limit=1)
    assert len(rows) == 1
    assert rows[0][1] == "checkin"
    assert json.loads(rows[0][5]) == {"note": "lunch"}
    assert [r[1] for r in devtools.event_rows(None)] == ["checkin", "button"]


def test_progress_adapter_passes_fraction():
    calls = []
    report = devtools.progress_adapter(lambda frac, desc: calls.append((frac, desc)))
    report(1, 4, "hello")
    report(0, 0, "none")
    assert calls == [(0.25, "hello"), (1.0, "none")]


def test_synth_out_path_is_readable_and_unique(data_dir):
    first = devtools.synth_out_path("It's okay. You are safe!", "fake")
    assert first.parent == devtools.synth_dir()
    assert first.name.endswith("_fake_it-s-okay-you-are-safe.wav")
    first.touch()
    second = devtools.synth_out_path("It's okay. You are safe!", "fake")
    assert second != first and second.stem.endswith("_2")


def test_synthesize_callback_lists_and_deletes_outputs(data_dir):
    audio, message, _ = devtools._on_synthesize("Hello there", "fake", "en")
    assert audio is not None and "fake" in message
    legacy = data_dir / "synth_old.wav"
    legacy.touch()
    found = devtools.find_synthesized()
    assert Path(audio) in found and legacy in found
    assert not any("library" in p.parts for p in found)
    name = devtools._synth_choices()[0][1]
    assert devtools._on_play_synthesized(name) is not None
    assert devtools.delete_synthesized() == "Deleted 2 synthesized file(s)."
    assert devtools.find_synthesized() == []


def test_default_engine_is_xtts_unless_env_names_another(monkeypatch):
    monkeypatch.delenv("FV_ENGINE", raising=False)
    assert devtools.default_engine() == "xtts"
    monkeypatch.setenv("FV_ENGINE", "nonsense")
    assert devtools.default_engine() == "xtts"
    monkeypatch.setenv("FV_ENGINE", "fake")
    assert devtools.default_engine() == "fake"
