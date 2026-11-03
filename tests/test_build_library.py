import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from familiar_voice.core import phrases
from familiar_voice.voice import build_library as builder
from familiar_voice.voice.build_library import (
    NoSamplesError,
    build_library,
    load_manifest,
    text_hash,
)
from familiar_voice.voice.engine import ENGINE_ENV_VAR


@pytest.fixture
def samples(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Select the fake engine and write one short voice sample."""
    monkeypatch.setenv(ENGINE_ENV_VAR, "fake")
    sample = data_dir / "samples" / "sample_1.wav"
    sample.parent.mkdir(parents=True)
    sf.write(sample, np.zeros(2400, dtype=np.float32), 24_000)
    return [sample]


def all_phrases() -> list[tuple[str, str]]:
    """Return (category id, phrase id) for every phrase in the phrase file."""
    return [
        (category["id"], phrase["id"])
        for category in phrases.load_phrases()["categories"]
        for phrase in category["phrases"]
    ]


def wav_path(data_dir: Path, category_id: str, phrase_id: str) -> Path:
    return data_dir / "library" / category_id / f"{phrase_id}.wav"


# --- First build ---


def test_builds_a_wav_for_every_phrase(data_dir: Path, samples: list[Path]) -> None:
    summary = build_library()

    expected = all_phrases()
    assert sorted(summary.built) == sorted(pid for _, pid in expected)
    assert summary.skipped == []
    assert summary.removed == []
    for category_id, phrase_id in expected:
        assert sf.info(wav_path(data_dir, category_id, phrase_id)).frames > 0


def test_manifest_records_hash_and_relative_path(
    data_dir: Path, samples: list[Path]
) -> None:
    build_library()

    manifest = load_manifest()
    text = phrases.load_phrases()["categories"][0]["phrases"][0]["text"]
    assert manifest["worried-1"] == {
        "category": "worried",
        "text": text,
        "text_hash": text_hash(text),
        "path": "worried/worried-1.wav",
    }
    on_disk = json.loads((data_dir / "library" / "manifest.json").read_text("utf-8"))
    assert set(on_disk["phrases"]) == {pid for _, pid in all_phrases()}


def test_reports_progress_for_every_phrase(samples: list[Path]) -> None:
    calls: list[tuple[int, int, str]] = []

    build_library(progress=lambda done, total, text: calls.append((done, total, text)))

    total = len(all_phrases())
    assert [done for done, _, _ in calls] == list(range(1, total + 1))
    assert {t for _, t, _ in calls} == {total}
    assert all(text for _, _, text in calls)


def test_passes_samples_and_language_to_engine(samples: list[Path]) -> None:
    calls: list[tuple[list[Path], str]] = []

    class RecordingEngine:
        def synthesize(
            self, text: str, ref_wavs: Sequence[Path], lang: str, out_path: Path
        ) -> None:
            calls.append((list(ref_wavs), lang))
            sf.write(out_path, np.zeros(10, dtype=np.float32), 24_000)

    build_library(engine=RecordingEngine(), lang="es")

    assert calls
    assert all(call == (samples, "es") for call in calls)


# --- Incremental rebuilds ---


def test_second_run_skips_everything(samples: list[Path]) -> None:
    build_library()

    summary = build_library()

    assert summary.built == []
    assert len(summary.skipped) == len(all_phrases())


def test_editing_one_phrase_rebuilds_only_that_one(
    data_dir: Path, samples: list[Path]
) -> None:
    build_library()
    data = phrases.load_phrases()
    phrases.update_phrase(data, "lonely-2", "I'm thinking of you right now.")
    phrases.save_phrases(data)

    summary = build_library()

    assert summary.built == ["lonely-2"]
    assert load_manifest()["lonely-2"]["text"] == "I'm thinking of you right now."


def test_adding_a_phrase_builds_only_the_new_one(
    data_dir: Path, samples: list[Path]
) -> None:
    build_library()
    data = phrases.load_phrases()
    new_id = phrases.add_phrase(data, "routine", "Time for a glass of water.")
    phrases.save_phrases(data)

    summary = build_library()

    assert summary.built == [new_id]
    assert wav_path(data_dir, "routine", new_id).is_file()


def test_missing_wav_is_rebuilt(data_dir: Path, samples: list[Path]) -> None:
    build_library()
    wav_path(data_dir, "worried", "worried-1").unlink()

    summary = build_library()

    assert summary.built == ["worried-1"]
    assert wav_path(data_dir, "worried", "worried-1").is_file()


def test_force_rebuilds_everything(samples: list[Path]) -> None:
    build_library()

    summary = build_library(force=True)

    assert len(summary.built) == len(all_phrases())
    assert summary.skipped == []


def test_unreadable_manifest_rebuilds_everything(
    data_dir: Path, samples: list[Path]
) -> None:
    build_library()
    (data_dir / "library" / "manifest.json").write_text("{not json", "utf-8")

    summary = build_library()

    assert len(summary.built) == len(all_phrases())


# --- Removal ---


def test_deleting_a_phrase_removes_its_wav(data_dir: Path, samples: list[Path]) -> None:
    build_library()
    data = phrases.load_phrases()
    phrases.delete_phrase(data, "worried-2")
    phrases.save_phrases(data)

    summary = build_library()

    assert summary.removed == ["worried-2"]
    assert summary.built == []
    assert not wav_path(data_dir, "worried", "worried-2").exists()
    assert "worried-2" not in load_manifest()


def test_moving_a_phrase_to_another_category_moves_its_wav(
    data_dir: Path, samples: list[Path]
) -> None:
    build_library()
    data = phrases.load_phrases()
    worried, lonely = data["categories"][0], data["categories"][1]
    lonely["phrases"].append(worried["phrases"].pop(0))  # worried-1
    phrases.save_phrases(data)

    summary = build_library()

    assert summary.built == ["worried-1"]
    assert not wav_path(data_dir, "worried", "worried-1").exists()
    assert wav_path(data_dir, "lonely", "worried-1").is_file()


# --- Errors ---


def test_no_samples_raises_clear_error(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENGINE_ENV_VAR, "fake")

    with pytest.raises(NoSamplesError, match="No voice samples"):
        build_library()
    assert not (data_dir / "library" / "manifest.json").exists()


def test_failed_synthesis_leaves_no_partial_wav(
    data_dir: Path, samples: list[Path]
) -> None:
    class FailingEngine:
        def synthesize(
            self, text: str, ref_wavs: Sequence[Path], lang: str, out_path: Path
        ) -> None:
            out_path.write_bytes(b"half a wav")
            raise RuntimeError("model crashed")

    with pytest.raises(RuntimeError, match="model crashed"):
        build_library(engine=FailingEngine())

    assert list((data_dir / "library").rglob("*.wav")) == []
    assert load_manifest() == {}


# --- CLI ---


def test_cli_builds_and_prints_summary(
    samples: list[Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert builder.main([]) == 0
    assert builder.main(["--force"]) == 0

    out = capsys.readouterr().out
    total = len(all_phrases())
    assert f"[{total}/{total}]" in out
    assert f"Built {total}, skipped 0, removed 0" in out


def test_cli_without_samples_exits_with_error(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(ENGINE_ENV_VAR, "fake")

    assert builder.main([]) == 1
    assert "No voice samples" in capsys.readouterr().err
