# `familiar_voice.voice.build_library`

Batch-generates every reassurance phrase in the caregiver's cloned voice and
keeps the voice library in sync with the phrase file.

## Purpose

Voice cloning on a CPU takes seconds to minutes per phrase, far too slow to run
while the person being cared for waits. This module runs that work ahead of
time: it reads the phrases and the caregiver's samples, and writes one WAV per
phrase so the User tab only ever plays files. It rebuilds only what changed and
cleans up after deleted phrases. It does not record or preprocess samples, edit
phrases, or choose which WAV to play.

## Key Components

- `build_library()` — builds new and edited phrases, removes WAVs of deleted
  ones, and returns a `BuildSummary`.
- `BuildSummary` — the phrase ids that were built, skipped, and removed, plus
  elapsed seconds. `str(summary)` gives a one-line report.
- `load_manifest()` — reads `library/manifest.json` as phrase id → entry
  (`category`, `text`, `text_hash`, `path`).
- `manifest_path()`, `find_samples()`, `text_hash()` — the manifest location,
  the sample WAVs used as voice references, and the SHA-256 used to detect
  edits.
- `NoSamplesError` — raised when no samples have been recorded yet.
- `main()` — the command-line entry point.

## Usage

```powershell
python -m familiar_voice.voice.build_library          # build what changed
python -m familiar_voice.voice.build_library --force  # rebuild everything
```

```python
from familiar_voice.voice.build_library import NoSamplesError, build_library


def show(done: int, total: int, text: str) -> None:
    print(f"{done}/{total}: {text}")


try:
    summary = build_library(progress=show)
except NoSamplesError as err:
    print(err)
else:
    print(summary)  # Built 2, skipped 10, removed 1 in 41.3 s.
```

Output layout under the data root:

```text
library/
  manifest.json
  worried/worried-1.wav
  lonely/lonely-1.wav
  ...
```

## Dependencies

- **Uses:** `familiar_voice.core.config` (for `library_dir()`,
  `samples_dir()`), `familiar_voice.core.phrases` (for `load_phrases()`),
  `familiar_voice.voice.engine` (for `synthesize()`).
- **Used by:** nothing yet; the library playback picker and the caregiver's
  "Build voice library" button depend on it.

## Design Notes

- A phrase is skipped only when its text hash and path match the manifest and
  its WAV exists, so a deleted WAV or a phrase moved to another category is
  rebuilt. The hash covers the text only: after re-recording samples, use
  `--force` (or `force=True`).
- Every `*.wav` in `samples/` is passed to the engine as a voice reference.
- The manifest is saved after each phrase, so stopping a long CPU build keeps
  the finished work and the next run resumes. Each WAV is written to
  `<id>.partial.wav` first and renamed only on success, so a crash never
  leaves a truncated WAV that looks built.
- Missing samples raise `NoSamplesError` before anything is touched. It
  subclasses `FileNotFoundError`, and the CLI prints it and exits with code 1.
- An unreadable manifest is treated as empty, which rebuilds the library
  rather than failing.
- Category folders left empty by removals are deleted.
- `progress(done, total, text)` is called after each phrase, built or
  skipped, so a UI progress bar moves steadily.
