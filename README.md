# Familiar Voice

## Quick Start

### Prerequisites

- **Python 3.11.** coqui-tts (XTTS-v2) supports only Python 3.10 and 3.11.
- **ffmpeg** on your `PATH`. pydub uses it to convert voice samples.
  - Windows: `winget install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
```

| Shell                | Activate command                |
| -------------------- | ------------------------------- |
| PowerShell (Windows) | `.venv\Scripts\Activate.ps1`    |
| Git Bash (Windows)   | `source .venv/Scripts/activate` |
| macOS / Linux        | `source .venv/bin/activate`     |

On Windows with more than one Python installed, use `py -3.11 -m venv .venv` instead.

### 2. Install dependencies

All dependencies and tool settings (Ruff, pytest) live in `pyproject.toml`.

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

`-e` installs the project in editable mode, so code changes take effect without
reinstalling. `[dev]` adds the development tools (Ruff and pytest); leave it off
on a machine that only runs the app.

### 3. Run the app

```bash
python -m familiar_voice
```

Then open the local URL Gradio prints (usually <http://127.0.0.1:7860>).

### 4. Before every commit

Run these from the project root:

```bash
ruff format .
ruff check . --fix
python -m pytest
```

Fix any remaining Ruff warnings and confirm all tests pass before you commit.

| Command                               | What it runs                                       |
| ------------------------------------- | -------------------------------------------------- |
| `python -m pytest`                    | Fast unit tests (default)                          |
| `python -m pytest -m slow`            | Tests that load real voice models (minutes on CPU) |
| `python -m pytest -m integration`     | Tests that call the Claude API                     |

Integration tests need `ANTHROPIC_API_KEY` set as an environment variable. Never commit the key.