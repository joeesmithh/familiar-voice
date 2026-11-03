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

# PowerShell: $env:COQUI_TOS_AGREED = "1"
export COQUI_TOS_AGREED=1

python -m pytest -m slow                # end-to-end check; downloads ~1.8 GB once
python scripts/time_engine.py --n 5     # rewrites the Results section below
```

Setting `COQUI_TOS_AGREED=1` accepts the Coqui Public Model License, which
allows non-commercial use such as coursework.

## Results

The script replaces everything between the markers with its latest run.

<!-- timing:start -->
Not run yet.
<!-- timing:end -->

## Decision

To fill in after the run: keep XTTS-v2, or switch to a fallback cloner
(Chatterbox or OpenVoice v2) if it fails to install or is too slow.
