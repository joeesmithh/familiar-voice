# `familiar_voice.voice.engine`

Turns text and the caregiver's voice samples into a WAV file through one
swappable voice-cloning interface.

## Purpose

The project may run XTTS-v2, Tortoise, or a fallback cloner, and tests must
run without model weights. This module gives every engine the same
`synthesize()` entry point and picks one by name, so the library builder never
depends on a specific engine. It does not preprocess samples, decide which
phrases to build, or play audio.

## Key Components

- `synthesize()` — speaks one phrase and returns the path of the written WAV.
- `Engine` — the `Protocol` an engine implements: one `synthesize()` method
  that writes to a given path.
- `ENGINES` — the registry mapping names (`fake`, `xtts`) to engine classes.
- `get_engine()` — returns the cached instance for a registered name.
- `FakeEngine` — writes a 440 Hz sine tone whose length grows with the text.
- `XTTSEngine` — placeholder for XTTS-v2; raises `NotImplementedError`.

## Usage

```python
from pathlib import Path

from familiar_voice.voice.engine import synthesize

wav = synthesize(
    "I'm thinking of you and I'll see you soon.",
    ref_wavs=[Path("data/samples/sample_1.wav")],
    out_path=Path("data/library/lonely/lonely-1.wav"),
    engine="fake",  # omit to use FV_ENGINE, default "xtts"
)
print(wav)  # data\library\lonely\lonely-1.wav
```

## Dependencies

- **Uses:** `familiar_voice.core.config` (for `data_dir()`), `numpy`,
  `soundfile`.
- **Used by:** nothing yet; the library builder and conversation mode depend
  on it.

## Design Notes

- The engine is chosen by the `engine` argument, then the `FV_ENGINE`
  environment variable, then `xtts`. Tests set `FV_ENGINE=fake`.
- Engines are `Protocol`s, not subclasses, so any object with a matching
  `synthesize()` method works, including test doubles.
- `get_engine()` caches one instance per name. XTTS-v2 takes a long time to
  load on CPU, so it must load only once per process.
- Without `out_path`, the WAV goes in the data root rather than the system
  temp folder, so cloned-voice audio stays in the private, git-ignored folder.
- `FakeEngine` output scales with text length (clamped to 0.2–5 s), so code
  that concatenates or times audio behaves realistically in tests.
