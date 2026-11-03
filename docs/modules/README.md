# Module Index

One doc per module in `src/familiar_voice/`. Update this list when adding a
module.

| Module | Description |
| --- | --- |
| [`familiar_voice.app`](app.md) | Starts the app via `python -m familiar_voice`; future home of the Gradio UI. |
| [`familiar_voice.core.config`](config.md) | Returns the filesystem paths for every piece of local app data. |
| [`familiar_voice.core.log`](log.md) | Appends interaction events to `log.jsonl` and reads them back newest first. |
| [`familiar_voice.core.phrases`](phrases.md) | Loads, validates, edits, and saves the caregiver's reassurance phrases. |
| [`familiar_voice.voice.engine`](engine.md) | Turns text and voice samples into a WAV through one swappable voice-cloning interface. |
