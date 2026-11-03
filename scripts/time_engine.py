"""Time voice-cloning synthesis on this machine and record it in docs/spike.md.

Loads the engine, speaks the first N caregiver phrases in the cloned voice of
the samples in ``data/samples/``, and writes a results table between the
``<!-- timing:start -->`` and ``<!-- timing:end -->`` markers of
``docs/spike.md``. Generated WAVs go to ``data/spike/`` for listening.

Run from the project root after ``pip install -e ".[dev]"``::

    COQUI_TOS_AGREED=1 python scripts/time_engine.py --n 5
"""

import argparse
import logging
import os
import platform
import re
import time
from datetime import date
from pathlib import Path

import soundfile as sf

from familiar_voice.core.config import data_dir, samples_dir
from familiar_voice.core.phrases import load_phrases
from familiar_voice.voice.engine import DEFAULT_ENGINE, get_engine, synthesize
from familiar_voice.voice.preprocess import total_duration

SPIKE_DOC = Path(__file__).resolve().parents[1] / "docs" / "spike.md"
START_MARKER = "<!-- timing:start -->"
END_MARKER = "<!-- timing:end -->"


def parse_args() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=5, help="phrases to time")
    parser.add_argument("--engine", default=DEFAULT_ENGINE, help="engine name")
    parser.add_argument("--lang", default="en", help="language code")
    parser.add_argument(
        "--samples",
        type=Path,
        nargs="+",
        help="reference WAVs (default: data/samples/*.wav)",
    )
    parser.add_argument("--doc", type=Path, default=SPIKE_DOC, help="doc to update")
    return parser.parse_args()


def phrase_texts(n: int) -> list[str]:
    """Return the text of the first `n` phrases across all categories."""
    data = load_phrases()
    texts = [p["text"] for c in data["categories"] for p in c["phrases"]]
    return texts[:n]


def time_phrases(
    engine_name: str, texts: list[str], ref_wavs: list[Path], lang: str
) -> tuple[float, list[tuple[str, float, float]]]:
    """Return model load seconds and ``(text, synth_s, audio_s)`` per phrase."""
    engine = get_engine(engine_name)
    load_start = time.perf_counter()
    if hasattr(engine, "load"):
        engine.load()
    load_seconds = time.perf_counter() - load_start

    out_dir = data_dir() / "spike"
    rows = []
    for i, text in enumerate(texts, start=1):
        start = time.perf_counter()
        wav = synthesize(
            text, ref_wavs, lang, out_path=out_dir / f"{i}.wav", engine=engine
        )
        synth_seconds = time.perf_counter() - start
        audio_seconds = sf.info(wav).duration
        logging.info("%d/%d: %.1f s -> %s", i, len(texts), synth_seconds, wav)
        rows.append((text, synth_seconds, audio_seconds))
    return load_seconds, rows


def results_markdown(
    engine_name: str,
    ref_wavs: list[Path],
    load_seconds: float,
    rows: list[tuple[str, float, float]],
) -> str:
    """Format one timing run as a Markdown section."""
    lines = [
        f"### Run {date.today().isoformat()} — `{engine_name}`",
        "",
        f"- **Machine:** {platform.platform()}, {platform.processor() or 'CPU'}, "
        f"{os.cpu_count()} logical cores, Python {platform.python_version()}",
        f"- **Reference audio:** {len(ref_wavs)} file(s), "
        f"{total_duration(ref_wavs):.1f} s",
        f"- **Model load:** {load_seconds:.1f} s",
        "",
        "| # | Phrase | Synthesis (s) | Audio (s) | Real-time factor |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i, (text, synth, audio) in enumerate(rows, start=1):
        lines.append(
            f"| {i} | {text} | {synth:.1f} | {audio:.1f} | {synth / audio:.2f} |"
        )
    total_synth = sum(r[1] for r in rows)
    total_audio = sum(r[2] for r in rows)
    lines += [
        "",
        f"**Mean:** {total_synth / len(rows):.1f} s per phrase; "
        f"real-time factor {total_synth / total_audio:.2f} "
        "(synthesis time ÷ audio length; below 1 is faster than real time).",
    ]
    return "\n".join(lines)


def record(doc: Path, section: str) -> None:
    """Replace the text between the timing markers in `doc` with `section`."""
    text = doc.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(START_MARKER) + ".*?" + re.escape(END_MARKER), re.DOTALL
    )
    if not pattern.search(text):
        raise ValueError(f"{doc} is missing the {START_MARKER} / {END_MARKER} markers.")
    replacement = f"{START_MARKER}\n{section}\n{END_MARKER}"
    doc.write_text(pattern.sub(lambda _: replacement, text), encoding="utf-8")


def main() -> None:
    """Time the engine and record the results."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    ref_wavs = args.samples or sorted(samples_dir().glob("*.wav"))
    if not ref_wavs:
        raise SystemExit(f"No reference WAVs in {samples_dir()}; pass --samples.")
    texts = phrase_texts(args.n)

    load_seconds, rows = time_phrases(args.engine, texts, ref_wavs, args.lang)
    record(args.doc, results_markdown(args.engine, ref_wavs, load_seconds, rows))
    logging.info("Recorded results in %s", args.doc)


if __name__ == "__main__":
    main()
