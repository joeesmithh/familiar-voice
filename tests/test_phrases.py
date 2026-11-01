import copy
import json
from pathlib import Path

import pytest

from familiar_voice.core import phrases
from familiar_voice.core.phrases import PhraseData


def _all_phrase_ids(data: PhraseData) -> list[str]:
    return [p["id"] for c in data["categories"] for p in c["phrases"]]


def _find_text(data: PhraseData, phrase_id: str) -> str:
    for category in data["categories"]:
        for phrase in category["phrases"]:
            if phrase["id"] == phrase_id:
                return phrase["text"]
    raise KeyError(phrase_id)


@pytest.fixture
def sample() -> PhraseData:
    """Valid phrase data with four small categories."""
    return {
        "categories": [
            {
                "id": category_id,
                "label": category_id.title(),
                "icon": "🙂",
                "phrases": [{"id": f"{category_id}-1", "text": "Hello there."}],
            }
            for category_id in ("worried", "lonely", "when-home", "routine")
        ]
    }


# --- Defaults and seeding ---


def test_default_phrases_are_valid_and_have_expected_categories() -> None:
    data = phrases.default_phrases()

    assert phrases.validate(data) == []
    assert [c["id"] for c in data["categories"]] == [
        "worried",
        "lonely",
        "when-home",
        "routine",
    ]


def test_load_seeds_defaults_when_file_is_missing(data_dir: Path) -> None:
    data = phrases.load_phrases()

    assert data == phrases.default_phrases()
    assert (data_dir / "phrases.json").is_file()


def test_load_raises_on_invalid_json(data_dir: Path) -> None:
    data_dir.mkdir(parents=True)
    (data_dir / "phrases.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        phrases.load_phrases()


def test_load_raises_on_schema_errors(data_dir: Path) -> None:
    data_dir.mkdir(parents=True)
    (data_dir / "phrases.json").write_text('{"categories": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="categories"):
        phrases.load_phrases()


# --- Save / load round trip ---


def test_save_then_load_round_trips(data_dir: Path, sample: PhraseData) -> None:
    sample["categories"][0]["phrases"][0]["text"] = "Ça va — I'm here. 💛"

    phrases.save_phrases(sample)

    assert phrases.load_phrases() == sample


def test_save_refuses_invalid_data_and_keeps_old_file(
    data_dir: Path, sample: PhraseData
) -> None:
    phrases.save_phrases(sample)
    broken = copy.deepcopy(sample)
    broken["categories"][0]["phrases"][0]["text"] = "   "

    with pytest.raises(ValueError, match="empty text"):
        phrases.save_phrases(broken)

    assert phrases.load_phrases() == sample


def test_save_leaves_no_temp_file(data_dir: Path, sample: PhraseData) -> None:
    phrases.save_phrases(sample)

    assert [p.name for p in data_dir.iterdir()] == ["phrases.json"]


# --- Validation ---


def test_validate_accepts_valid_data(sample: PhraseData) -> None:
    assert phrases.validate(sample) == []


@pytest.mark.parametrize("count", [3, 7])
def test_validate_rejects_wrong_category_count(sample: PhraseData, count: int) -> None:
    template = sample["categories"][0]
    sample["categories"] = [
        {**template, "id": f"cat-{n}", "phrases": [{"id": f"p-{n}", "text": "Hi"}]}
        for n in range(count)
    ]

    errors = phrases.validate(sample)

    assert any("4 to 6 categories" in e for e in errors)


def test_validate_rejects_duplicate_phrase_ids_across_categories(
    sample: PhraseData,
) -> None:
    sample["categories"][1]["phrases"][0]["id"] = "worried-1"

    assert any("Duplicate phrase id" in e for e in phrases.validate(sample))


def test_validate_rejects_duplicate_category_ids(sample: PhraseData) -> None:
    sample["categories"][1]["id"] = "worried"

    assert any("Duplicate category id" in e for e in phrases.validate(sample))


@pytest.mark.parametrize("text", ["", "   ", None])
def test_validate_rejects_empty_text(sample: PhraseData, text: str | None) -> None:
    sample["categories"][0]["phrases"][0]["text"] = text

    assert any("empty text" in e for e in phrases.validate(sample))


@pytest.mark.parametrize("bad_id", ["Has Space", "../escape", "UPPER", "", None])
def test_validate_rejects_ids_unsafe_for_file_names(
    sample: PhraseData, bad_id: str | None
) -> None:
    sample["categories"][0]["phrases"][0]["id"] = bad_id

    assert any("invalid id" in e for e in phrases.validate(sample))


def test_validate_requires_label_and_icon(sample: PhraseData) -> None:
    sample["categories"][0]["label"] = ""
    del sample["categories"][0]["icon"]

    errors = phrases.validate(sample)

    assert any("non-empty label" in e for e in errors)
    assert any("non-empty icon" in e for e in errors)


def test_validate_reports_missing_categories_list() -> None:
    assert phrases.validate({}) == ['Phrase data must have a "categories" list.']


def test_validate_reports_every_error_at_once(sample: PhraseData) -> None:
    sample["categories"][0]["phrases"][0]["text"] = ""
    sample["categories"][1]["id"] = "worried"

    assert len(phrases.validate(sample)) == 2


# --- Editing keeps ids stable ---


def test_add_phrase_returns_new_unique_id(sample: PhraseData) -> None:
    before = _all_phrase_ids(sample)

    new_id = phrases.add_phrase(sample, "lonely", "  I love you.  ")

    assert new_id.startswith("lonely-")
    assert new_id not in before
    assert _all_phrase_ids(sample) == [*before[:2], new_id, *before[2:]]
    assert _find_text(sample, new_id) == "I love you."
    assert phrases.validate(sample) == []


def test_add_phrase_rejects_unknown_category(sample: PhraseData) -> None:
    with pytest.raises(KeyError, match="nope"):
        phrases.add_phrase(sample, "nope", "Hi")


def test_add_phrase_rejects_blank_text(sample: PhraseData) -> None:
    with pytest.raises(ValueError, match="empty"):
        phrases.add_phrase(sample, "worried", "   ")


def test_update_phrase_changes_text_but_not_id(sample: PhraseData) -> None:
    before = _all_phrase_ids(sample)

    phrases.update_phrase(sample, "lonely-1", "I miss you too.")

    assert _all_phrase_ids(sample) == before
    assert _find_text(sample, "lonely-1") == "I miss you too."


def test_update_phrase_rejects_unknown_id(sample: PhraseData) -> None:
    with pytest.raises(KeyError):
        phrases.update_phrase(sample, "missing", "Hi")


def test_update_phrase_rejects_blank_text(sample: PhraseData) -> None:
    with pytest.raises(ValueError):
        phrases.update_phrase(sample, "worried-1", "")


def test_delete_phrase_removes_only_that_phrase(sample: PhraseData) -> None:
    phrases.add_phrase(sample, "worried", "Second phrase.")
    before = _all_phrase_ids(sample)

    phrases.delete_phrase(sample, "worried-1")

    assert _all_phrase_ids(sample) == [i for i in before if i != "worried-1"]


def test_delete_phrase_rejects_unknown_id(sample: PhraseData) -> None:
    with pytest.raises(KeyError):
        phrases.delete_phrase(sample, "missing")


def test_ids_survive_edit_save_and_reload(data_dir: Path, sample: PhraseData) -> None:
    new_id = phrases.add_phrase(sample, "routine", "Time for a snack.")
    phrases.save_phrases(sample)

    data = phrases.load_phrases()
    phrases.update_phrase(data, new_id, "Time for a healthy snack.")
    phrases.save_phrases(data)
    reloaded = phrases.load_phrases()

    assert _find_text(reloaded, new_id) == "Time for a healthy snack."
    assert json.loads((data_dir / "phrases.json").read_text(encoding="utf-8")) == (
        reloaded
    )
