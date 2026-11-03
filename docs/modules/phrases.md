# `familiar_voice.core.phrases`

Loads, validates, edits, and saves the caregiver's reassurance phrases in
`phrases.json`.

## Purpose

The caregiver writes phrases grouped into categories, and each category becomes
one big button on the User tab. This module owns the `phrases.json` schema and
keeps the file valid, so the UI and library builder can trust its contents. It
does not generate audio or play phrases; it only manages the text and ids.

## Key Components

- `PhraseData`, `Category`, `Phrase` — `TypedDict` types describing the file's
  structure.
- `load_phrases()` — reads and validates the file, seeding it from defaults if
  missing.
- `save_phrases()` — validates and writes the file atomically.
- `validate()` — returns a list of every schema error; an empty list means
  valid.
- `default_phrases()` — returns the bundled starter set (worried, lonely,
  when-home, routine).
- `add_phrase()`, `update_phrase()`, `delete_phrase()` — edit a `PhraseData`
  object in place.

## Usage

```python
from familiar_voice.core.phrases import (
    add_phrase,
    load_phrases,
    save_phrases,
    update_phrase,
)

data = load_phrases()
new_id = add_phrase(data, "worried", "I'm proud of you for telling me.")
update_phrase(data, new_id, "I'm so proud of you for telling me.")
save_phrases(data)
print(new_id)  # e.g. worried-3f9a1c2b
```

## Dependencies

- **Uses:** `familiar_voice.core.config` (for `phrases_path()`), and the bundled
  `default_phrases.json`.
- **Used by:** `familiar_voice.voice.build_library`; the caregiver phrase
  editor depends on it.

## Design Notes

- Category and phrase ids become folder and file names in the voice library
  (`library/<category id>/<phrase id>.wav`). Ids therefore allow only lowercase
  letters, digits, and hyphens.
- A phrase keeps its id when its text changes. The library builder can then
  tell which WAV files to rebuild and which to delete.
- New phrase ids use a random suffix, not a counter. Deleting and re-adding a
  phrase never reuses an old id and its stale WAV.
- `validate()` collects all errors instead of stopping at the first one, so the
  caregiver sees every problem at once.
- The file must hold 4 to 6 categories (`MIN_CATEGORIES`, `MAX_CATEGORIES`),
  matching the button count the User tab is designed for.
