"""Developer test console for trying the voice pipeline by hand.

This is a separate Gradio page, not part of the Caregiver/User app. It puts
one tab on each feature built so far (samples, phrases, synthesis, library
builder, interaction log) so a developer can test them in a browser before
the real UI exists. Run it with::

    python -m familiar_voice.app.devtools

It stores its data in ``data_dev_tools/`` by default, apart from the real
``data/`` folder. Set ``FV_DATA_DIR`` to use a different folder.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import gradio as gr
import soundfile as sf

from familiar_voice.app import serve
from familiar_voice.core.config import (
    DATA_DIR_ENV_VAR,
    DEV_TOOLS_DATA_DIR,
    config,
    data_dir,
    library_dir,
    phrases_path,
    samples_dir,
)
from familiar_voice.core.log import EVENT_KINDS, log_event, read_events
from familiar_voice.core.phrases import (
    add_phrase,
    default_phrases,
    delete_phrase,
    load_phrases,
    save_phrases,
    update_phrase,
    validate,
)
from familiar_voice.voice.build_library import (
    NoSamplesError,
    ProgressCallback,
    build_library,
    find_samples,
    load_manifest,
)
from familiar_voice.voice.engine import (
    DEFAULT_ENGINE,
    ENGINE_ENV_VAR,
    ENGINES,
    synthesize,
)
from familiar_voice.voice.preprocess import (
    MAX_TOTAL_SECONDS,
    MIN_TOTAL_SECONDS,
    preprocess,
    total_duration,
)
from familiar_voice.voice.reading_script import RECORDING_TIPS, passage_markdown

logger = logging.getLogger(__name__)

SAMPLE_NAME = re.compile(r"^sample_(\d+)\.wav$")
SYNTH_DIR_NAME = "synthesized"  # Synthesize-tab outputs, apart from library/
LEGACY_SYNTH_GLOB = "synth_*.wav"  # older outputs written to the data root
SLUG_MAX_CHARS = 40
MANIFEST_HEADERS = ["id", "category", "text", "on disk"]
EVENT_HEADERS = ["ts", "kind", "category", "phrase_id", "flagged", "extra"]
DEFAULT_EVENT_LIMIT = 50

# Errors a synthesis or build can raise for reasons the developer can fix
# (no samples, license not accepted, coqui-tts missing, bad phrase file).
# They are shown as messages; anything else propagates so Gradio reports it.
EXPECTED_ERRORS = (NoSamplesError, ValueError, RuntimeError, ImportError, OSError)


# --- Helpers (tested directly) ------------------------------------------------


def default_engine() -> str:
    """Return the engine the dropdowns start on.

    Returns
    -------
    str
        ``FV_ENGINE`` if it names a registered engine, otherwise
        ``DEFAULT_ENGINE`` (``"xtts"``).
    """
    name = os.environ.get(ENGINE_ENV_VAR, "")
    return name if name in ENGINES else DEFAULT_ENGINE


def next_sample_path() -> Path:
    """Return the first unused ``samples/sample_<n>.wav`` path.

    Returns
    -------
    Path
        Path with ``n`` one higher than the largest existing sample number.
    """
    numbers = [
        int(match.group(1))
        for path in samples_dir().iterdir()
        if (match := SAMPLE_NAME.match(path.name))
    ]
    return samples_dir() / f"sample_{max(numbers, default=0) + 1}.wav"


def synth_dir() -> Path:
    """Return the folder for Synthesize-tab outputs, creating it if needed.

    Returns
    -------
    Path
        ``<data root>/synthesized``.
    """
    path = data_dir() / SYNTH_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def synth_out_path(text: str, engine: str) -> Path:
    """Return a new, readable WAV path for one synthesized phrase.

    Parameters
    ----------
    text : str
        The phrase; its first words become part of the file name.
    engine : str
        Engine name, also part of the file name.

    Returns
    -------
    Path
        ``synthesized/<YYYYmmdd-HHMMSS>_<engine>_<slug>.wav``, with a
        ``_<n>`` suffix if that name is already taken.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:SLUG_MAX_CHARS]
    stem = f"{time.strftime('%Y%m%d-%H%M%S')}_{engine}_{slug.strip('-') or 'phrase'}"
    path = synth_dir() / f"{stem}.wav"
    n = 2
    while path.exists():
        path = synth_dir() / f"{stem}_{n}.wav"
        n += 1
    return path


def find_synthesized() -> list[Path]:
    """List every individually synthesized WAV, newest first.

    Returns
    -------
    list[Path]
        WAVs in ``synthesized/`` plus older ``synth_*.wav`` files in the
        data root. Library WAVs are not included.
    """
    paths = [*synth_dir().glob("*.wav"), *data_dir().glob(LEGACY_SYNTH_GLOB)]
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def delete_synthesized() -> str:
    """Delete every individually synthesized WAV.

    Returns
    -------
    str
        How many files were removed.
    """
    paths = find_synthesized()
    for path in paths:
        path.unlink(missing_ok=True)
    return f"Deleted {len(paths)} synthesized file(s)."


def samples_report() -> str:
    """Describe the saved samples, their total length, and any warning.

    Returns
    -------
    str
        One line per sample, then the total and a too-short/too-long note.
    """
    samples = find_samples()
    if not samples:
        return "No samples saved yet."
    lines = [f"{path.name}: {sf.info(path).duration:.1f} s" for path in samples]
    total = total_duration(samples)
    lines.append(f"Total: {total:.1f} s")
    if total < MIN_TOTAL_SECONDS:
        lines.append(f"Warning: under {MIN_TOTAL_SECONDS:.0f} s, too little to clone.")
    elif total > MAX_TOTAL_SECONDS:
        lines.append(f"Warning: over {MAX_TOTAL_SECONDS:.0f} s, builds will be slow.")
    return "\n".join(lines)


def save_sample(path: str | Path | None, consented: bool) -> str:
    """Preprocess one recording into the samples folder.

    Parameters
    ----------
    path : str, Path, or None
        The recorded or uploaded file; ``None`` if nothing was recorded.
    consented : bool
        Whether the speaker confirmed it is their own voice and they consent.

    Returns
    -------
    str
        A status message followed by `samples_report`.
    """
    if not path:
        return "Record or upload audio first."
    if not consented:
        return "Not saved: tick the consent box first. Only clone your own voice."
    try:
        out = preprocess(path, next_sample_path())
    except (FileNotFoundError, ValueError) as err:
        return f"Not saved: {err}"
    return f"Saved {out.name}.\n\n{samples_report()}"


def current_passage() -> str:
    """Return the reading-script passage for the next sample, as Markdown.

    Returns
    -------
    str
        The passage after the ones already saved, or a done message.
    """
    return passage_markdown(len(find_samples()))


def delete_samples() -> str:
    """Delete every saved sample WAV.

    Returns
    -------
    str
        How many files were removed.
    """
    samples = find_samples()
    for path in samples:
        path.unlink(missing_ok=True)
    return f"Deleted {len(samples)} sample(s)."


def phrases_json() -> str:
    """Return the phrase file as pretty JSON for the editor.

    Returns
    -------
    str
        The loaded phrases, or the raw file text if it is currently invalid
        so it can be fixed in the editor.
    """
    try:
        return json.dumps(load_phrases(), indent=2, ensure_ascii=False)
    except ValueError:
        return phrases_path().read_text(encoding="utf-8")


def validate_json(text: str) -> list[str]:
    """Check phrase JSON from the editor.

    Parameters
    ----------
    text : str
        Editor contents.

    Returns
    -------
    list[str]
        JSON syntax errors or schema errors; empty if the data is valid.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        return [f"Invalid JSON: {err}"]
    if not isinstance(data, dict):
        return ["Phrase data must be a JSON object."]
    return validate(data)


def manifest_rows() -> list[list[Any]]:
    """Return the library manifest as table rows.

    Returns
    -------
    list[list]
        ``[id, category, text, on disk]`` for each built phrase.
    """
    root = library_dir()
    return [
        [
            pid,
            entry.get("category"),
            entry.get("text"),
            (root / entry["path"]).is_file(),
        ]
        for pid, entry in load_manifest().items()
    ]


def event_rows(limit: int | None = DEFAULT_EVENT_LIMIT) -> list[list[Any]]:
    """Return logged events as table rows, newest first.

    Parameters
    ----------
    limit : int or None, optional
        Maximum number of rows.

    Returns
    -------
    list[list]
        ``[ts, kind, category, phrase_id, flagged, extra]``, where ``extra``
        is any other fields as JSON.
    """
    rows = []
    for event in read_events(None if limit is None else int(limit)):
        extra = {k: v for k, v in event.items() if k not in EVENT_HEADERS}
        rows.append(
            [
                event.get("ts"),
                event.get("kind"),
                event.get("category"),
                event.get("phrase_id"),
                event.get("flagged"),
                json.dumps(extra, ensure_ascii=False) if extra else "",
            ]
        )
    return rows


def progress_adapter(gr_progress: Any) -> ProgressCallback:
    """Turn a `gr.Progress` into a `build_library` progress callback.

    Parameters
    ----------
    gr_progress : callable
        Called as ``gr_progress(fraction, desc=text)``.

    Returns
    -------
    ProgressCallback
        Callback taking ``(done, total, text)``.
    """

    def report(done: int, total: int, text: str) -> None:
        gr_progress(done / total if total else 1.0, desc=text)

    return report


def status_text() -> str:
    """Return a one-line summary of what is in the data folder.

    Returns
    -------
    str
        Data root, sample count and length, phrase count, WAVs, log events.
    """
    samples = find_samples()
    seconds = sum(sf.info(p).duration for p in samples)
    try:
        n_phrases = sum(len(c["phrases"]) for c in load_phrases()["categories"])
    except ValueError:
        n_phrases = "invalid file"
    built = sum(1 for row in manifest_rows() if row[3])
    return (
        f"**Data root:** `{data_dir().resolve()}` · samples: {len(samples)} "
        f"({seconds:.1f} s) · phrases: {n_phrases} · built WAVs: {built} · "
        f"log events: {len(read_events())}"
    )


# --- Callbacks (thin wrappers that also refresh widgets) ----------------------


def _sample_choices() -> list[str]:
    return [p.name for p in find_samples()]


def _category_choices() -> list[str]:
    try:
        return [c["id"] for c in load_phrases()["categories"]]
    except ValueError:
        return []


def _on_save_sample(path: str | None, consented: bool) -> tuple[str, Any, str]:
    message = save_sample(path, consented)
    return message, gr.Dropdown(choices=_sample_choices()), current_passage()


def _on_delete_samples() -> tuple[str, Any, None, str]:
    message = delete_samples()
    return message, gr.Dropdown(choices=[], value=None), None, current_passage()


def _on_play_sample(name: str | None) -> str | None:
    return str(samples_dir() / name) if name else None


def _on_validate(text: str) -> str:
    errors = validate_json(text)
    return "Valid." if not errors else "Errors:\n- " + "\n- ".join(errors)


def _on_save_phrases(text: str) -> tuple[str, Any]:
    errors = validate_json(text)
    if errors:
        return "Not saved:\n- " + "\n- ".join(errors), gr.Dropdown()
    save_phrases(json.loads(text))
    return "Saved.", gr.Dropdown(choices=_category_choices())


def _on_reset_phrases() -> tuple[str, str, Any]:
    save_phrases(default_phrases())
    return (
        phrases_json(),
        "Reset to defaults.",
        gr.Dropdown(choices=_category_choices()),
    )


def _quick_edit(
    action: str, category: str, phrase_id: str, text: str
) -> tuple[str, str]:
    try:
        data = load_phrases()
        if action == "add":
            if not category:
                return phrases_json(), "Pick a category."
            new_id = add_phrase(data, category, text)
            message = f"Added {new_id}."
        elif action == "update":
            update_phrase(data, phrase_id.strip(), text)
            message = f"Updated {phrase_id}."
        else:
            delete_phrase(data, phrase_id.strip())
            message = f"Deleted {phrase_id}."
        save_phrases(data)
    except (KeyError, ValueError) as err:
        return phrases_json(), f"Failed: {err}"
    return phrases_json(), message


def _synth_choices() -> list[tuple[str, str]]:
    root = data_dir()
    return [(p.name, str(p.relative_to(root))) for p in find_synthesized()]


def _on_synthesize(text: str, engine: str, lang: str) -> tuple[str | None, str, Any]:
    start = time.perf_counter()
    out_path = synth_out_path(text, engine) if text.strip() else None
    try:
        path = synthesize(
            text, find_samples(), lang=lang or "en", out_path=out_path, engine=engine
        )
    except EXPECTED_ERRORS as err:
        if out_path is not None:
            out_path.unlink(missing_ok=True)
        return None, f"Failed: {err}", gr.Dropdown(choices=_synth_choices())
    return (
        str(path),
        f"{engine}: {time.perf_counter() - start:.2f} s → {path.name}",
        gr.Dropdown(choices=_synth_choices()),
    )


def _on_play_synthesized(name: str | None) -> str | None:
    if not name:
        return None
    path = data_dir() / name
    return str(path) if path.is_file() else None


def _on_delete_synthesized() -> tuple[str, Any, None]:
    return delete_synthesized(), gr.Dropdown(choices=[], value=None), None


def _on_build(
    engine: str,
    force: bool,
    progress: gr.Progress = gr.Progress(),  # noqa: B008 (Gradio injects it)
) -> tuple[str, list[list[Any]], Any]:
    try:
        summary = build_library(
            progress=progress_adapter(progress), force=force, engine=engine
        )
        message = str(summary)
    except EXPECTED_ERRORS as err:
        message = f"Failed: {err}"
    return message, manifest_rows(), gr.Dropdown(choices=list(load_manifest()))


def _on_play_library(phrase_id: str | None) -> str | None:
    entry = load_manifest().get(phrase_id or "")
    if entry is None:
        return None
    path = library_dir() / entry["path"]
    return str(path) if path.is_file() else None


def _on_log_event(
    kind: str, category: str, phrase_id: str, flagged: bool, limit: float
) -> tuple[str, list[list[Any]]]:
    event = log_event(
        kind, category=category or None, phrase_id=phrase_id or None, flagged=flagged
    )
    return f"Logged at {event['ts']}.", event_rows(limit)


# --- Layout -------------------------------------------------------------------


def build_console() -> gr.Blocks:
    """Build the developer test console.

    Returns
    -------
    gr.Blocks
        The console app; call ``.launch()`` to serve it.
    """
    engines = sorted(ENGINES)
    with gr.Blocks(title="Familiar Voice — Dev Console") as console:
        gr.Markdown(
            "# Familiar Voice — Developer Console\n"
            "Testing tool only. Not the Caregiver/User app."
        )
        with gr.Row():
            status = gr.Markdown()
            refresh_status = gr.Button("Refresh status", scale=0)
        refresh_status.click(status_text, outputs=status)

        with gr.Tab("Samples"):
            script_md = gr.Markdown()
            with gr.Accordion("Recording tips", open=False):
                gr.Markdown(RECORDING_TIPS)
            recording = gr.Audio(
                sources=["microphone", "upload"], type="filepath", label="Recording"
            )
            consent = gr.Checkbox(
                label="This is my own voice and I consent "
                "(passage 1 is the spoken consent)"
            )
            with gr.Row():
                save_btn = gr.Button("Preprocess and save", variant="primary")
                delete_btn = gr.Button("Delete all samples", variant="stop")
            samples_out = gr.Textbox(label="Samples", lines=6, interactive=False)
            with gr.Row():
                sample_pick = gr.Dropdown(label="Play a saved sample", choices=[])
                sample_audio = gr.Audio(label="Saved sample", interactive=False)
            save_btn.click(
                _on_save_sample,
                [recording, consent],
                [samples_out, sample_pick, script_md],
            )
            delete_btn.click(
                _on_delete_samples,
                outputs=[samples_out, sample_pick, sample_audio, script_md],
            )
            sample_pick.change(_on_play_sample, sample_pick, sample_audio)

        with gr.Tab("Phrases"):
            editor = gr.Code(language="json", label="phrases.json", lines=20)
            with gr.Row():
                validate_btn = gr.Button("Validate")
                save_phr_btn = gr.Button("Save", variant="primary")
                reload_btn = gr.Button("Reload from disk")
                reset_btn = gr.Button("Reset to defaults", variant="stop")
            phrases_msg = gr.Textbox(label="Result", lines=3, interactive=False)
            gr.Markdown("### Quick edit")
            with gr.Row():
                qe_category = gr.Dropdown(label="Category (add)", choices=[])
                qe_id = gr.Textbox(label="Phrase id (update/delete)")
                qe_text = gr.Textbox(label="Text (add/update)")
            with gr.Row():
                add_btn = gr.Button("Add")
                update_btn = gr.Button("Update")
                del_phr_btn = gr.Button("Delete")
            validate_btn.click(_on_validate, editor, phrases_msg)
            save_phr_btn.click(_on_save_phrases, editor, [phrases_msg, qe_category])
            reload_btn.click(phrases_json, outputs=editor)
            reset_btn.click(
                _on_reset_phrases, outputs=[editor, phrases_msg, qe_category]
            )
            for button, action in (
                (add_btn, "add"),
                (update_btn, "update"),
                (del_phr_btn, "delete"),
            ):
                button.click(
                    lambda c, i, t, a=action: _quick_edit(a, c, i, t),
                    [qe_category, qe_id, qe_text],
                    [editor, phrases_msg],
                )

        with gr.Tab("Synthesize"):
            gr.Markdown(
                "Uses every saved sample as the reference voice. `xtts` is "
                "slow on CPU; `fake` writes a tone."
            )
            with gr.Row():
                synth_text = gr.Textbox(
                    label="Text", value="It's okay. You are safe.", scale=3
                )
                synth_engine = gr.Dropdown(
                    engines, value=default_engine(), label="Engine"
                )
                synth_lang = gr.Textbox(label="Language", value="en")
            synth_btn = gr.Button("Synthesize", variant="primary")
            synth_audio = gr.Audio(label="Output", interactive=False)
            synth_msg = gr.Textbox(label="Result", interactive=False)
            gr.Markdown("### Previously synthesized (not the library)")
            with gr.Row():
                synth_pick = gr.Dropdown(label="Play a synthesized phrase", choices=[])
                synth_past_audio = gr.Audio(label="Synthesized WAV", interactive=False)
            delete_synth_btn = gr.Button(
                "Delete all synthesized phrases", variant="stop"
            )
            synth_btn.click(
                _on_synthesize,
                [synth_text, synth_engine, synth_lang],
                [synth_audio, synth_msg, synth_pick],
            )
            synth_pick.change(_on_play_synthesized, synth_pick, synth_past_audio)
            delete_synth_btn.click(
                _on_delete_synthesized,
                outputs=[synth_msg, synth_pick, synth_past_audio],
            )

        with gr.Tab("Library"):
            with gr.Row():
                build_engine = gr.Dropdown(
                    engines, value=default_engine(), label="Engine"
                )
                force = gr.Checkbox(label="Force rebuild everything")
            build_btn = gr.Button("Build voice library", variant="primary")
            build_msg = gr.Textbox(label="Summary", interactive=False)
            manifest = gr.Dataframe(
                headers=MANIFEST_HEADERS, label="manifest.json", interactive=False
            )
            with gr.Row():
                lib_pick = gr.Dropdown(label="Play a built phrase", choices=[])
                lib_audio = gr.Audio(label="Library WAV", interactive=False)
            build_btn.click(
                _on_build, [build_engine, force], [build_msg, manifest, lib_pick]
            )
            lib_pick.change(_on_play_library, lib_pick, lib_audio)

        with gr.Tab("Log"):
            with gr.Row():
                kind = gr.Dropdown(sorted(EVENT_KINDS), value="button", label="Kind")
                log_category = gr.Textbox(label="Category")
                log_phrase = gr.Textbox(label="Phrase id")
                flagged = gr.Checkbox(label="Flagged")
            with gr.Row():
                log_btn = gr.Button("Write event", variant="primary")
                refresh_log = gr.Button("Refresh")
            limit = gr.Slider(
                1, 500, value=DEFAULT_EVENT_LIMIT, step=1, label="Rows to show"
            )
            log_msg = gr.Textbox(label="Result", interactive=False)
            events = gr.Dataframe(
                headers=EVENT_HEADERS,
                label="log.jsonl (newest first)",
                interactive=False,
            )
            log_btn.click(
                _on_log_event,
                [kind, log_category, log_phrase, flagged, limit],
                [log_msg, events],
            )
            refresh_log.click(event_rows, limit, events)

        def _initial() -> tuple:
            return (
                status_text(),
                samples_report(),
                current_passage(),
                gr.Dropdown(choices=_sample_choices()),
                phrases_json(),
                gr.Dropdown(choices=_category_choices()),
                gr.Dropdown(choices=_synth_choices()),
                manifest_rows(),
                gr.Dropdown(choices=list(load_manifest())),
                event_rows(),
            )

        console.load(
            _initial,
            outputs=[
                status,
                samples_out,
                script_md,
                sample_pick,
                editor,
                qe_category,
                synth_pick,
                manifest,
                lib_pick,
                events,
            ],
        )
    return console


def main() -> None:
    """Launch the developer console, using ``data_dev_tools/`` by default."""
    logging.basicConfig(level=logging.INFO)
    # Keep dev test data out of the real data/ folder unless FV_DATA_DIR is set.
    os.environ.setdefault(DATA_DIR_ENV_VAR, str(DEV_TOOLS_DATA_DIR))
    serve.launch(build_console(), config.server.dev_port)


if __name__ == "__main__":
    main()
