# Familiar Voice

Familiar Voice is a Gradio web app for people with intellectual or cognitive disabilities who feel anxious when their caregiver is away. The caregiver records about 30 seconds of speech and writes a set of reassurance phrases. The app clones the caregiver's voice and pre-builds a library of those phrases in that voice. The person being cared for taps buttons to hear a familiar, calming reply.

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

#### Troubleshooting: SSL certificate error on model download

On Windows, if your venv was created from a conda Python, the first XTTS-v2
download can fail with `FileNotFoundError: [Errno 2] No such file or directory`
raised from `ssl.create_default_context` / `load_verify_locations`.

Cause: conda's bash activation script sets `SSL_CERT_FILE` to
`<conda env>/ssl/cacert.pem`. On Windows that file actually lives at
`<conda env>\Library\ssl\cacert.pem`. Any shell started from Git Bash, or from a
terminal that inherits its environment, passes the wrong path to Python.

Check the value:

```powershell
$env:SSL_CERT_FILE
```

Fix it by pointing the variable at the real file, using your own conda env path:

```powershell
# PowerShell, current session only
$env:SSL_CERT_FILE = "$env:USERPROFILE\miniconda3\envs\python_3.11\Library\ssl\cacert.pem"
```

```bash
# Git Bash, current session only
export SSL_CERT_FILE="$USERPROFILE\miniconda3\envs\python_3.11\Library\ssl\cacert.pem"
```

Other options:

- Clear it for the session (`Remove-Item Env:SSL_CERT_FILE` or
  `unset SSL_CERT_FILE`). Python then uses the Windows certificate store.
- Make it permanent by setting `SSL_CERT_FILE` as a user environment variable in
  Windows settings, then opening a new terminal.

This only matters for downloads. Once the model is cached in
`~/.cache/huggingface`, later runs work offline.

### 3. Run the app

```bash
python -m familiar_voice
```

Then open the local URL Gradio prints (usually <http://127.0.0.1:7860>).

To test the pipeline pieces by hand (samples, phrases, synthesis, library build,
log) before the full UI exists, run the developer console instead:

```bash
python -m familiar_voice.app.devtools
```

The console stores its data in `data_dev_tools/` by default, and the app uses
`data/`. Both folders are git-ignored. Set `FV_DATA_DIR` to use a different folder.

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

Integration tests need `ANTHROPIC_API_KEY` set as an environment variable.
The XTTS-v2 engine accepts the Coqui Public Model License (non-commercial use)
by itself when it loads, so you don't need to set `COQUI_TOS_AGREED`. The first run downloads the
model (about 1.8 GB). See [docs/spike.md](docs/spike.md) for CPU timings.