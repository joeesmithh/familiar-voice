import json
import random
from pathlib import Path

import pytest

from familiar_voice.core import library
from familiar_voice.core.library import Picker


def write_library(
    data_dir: Path, entries: dict[str, str], *, on_disk: bool = True
) -> None:
    """Write a manifest mapping phrase id → category, plus one WAV per phrase."""
    root = data_dir / "library"
    root.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for phrase_id, category in entries.items():
        rel = f"{category}/{phrase_id}.wav"
        manifest[phrase_id] = {
            "category": category,
            "text": phrase_id,
            "text_hash": "x",
            "path": rel,
        }
        if on_disk:
            (root / category).mkdir(exist_ok=True)
            (root / rel).write_bytes(b"RIFF")
    (root / "manifest.json").write_text(json.dumps({"phrases": manifest}), "utf-8")


# --- Choosing ---


def test_pick_returns_phrase_id_and_existing_path(data_dir: Path) -> None:
    write_library(data_dir, {"worried-1": "worried"})

    result = Picker().pick("worried")

    assert result is not None
    phrase_id, path = result
    assert phrase_id == "worried-1"
    assert path.is_file()
    assert path.name == "worried-1.wav"


def test_pick_only_chooses_from_requested_category(data_dir: Path) -> None:
    write_library(data_dir, {"worried-1": "worried", "lonely-1": "lonely"})
    picker = Picker(random.Random(0))

    picks = {picker.pick("lonely")[0] for _ in range(10)}  # type: ignore[index]

    assert picks == {"lonely-1"}


def test_no_immediate_repeat(data_dir: Path) -> None:
    write_library(data_dir, {"w-1": "worried", "w-2": "worried", "w-3": "worried"})
    picker = Picker(random.Random(1))

    picks = [picker.pick("worried")[0] for _ in range(50)]  # type: ignore[index]

    assert all(a != b for a, b in zip(picks, picks[1:], strict=False))
    assert set(picks) == {"w-1", "w-2", "w-3"}


def test_two_phrases_alternate(data_dir: Path) -> None:
    write_library(data_dir, {"w-1": "worried", "w-2": "worried"})
    picker = Picker(random.Random(2))

    picks = [picker.pick("worried")[0] for _ in range(6)]  # type: ignore[index]

    assert picks[0::2] == [picks[0]] * 3
    assert picks[1::2] == [picks[1]] * 3
    assert picks[0] != picks[1]


def test_single_phrase_repeats(data_dir: Path) -> None:
    write_library(data_dir, {"w-1": "worried"})
    picker = Picker()

    assert picker.pick("worried")[0] == "w-1"  # type: ignore[index]
    assert picker.pick("worried")[0] == "w-1"  # type: ignore[index]


def test_repeat_memory_is_per_category(data_dir: Path) -> None:
    write_library(data_dir, {"w-1": "worried", "l-1": "lonely", "l-2": "lonely"})
    picker = Picker(random.Random(3))

    first = picker.pick("lonely")
    picker.pick("worried")
    second = picker.pick("lonely")

    assert first is not None and second is not None
    assert first[0] != second[0]


def test_same_seed_gives_same_picks(data_dir: Path) -> None:
    write_library(data_dir, {f"w-{i}": "worried" for i in range(5)})

    def run(seed: int) -> list[str]:
        picker = Picker(random.Random(seed))
        return [picker.pick("worried")[0] for _ in range(10)]  # type: ignore[index]

    assert run(42) == run(42)


# --- Empty and missing audio ---


def test_empty_category_returns_none(data_dir: Path) -> None:
    write_library(data_dir, {"worried-1": "worried"})

    assert Picker().pick("lonely") is None


def test_no_manifest_returns_none(data_dir: Path) -> None:
    assert Picker().pick("worried") is None


def test_only_entries_on_disk_are_chosen(data_dir: Path) -> None:
    write_library(data_dir, {"w-1": "worried", "w-2": "worried"})
    (data_dir / "library" / "worried" / "w-2.wav").unlink()
    picker = Picker(random.Random(4))

    picks = {picker.pick("worried")[0] for _ in range(10)}  # type: ignore[index]

    assert picks == {"w-1"}


def test_wavs_missing_from_manifest_are_ignored(data_dir: Path) -> None:
    write_library(data_dir, {"w-1": "worried"})
    (data_dir / "library" / "worried" / "stray.wav").write_bytes(b"RIFF")
    picker = Picker(random.Random(5))

    picks = {picker.pick("worried")[0] for _ in range(10)}  # type: ignore[index]

    assert picks == {"w-1"}


def test_all_wavs_missing_returns_none(data_dir: Path) -> None:
    write_library(data_dir, {"w-1": "worried"}, on_disk=False)

    assert Picker().pick("worried") is None


def test_entries_outside_library_are_ignored(data_dir: Path) -> None:
    write_library(data_dir, {})
    outside = data_dir / "secret.wav"
    outside.write_bytes(b"RIFF")
    manifest = {"phrases": {"bad": {"category": "worried", "path": "../secret.wav"}}}
    (data_dir / "library" / "manifest.json").write_text(json.dumps(manifest), "utf-8")

    assert Picker().pick("worried") is None


# --- Module-level helper ---


def test_module_pick_uses_shared_picker(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_library(data_dir, {"w-1": "worried", "w-2": "worried"})
    monkeypatch.setattr(library, "_default_picker", Picker(random.Random(6)))

    first = library.pick("worried")
    second = library.pick("worried")

    assert first is not None and second is not None
    assert first[0] != second[0]
