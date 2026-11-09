# `familiar_voice.voice.reading_script`

Guided reading passages and recording tips for capturing good voice-cloning
samples.

## Purpose

Improvised speech makes poor reference audio because it is often short, flat,
and covers few sounds. This module supplies 5 passages to read, one per sample,
plus advice on how to record them. It does not record, preprocess, or store
audio.

| # | Passage | Why |
| --- | --- | --- |
| 1 | Spoken consent statement | Required: only the voice owner may clone their voice. |
| 2–3 | Rainbow Passage (Fairbanks, 1960) | Designed to contain every English phoneme. |
| 4 | Harvard sentences (IEEE, 1969) | Phonetically balanced sentences. |
| 5 | Questions, an exclamation, numbers | Varied intonation and prosody. |

All 5 take about 45–55 s at a natural pace, which is inside the 6–60 s window
from `familiar_voice.voice.preprocess`.

## Key Components

- `READING_SCRIPT`: tuple of the 5 passages, in recording order.
- `CONSENT_PASSAGE`: the first passage.
- `RECORDING_TIPS`: Markdown bullet list of recording advice.
- `passage_markdown(n_saved)`: Markdown for the next passage, given how many
  samples are already saved, or a done message after the last one.

## Usage

```python
from familiar_voice.voice.reading_script import passage_markdown

print(passage_markdown(0))
# **Read this aloud (passage 1 of 5):** This passage is your spoken consent.
#
# > My name is [your name]. This is my own voice, ...
```

## Dependencies

- **Uses:** nothing.
- **Used by:** `familiar_voice.app.devtools` (Samples tab).

## Design Notes

- The passages other than consent are intentionally general, not caregiver
  phrases. They are chosen for phonetic coverage, not content.
- Passages 2–5 are public-domain standard speech-recording texts.
