"""Load, save, validate, and edit the caregiver's reassurance phrases.

Phrases live in ``phrases.json`` under the data root, grouped into the
categories shown as big buttons on the User tab::

    {
      "categories": [
        {
          "id": "worried",
          "label": "I'm worried",
          "icon": "😟",
          "phrases": [{"id": "worried-1", "text": "It's okay. You are safe."}]
        }
      ]
    }

Category and phrase ids are used as folder and file names in the voice
library (``library/<category id>/<phrase id>.wav``). A phrase keeps its id
when its text is edited, so the library builder can tell which WAVs to
rebuild and which to delete.
"""

import json
import re
import uuid
from collections.abc import Mapping
from importlib import resources
from typing import TypedDict

from familiar_voice.core.config import phrases_path

MIN_CATEGORIES = 4
MAX_CATEGORIES = 6
DEFAULT_PHRASES_FILE = "default_phrases.json"

# Ids become folder and file names, so allow only lowercase letters, digits,
# and hyphens.
ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class Phrase(TypedDict):
    """One reassurance phrase.

    Attributes
    ----------
    id : str
        Stable id, used as the phrase's WAV file name.
    text : str
        What the voice says.
    """

    id: str
    text: str


class Category(TypedDict):
    """A group of phrases shown as one button on the User tab.

    Attributes
    ----------
    id : str
        Stable id, used as the category's library folder name.
    label : str
        Short button label, e.g. "I'm worried".
    icon : str
        Emoji shown on the button.
    phrases : list[Phrase]
        Phrases played at random when the button is pressed.
    """

    id: str
    label: str
    icon: str
    phrases: list[Phrase]


class PhraseData(TypedDict):
    """The whole contents of ``phrases.json``.

    Attributes
    ----------
    categories : list[Category]
        Button categories in display order.
    """

    categories: list[Category]


def load_phrases() -> PhraseData:
    """Load the phrase file, seeding it from the defaults if it is missing.

    Returns
    -------
    PhraseData
        The validated phrase data.

    Raises
    ------
    ValueError
        If the file is not valid JSON or fails `validate`.
    """
    path = phrases_path()
    if not path.exists():
        save_phrases(default_phrases())

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in phrase file: {path}") from err

    _raise_if_invalid(data)
    return data


def save_phrases(data: PhraseData) -> None:
    """Validate the phrase data and write it to the phrase file.

    The file is written to a temporary file first and then swapped in, so a
    crash mid-write never leaves a half-written phrase file behind.

    Parameters
    ----------
    data : PhraseData
        Phrase data to save.

    Raises
    ------
    ValueError
        If `data` fails `validate`. Nothing is written in that case.
    """
    _raise_if_invalid(data)
    path = phrases_path()
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temp_path.replace(path)


def default_phrases() -> PhraseData:
    """Return a fresh copy of the bundled default phrases.

    Returns
    -------
    PhraseData
        Default categories: worried, lonely, when-home, and routine.
    """
    default_file = resources.files("familiar_voice.core") / DEFAULT_PHRASES_FILE
    return json.loads(default_file.read_text(encoding="utf-8"))


def validate(data: Mapping) -> list[str]:
    """Check phrase data against the schema and return every problem found.

    Parameters
    ----------
    data : Mapping
        Phrase data, typically freshly loaded or edited by the caregiver.

    Returns
    -------
    list[str]
        Human-readable error messages. An empty list means the data is valid.
    """
    categories = data.get("categories")
    if not isinstance(categories, list):
        return ['Phrase data must have a "categories" list.']

    errors: list[str] = []
    if not MIN_CATEGORIES <= len(categories) <= MAX_CATEGORIES:
        errors.append(
            f"There must be {MIN_CATEGORIES} to {MAX_CATEGORIES} categories, "
            f"found {len(categories)}."
        )

    category_ids: set[str] = set()
    phrase_ids: set[str] = set()
    for position, category in enumerate(categories, start=1):
        if not isinstance(category, Mapping):
            errors.append(f"Category {position} must be an object.")
            continue
        errors.extend(_validate_category(category, position, category_ids))
        for phrase in category.get("phrases", []):
            errors.extend(_validate_phrase(phrase, category.get("id"), phrase_ids))
    return errors


def add_phrase(data: PhraseData, category_id: str, text: str) -> str:
    """Add a new phrase to a category, editing `data` in place.

    Parameters
    ----------
    data : PhraseData
        Phrase data to modify.
    category_id : str
        Id of the category to add the phrase to.
    text : str
        Phrase text. Surrounding whitespace is removed.

    Returns
    -------
    str
        The new phrase's id.

    Raises
    ------
    KeyError
        If no category has id `category_id`.
    ValueError
        If `text` is blank.
    """
    category = _find_category(data, category_id)
    phrase_id = _new_phrase_id(data, category_id)
    category["phrases"].append({"id": phrase_id, "text": _clean_text(text)})
    return phrase_id


def update_phrase(data: PhraseData, phrase_id: str, text: str) -> None:
    """Change a phrase's text, editing `data` in place. The id stays the same.

    Parameters
    ----------
    data : PhraseData
        Phrase data to modify.
    phrase_id : str
        Id of the phrase to change.
    text : str
        New phrase text. Surrounding whitespace is removed.

    Raises
    ------
    KeyError
        If no phrase has id `phrase_id`.
    ValueError
        If `text` is blank.
    """
    _find_phrase(data, phrase_id)["text"] = _clean_text(text)


def delete_phrase(data: PhraseData, phrase_id: str) -> None:
    """Remove a phrase, editing `data` in place.

    Parameters
    ----------
    data : PhraseData
        Phrase data to modify.
    phrase_id : str
        Id of the phrase to remove.

    Raises
    ------
    KeyError
        If no phrase has id `phrase_id`.
    """
    for category in data["categories"]:
        for index, phrase in enumerate(category["phrases"]):
            if phrase["id"] == phrase_id:
                del category["phrases"][index]
                return
    raise KeyError(f"No phrase with id {phrase_id!r}")


def _validate_category(
    category: Mapping, position: int, seen_ids: set[str]
) -> list[str]:
    """Check one category's own fields (not its phrases) and record its id."""
    errors: list[str] = []
    category_id = category.get("id")
    name = f"Category {position}"
    if not _is_valid_id(category_id):
        errors.append(
            f"{name} has invalid id {category_id!r}; use lowercase letters, "
            "digits, and hyphens."
        )
    elif category_id in seen_ids:
        errors.append(f"Duplicate category id {category_id!r}.")
    else:
        seen_ids.add(category_id)

    for field in ("label", "icon"):
        if not _is_non_empty_text(category.get(field)):
            errors.append(f"{name} ({category_id}) needs a non-empty {field}.")
    if not isinstance(category.get("phrases"), list):
        errors.append(f"{name} ({category_id}) must have a phrases list.")
    return errors


def _validate_phrase(
    phrase: object, category_id: object, seen_ids: set[str]
) -> list[str]:
    """Check one phrase and record its id."""
    if not isinstance(phrase, Mapping):
        return [f"A phrase in category {category_id!r} must be an object."]

    errors: list[str] = []
    phrase_id = phrase.get("id")
    if not _is_valid_id(phrase_id):
        errors.append(
            f"Phrase in category {category_id!r} has invalid id {phrase_id!r}."
        )
    elif phrase_id in seen_ids:
        errors.append(f"Duplicate phrase id {phrase_id!r}.")
    else:
        seen_ids.add(phrase_id)

    if not _is_non_empty_text(phrase.get("text")):
        errors.append(f"Phrase {phrase_id!r} has empty text.")
    return errors


def _raise_if_invalid(data: Mapping) -> None:
    """Raise ValueError listing every validation error, if there are any."""
    errors = validate(data)
    if errors:
        raise ValueError("Invalid phrase data:\n- " + "\n- ".join(errors))


def _is_valid_id(value: object) -> bool:
    """Return True if `value` is a string usable as a file or folder name."""
    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None


def _is_non_empty_text(value: object) -> bool:
    """Return True if `value` is a string with at least one visible character."""
    return isinstance(value, str) and bool(value.strip())


def _clean_text(text: str) -> str:
    """Strip whitespace from phrase text and reject blank text."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Phrase text must not be empty.")
    return cleaned


def _new_phrase_id(data: PhraseData, category_id: str) -> str:
    """Return a new phrase id like ``worried-3f9a1c2b`` not used in `data`."""
    existing = {
        phrase["id"]
        for category in data["categories"]
        for phrase in category["phrases"]
    }
    while True:
        # Random rather than numbered, so deleting and re-adding a phrase never
        # reuses an old id (and its stale WAV).
        phrase_id = f"{category_id}-{uuid.uuid4().hex[:8]}"
        if phrase_id not in existing:
            return phrase_id


def _find_category(data: PhraseData, category_id: str) -> Category:
    """Return the category with `category_id`, or raise KeyError."""
    for category in data["categories"]:
        if category["id"] == category_id:
            return category
    raise KeyError(f"No category with id {category_id!r}")


def _find_phrase(data: PhraseData, phrase_id: str) -> Phrase:
    """Return the phrase with `phrase_id`, or raise KeyError."""
    for category in data["categories"]:
        for phrase in category["phrases"]:
            if phrase["id"] == phrase_id:
                return phrase
    raise KeyError(f"No phrase with id {phrase_id!r}")
