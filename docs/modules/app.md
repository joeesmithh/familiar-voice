# `familiar_voice.app`

Starts the Familiar Voice app when run as `python -m familiar_voice`.

## Purpose

This package holds the Gradio user interface: the Caregiver tab and the User
tab. `__main__.py` forwards to `app.main.main()`, so the launch command stays
the same as the UI grows. The UI is not built yet; `main()` currently configures
logging and reports that the UI is unavailable. It contains no phrase or voice
logic; see [phrases](phrases.md).

## Key Components

- `main()` — configures logging and launches the app. Currently logs a
  placeholder message.
- `familiar_voice.__main__` — entry point for `python -m familiar_voice`; calls
  `main()`.

## Usage

```bash
python -m familiar_voice
# INFO:familiar_voice.app.main:Familiar Voice UI is not implemented yet (see roadmap F07).
```

## Dependencies

- **Uses:** standard library only (`logging`).
- **Used by:** `familiar_voice.__main__`.

## Design Notes

- The entry point lives in `app.main` rather than `__main__.py`, so tests and
  other code can import and call `main()` without running the module as a
  script.
