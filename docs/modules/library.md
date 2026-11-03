# `familiar_voice.core.library`

Chooses which pre-built phrase WAV to play when the person being cared for
taps a category button.

## Purpose

Each button press should play a random phrase from that category in the
caregiver's voice, and the same sentence should not play twice in a row
because that sounds robotic. This module reads the library manifest, keeps
only the phrases whose WAV is actually on disk, and picks one at random while
avoiding the previous pick. It does not build audio, add the transparency
chime, play sound, or log the press.

## Key Components

- `pick(category)`: returns `(phrase_id, wav_path)` from the shared picker,
  or `None` if the category has no built audio.
- `Picker`: the chooser itself. It remembers the last pick for each category
  and takes an optional `random.Random` so tests get repeatable results.
  - `Picker.pick(category)`: same contract as the module-level `pick`.
  - `Picker.candidates(category)`: every playable `(phrase_id, wav_path)` in
    a category, sorted by phrase id.

## Usage

```python
import random

from familiar_voice.core.library import Picker, pick

result = pick("worried")
if result is None:
    print("No audio yet. Build the voice library first.")
else:
    phrase_id, wav = result
    print(phrase_id, wav)  # worried-2 data/library/worried/worried-2.wav

picker = Picker(random.Random(42))  # repeatable picks, e.g. in tests
picker.pick("lonely")
```

## Dependencies

- **Uses:** `familiar_voice.core.config` (for `library_dir()`),
  `familiar_voice.voice.build_library` (for `load_manifest()`).
- **Used by:** nothing yet; the User tab's big buttons and check-in playback
  depend on it.

## Design Notes

- Candidates come from the manifest, not from scanning folders. Stray or
  `.partial.wav` files are never played, and a manifest entry whose WAV was
  deleted is skipped.
- The manifest is re-read on every pick, so a library rebuilt from the
  Caregiver tab is used right away without restarting the app.
- "No immediate repeat" applies only when a category has two or more playable
  phrases. With one phrase, that phrase plays every time.
- The memory of the last pick is per category and in memory only. The app
  shares one module-level `Picker`, so the rule holds across every button in
  the running app and resets on restart.
- Candidates are sorted before choosing, so a seeded `random.Random` gives
  the same sequence regardless of manifest order.
- Manifest paths that resolve outside the library folder are ignored.
