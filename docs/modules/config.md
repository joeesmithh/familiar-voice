# `familiar_voice.core.config`

Loads app settings from `config.yaml` and returns the filesystem paths for every
piece of local app data.

## Purpose

Voice samples, generated audio, and logs are private, so they all live under
one git-ignored data root. This module is the single place that knows where
that root is and how it is laid out. Other modules ask it for a path instead of
building paths themselves. It does not read or write file contents; see
[phrases](phrases.md) for the phrase file.

It also reads the app's settings from `config.yaml` into dataclasses, so every
module gets settings (such as whether to synthesize on the CPU or GPU) from one
`config` object.

## Key Components

- `data_dir()` — returns the data root: `FV_DATA_DIR` if set, otherwise `./data`.
- `samples_dir()` — returns `<root>/samples`, for the caregiver's voice samples.
- `library_dir()` — returns `<root>/library`, for pre-generated phrase WAV files.
- `phrases_path()` — returns `<root>/phrases.json`.
- `log_path()` — returns `<root>/log.jsonl`, the interaction log.
- `checkins_path()` — returns `<root>/checkins.json`, the scheduled check-ins.

## Usage

```python
from familiar_voice.core.config import library_dir, phrases_path

print(phrases_path())  # data/phrases.json
wav = library_dir() / "worried" / "worried-1.wav"
```

```bash
# Point the app at a different data root, e.g. a pre-built demo library.
FV_DATA_DIR=demo_data python -m familiar_voice
```

The app defaults to `data/`. The developer console
(`python -m familiar_voice.app.devtools`) defaults to `data_dev_tools/`
(`DEV_TOOLS_DATA_DIR`). Both are git-ignored.

```yaml
# config.yaml (project root)
synthesis:
  device: cpu   # "cpu" or "cuda"
```

```python
from familiar_voice.core.config import config

config.synthesis.device  # "cpu"
```

## Dependencies

- **Uses:** `pyyaml`, standard library (`os`, `pathlib`, `dataclasses`).
- **Used by:** `familiar_voice.core.phrases`, `familiar_voice.core.log`,
  `familiar_voice.voice.engine`, `familiar_voice.voice.build_library`.

## Design Notes

- Directory helpers create their directory on demand, so callers never check
  for existence first.
- File helpers create only the parent directory, never the file. Each owning
  module decides what an empty or missing file means.
- The data root is read from the environment on every call rather than cached.
  Tests set `FV_DATA_DIR` to a temporary folder without reloading the module.
- Settings, unlike paths, are read once at import into the module-level
  `config`. Tests call `load_config(path)` directly instead.
- A missing or empty `config.yaml`, or a missing key, falls back to the
  dataclass defaults. Unknown keys and invalid values raise `ValueError`, so a
  typo such as `devise:` fails at startup instead of being ignored.
- To add a setting, add a field to a section dataclass; to add a section, add a
  dataclass, a `Config` field, and a `_build(...)` line in `load_config()`.
