# Module Index

One doc per module in `src/familiar_voice/`. Update this list when adding a
module.

| Module | Description |
| --- | --- |
| [`familiar_voice.app`](app.md) | Builds and launches the Gradio app: User tab (default) and Caregiver tab. |
| [`familiar_voice.app.devtools`](devtools.md) | Developer test console: one browser tab per pipeline piece for manual testing. |
| [`familiar_voice.core.config`](config.md) | Returns the filesystem paths for every piece of local app data. |
| [`familiar_voice.core.library`](library.md) | Picks a random built phrase WAV per category, never repeating the previous pick. |
| [`familiar_voice.core.log`](log.md) | Appends interaction events to `log.jsonl` and reads them back newest first. |
| [`familiar_voice.core.phrases`](phrases.md) | Loads, validates, edits, and saves the caregiver's reassurance phrases. |
| [`familiar_voice.voice.build_library`](build_library.md) | Batch-builds the voice library: one cloned-voice WAV per phrase, rebuilt only when it changes. |
| [`familiar_voice.voice.engine`](engine.md) | Turns text and voice samples into a WAV through one swappable voice-cloning interface. |
| [`familiar_voice.voice.preprocess`](preprocess.md) | Converts caregiver recordings into trimmed, normalized mono 24 kHz WAVs for cloning. |
