# `familiar_voice.app`

Builds and launches the Familiar Voice Gradio app when run as
`python -m familiar_voice`.

## Purpose

This package holds the Gradio user interface. `app.main` assembles one page
with two tabs: the User tab for the person being cared for, and the Caregiver
tab for setup. The User tab comes first, so it is what opens by default. The
tabs are empty shells for now; buttons, sample recording, the phrase editor,
and the log view are added in later features.

## Key Components

- `build_app()` — returns the `gr.Blocks` page with the User and Caregiver
  tabs. Tests call it without launching a server.
- `main()` — configures logging and launches `build_app()`.
- `user.build_user_tab()` — adds the User tab to the enclosing `gr.Blocks`.
- `caregiver.build_caregiver_tab()` — adds the Caregiver tab to the enclosing
  `gr.Blocks`.
- `familiar_voice.__main__` — entry point for `python -m familiar_voice`;
  calls `main()`.

## Usage

```bash
python -m familiar_voice
# Running on local URL:  http://127.0.0.1:7860
```

```python
from familiar_voice.app.main import build_app

app = build_app()  # build without serving, e.g. in tests
```

## Dependencies

- **Uses:** `gradio`.
- **Used by:** `familiar_voice.__main__`.

## Design Notes

- Each tab lives in its own module with a `build_*_tab()` function, so the
  two views grow independently and `main.py` stays a short assembly step.
- Gradio callbacks stay thin: they call `core/` and `voice/` functions, which
  are what tests target.
- The entry point lives in `app.main` rather than `__main__.py`, so tests and
  other code can import `main()` without running the module as a script.
- The developer console (`app.devtools`) is a separate page and is not part
  of this app; see [devtools](devtools.md).
