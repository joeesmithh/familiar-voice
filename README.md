# Familiar Voice

Familiar Voice is a Gradio web app for people with intellectual or cognitive disabilities who feel anxious when their caregiver is away. The caregiver records about 30 seconds of speech and writes a set of reassurance phrases. The app clones the caregiver's voice and pre-builds a library of those phrases in that voice. The person being cared for taps buttons to hear a familiar, calming reply.

## Quick Start

### Prerequisites

- **Python 3.11.** coqui-tts (XTTS-v2) supports only Python 3.10 and 3.11.
  Install a standalone Python:
  - Windows: `winget install Python.Python.3.11`, or the installer from
    [python.org](https://www.python.org/downloads/windows/). This also installs the
    `py` launcher, which lets several Python versions sit side by side.
  - macOS: `brew install python@3.11`
  - Linux: `sudo apt install python3.11 python3.11-venv`
- **ffmpeg** on your `PATH`. pydub uses it to convert voice samples.
  - Windows: `winget install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

### 1. Create and activate a virtual environment

| OS            | Create command                 |
| ------------- | ------------------------------ |
| Windows       | `py -3.11 -m venv .venv`       |
| macOS / Linux | `python3.11 -m venv .venv`     |

| Shell                | Activate command                |
| -------------------- | ------------------------------- |
| PowerShell (Windows) | `.venv\Scripts\Activate.ps1`    |
| Git Bash (Windows)   | `source .venv/Scripts/activate` |
| macOS / Linux        | `source .venv/bin/activate`     |

If PowerShell refuses to run `Activate.ps1`, allow local scripts once with
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 2. Install dependencies

All dependencies and tool settings (Ruff, pytest) live in `pyproject.toml`.

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

`-e` installs the project in editable mode, so code changes take effect without
reinstalling. `[dev]` adds the development tools (Ruff and pytest); leave it off
on a machine that only runs the app.

#### Optional: Nvidia GPU (CUDA) support

Voice synthesis runs on the CPU by default. With an Nvidia GPU, building the
voice library is much faster. The default install gives you CPU-only PyTorch, so
you must replace it with the CUDA build:

1. Install a recent Nvidia driver. `nvidia-smi` should list your GPU. You don't
   need the CUDA Toolkit, because the PyTorch wheels include the CUDA runtime.
2. With the virtual environment active, reinstall torch and torchaudio from
   PyTorch's CUDA 12.6 index. Keep version 2.8.0, which satisfies the project's
   `<2.9` pin:

   ```bash
   python -m pip install --force-reinstall torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
   ```

3. Check that PyTorch can see the GPU:

   ```bash
   python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```

   It should print `True` followed by your GPU name. If `torch.__version__` ends
   in `+cpu` (for example, after pip reinstalled torch), repeat step 2.

Then turn on GPU synthesis as described in
[Enable GPU phrase synthesis](#enable-gpu-phrase-synthesis).

#### Troubleshooting: SSL certificate error on model download

If the first XTTS-v2 download fails with
`FileNotFoundError: [Errno 2] No such file or directory` raised from
`ssl.create_default_context` / `load_verify_locations`, the `SSL_CERT_FILE`
environment variable points at a certificate file that doesn't exist. Some other
Python distribution usually left it behind.

Check the value:

```powershell
$env:SSL_CERT_FILE
```

Clear it for the session with `Remove-Item Env:SSL_CERT_FILE` (PowerShell) or
`unset SSL_CERT_FILE` (Git Bash). Python then uses the system certificate store.
If it comes back in every new terminal, delete it from your user environment
variables in Windows settings, or from your shell profile.

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
App settings (such as `synthesis.device: cpu` or `cuda`) live in `config.yaml`;
set `FV_CONFIG` to use a different settings file.
See [docs/modules/devtools.md](docs/modules/devtools.md) for a tab-by-tab guide.

#### Enable GPU phrase synthesis

After you install CUDA support (see
[Optional: Nvidia GPU (CUDA) support](#optional-nvidia-gpu-cuda-support)), set
the device in `config.yaml`:

```yaml
synthesis:
  device: cuda
```

Every phrase synthesis now runs on the GPU. That covers
`python -m familiar_voice.voice.build_library`, the developer console's build
button, and its Synthesize tab. Restart the app after you change the setting. If
PyTorch can't use the GPU, the build stops with an error that explains the fix.
Set `device: cpu` to switch back.

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