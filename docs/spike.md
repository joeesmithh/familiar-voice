# Phase 1 Spike: XTTS-v2 on CPU

Measures how long XTTS-v2 takes to clone a voice and speak one phrase on the
CPU-only demo machine. The numbers decide whether pre-generating the library
is enough and how long the caregiver's "Build voice library" step will take.

## Setup

- **Engine:** Coqui XTTS-v2 (`tts_models/multilingual/multi-dataset/xtts_v2`)
  through `coqui-tts`, on the CPU. See [engine](modules/engine.md).
- **Reference audio:** a teammate's preprocessed samples in `data/samples/`,
  about 30 s in total.
- **Phrases:** the first phrases of the default phrase set.

## How to Reproduce

```bash
# The extra index provides the smaller CPU-only torch wheels.
python -m pip install -e ".[dev]" --extra-index-url https://download.pytorch.org/whl/cpu


python -m pytest -m slow                # end-to-end check; downloads ~1.8 GB once
python scripts/time_engine.py --n 5     # rewrites the Results section below
```

The engine sets `COQUI_TOS_AGREED=1` itself when it loads. This accepts the
Coqui Public Model License, which allows non-commercial use such as coursework.

## Results

The script replaces everything between the markers with its latest run.

<!-- timing:start -->
### Run 2026-11-03 — `xtts`

- **Machine:** Windows-10-10.0.26300-SP0, Intel64 Family 6 Model 198 Stepping 2, GenuineIntel, 18 logical cores, Python 3.11.9
- **Reference audio:** 1 file(s), 27.8 s
- **Model load:** 9.0 s

| # | Phrase | Synthesis (s) | Audio (s) | Real-time factor |
| --- | --- | --- | --- | --- |
| 1 | It's okay. You are safe, and I'm thinking about you. | 6.2 | 5.9 | 1.05 |
| 2 | Take a slow, deep breath with me. In, and out. You're doing great. | 8.9 | 8.2 | 1.08 |
| 3 | Everything is alright. Your nurse is right there if you need anything. | 5.4 | 5.1 | 1.05 |
| 4 | I miss you too. I love you very much. | 6.2 | 5.9 | 1.05 |
| 5 | You are never alone. I'm thinking about you right now. | 4.3 | 4.0 | 1.08 |

**Mean:** 6.2 s per phrase; real-time factor 1.06 (synthesis time ÷ audio length; below 1 is faster than real time).
<!-- timing:end -->

## Decision

To fill in after the run: keep XTTS-v2, or switch to a fallback cloner
(Chatterbox or OpenVoice v2) if it fails to install or is too slow.
