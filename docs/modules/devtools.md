# `familiar_voice.app.devtools`

A developer test console: a separate Gradio page for trying each pipeline piece
by hand in a browser.

## Purpose

The Caregiver and User tabs are not built yet, but samples, phrases, synthesis,
the library builder, and the interaction log are. This console puts one tab on
each so a developer can record a voice, edit phrases, hear cloned speech, build
the library, and write log events without writing code. It is a testing tool
only. It is not the app shown to caregivers or users, and it is not part of the
demo.

## Usage

```powershell
familiar-voice-dev        # same as: python -m familiar_voice.app.devtools
```

Open the local URL Gradio prints (usually <http://127.0.0.1:7860>).

| Variable | Effect |
| --- | --- |
| `FV_DATA_DIR` | Data folder to use. Defaults to `data_dev_tools/` for the console, so the real `data/` is never touched. |
| `FV_ENGINE` | Engine the dropdowns start on (`xtts` or `fake`). Unset or unknown → `xtts`. Set `fake` for fast tone output while testing UI flow. |

```powershell
# Start on the fast fake engine, with a scratch data folder
$env:FV_ENGINE = "fake"; $env:FV_DATA_DIR = "data_scratch"
familiar-voice-dev
```

### Status bar

The line at the top shows the data root and counts of samples (with total
seconds), phrases, built library WAVs, and log events. Click **Refresh status**
after making changes; it does not update by itself.

### Samples tab

The top of the tab shows the passage to read for the next sample. The guided
reading script has 5 passages. Passage 1 is a spoken consent statement. The
others are general, phonetically rich text (the Rainbow Passage, Harvard
sentences, and a passage of questions and numbers for intonation). The
passage moves on after each saved sample and goes back to 1 when samples
are deleted. **Recording tips** expands to advice on the room, the
microphone, and how to speak.

1. Read the shown passage aloud into the microphone, or upload a file, in
   **Recording**.
2. Tick **This is my own voice and I consent**. Nothing is saved without it.
3. Click **Preprocess and save**. The recording is trimmed, normalized, and
   converted to mono 24 kHz, then saved as `samples/sample_<n>.wav`.

The **Samples** box lists each sample's length and the total. It warns under
6 s (too little to clone) and over 60 s (slower builds with no gain). Reading all
5 passages gives about 45–55 s. **Play a saved sample** plays back the
processed version. **Delete all samples** removes every sample WAV.

### Phrases tab

- **phrases.json** editor: edit the whole file as JSON. **Validate** checks it
  against the schema, **Save** validates and then writes it, **Reload from
  disk** discards unsaved edits, and **Reset to defaults** overwrites the file
  with the built-in phrase set.
- **Quick edit**: change one phrase without touching the JSON.
  - **Add**: pick a **Category**, enter **Text**. A new id is generated.
  - **Update**: enter the **Phrase id** and the new **Text**.
  - **Delete**: enter the **Phrase id**.

If the file on disk is invalid, the editor shows the raw text so it can be
fixed.

### Synthesize tab

Speak one line of text in the cloned voice, outside the library.

1. Enter **Text**, pick an **Engine**, and set **Language** (an XTTS-v2 code
   such as `en` or `es`).
2. Click **Synthesize**. **Result** shows the engine, time taken, and file
   name. Use it to measure per-phrase CPU timing.

Every saved sample is used as the voice reference. `xtts` takes seconds to
minutes on CPU, and the first call also loads (and on first run downloads,
~1.8 GB) the model. `fake` writes a 440 Hz tone in milliseconds.

Each output is kept in `synthesized/` with the name
`<YYYYmmdd-HHMMSS>_<engine>_<text-slug>.wav`. Under **Previously synthesized**,
**Play a synthesized phrase** lists them newest first, and **Delete all
synthesized phrases** removes them. Library WAVs are never listed or deleted
here. Older `synth_*.wav` files in the data root also appear in the list.

### Library tab

1. Pick an **Engine**. Tick **Force rebuild everything** after re-recording
   samples, because the builder only detects edited phrase text, not changed
   samples.
2. Click **Build voice library**. A progress bar tracks each phrase, then
   **Summary** reports how many were built, skipped, and removed.

The **manifest.json** table shows each phrase's id, category, text, and whether
its WAV exists. **Play a built phrase** plays a library WAV by id.

### Log tab

Write test events to `log.jsonl` and view them.

- Pick a **Kind** (`button`, `checkin`, `conversation`, `distress`), optionally
  fill in **Category** and **Phrase id**, tick **Flagged** if needed, and click
  **Write event**.
- The table shows the newest events first. **Rows to show** sets how many;
  **Refresh** reloads it. Fields other than the standard columns appear as JSON
  in **extra**.

## Data Layout

Everything lives under the data root (`data_dev_tools/` by default), which is
git-ignored:

```text
data_dev_tools/
  samples/sample_1.wav ...      # Samples tab
  phrases.json                  # Phrases tab
  synthesized/*.wav             # Synthesize tab
  library/manifest.json         # Library tab
  library/<category>/<id>.wav
  log.jsonl                     # Log tab
```

No voice model is saved. XTTS-v2 clones zero-shot from the samples on every
synthesis, so the samples are the only voice data. The shared base model is
cached by coqui-tts outside the project.

## Quick End-to-End Check

1. **Samples**: record the 5 script passages, consenting each time.
2. **Phrases**: click **Reset to defaults**.
3. **Synthesize**: run one line with `fake`, then with `xtts`, and compare the
   timings.
4. **Library**: build with `xtts`, then play a few phrases.
5. **Status bar**: click **Refresh status**. Built WAVs should match the phrase
   count.

## Key Components

- `build_console()`: builds the `gr.Blocks` page; call `.launch()` to serve
  it.
- `main()`: sets `FV_DATA_DIR` to `data_dev_tools/` if unset, then launches.
- Helpers with no Gradio dependency, tested directly: `save_sample()`,
  `current_passage()`, `samples_report()`, `next_sample_path()`, `delete_samples()`,
  `phrases_json()`, `validate_json()`, `synth_dir()`, `synth_out_path()`,
  `find_synthesized()`, `delete_synthesized()`, `manifest_rows()`,
  `event_rows()`, `status_text()`, `progress_adapter()`, `default_engine()`.
- `_on_*` callbacks: thin wrappers that call a helper and refresh the
  dropdowns that depend on it.

## Dependencies

- **Uses:** `gradio`, `soundfile`, `familiar_voice.core.config`,
  `familiar_voice.core.log`, `familiar_voice.core.phrases`,
  `familiar_voice.voice.build_library`, `familiar_voice.voice.engine`,
  `familiar_voice.voice.preprocess`, `familiar_voice.voice.reading_script`.
- **Used by:** nothing. It is a standalone entry point.

## Design Notes

- Errors a developer can fix (no samples, bad phrase file, coqui-tts missing,
  license not accepted) are shown as messages in the page. Anything else is
  raised so Gradio reports it.
- If a synthesis fails, its empty output file is deleted so it never shows up
  as a playable phrase.
- The consent checkbox mirrors the app's rule that only the voice owner may
  clone their own voice.
