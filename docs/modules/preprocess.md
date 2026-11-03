# `familiar_voice.voice.preprocess`

Converts caregiver voice recordings into trimmed, peak-normalized, mono 24 kHz
WAV files for voice cloning.

## Purpose

Recordings come from a browser microphone or a file upload in any format,
channel count, and sample rate, often with silence at each end. Voice cloning
works best on clean, consistently leveled clips, so this module gives every
sample the same shape before the library builder uses it. It does not record
audio, check consent, or choose where samples are stored.

## Key Components

- `preprocess()` — converts one recording and writes the cleaned WAV.
- `total_duration()` — sums sample lengths in seconds and logs a warning
  outside 6–60 s.
- `TARGET_SAMPLE_RATE` — 24 kHz, the rate XTTS-v2 expects and produces.
- `MIN_TOTAL_SECONDS`, `MAX_TOTAL_SECONDS` — the recommended range of total
  reference speech.

## Usage

```python
from familiar_voice.core.config import samples_dir
from familiar_voice.voice.preprocess import preprocess, total_duration

preprocess("upload.m4a", samples_dir() / "sample_1.wav")

seconds = total_duration(samples_dir().glob("sample_*.wav"))
print(f"{seconds:.1f} s of speech")  # 7.4 s of speech
```

## Dependencies

- **Uses:** `pydub` (needs `ffmpeg` on `PATH`), `soundfile`.
- **Used by:** nothing yet; the caregiver sample recorder depends on it.

## Design Notes

- `ffmpeg` must be installed separately. Tests that convert audio skip when
  it is missing.
- The silence threshold is 40 dB below the recording's own peak, not a fixed
  level, so quiet and loud recordings trim the same way. 100 ms of padding
  stays at each end so word onsets are not clipped.
- Output is 16-bit PCM with its peak 1 dB below full scale, leaving headroom
  so later resampling cannot clip.
- A recording with no sound at all raises `ValueError` instead of writing an
  empty sample.
- `total_duration()` logs instead of raising, so the UI can still save a short
  first sample and show the running total.
