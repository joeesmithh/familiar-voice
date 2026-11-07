"""Batch-build the voice library: every phrase spoken in the caregiver's voice.

Voice cloning on a CPU takes seconds to minutes per phrase, so the app never
synthesizes while the person is waiting. Instead, the caregiver runs this
builder once after editing phrases or recording samples. It writes one WAV per
phrase to ``library/<category id>/<phrase id>.wav`` and records what it built
in ``library/manifest.json``::

    {
      "phrases": {
        "worried-1": {
          "category": "worried",
          "text": "It's okay. You are safe.",
          "text_hash": "3b0c...",
          "path": "worried/worried-1.wav"
        }
      }
    }

Paths in the manifest are relative to the library folder. On later runs a
phrase is skipped when its text hash and path match the manifest and its WAV
still exists, so only new or edited phrases are rebuilt. WAVs of phrases that
were deleted are removed.

Run it from the command line with::

    python -m familiar_voice.voice.build_library [--force]
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from familiar_voice.core.config import library_dir, samples_dir
from familiar_voice.core.phrases import load_phrases
from familiar_voice.voice.engine import Engine, synthesize

logger = logging.getLogger(__name__)

MANIFEST_FILE = "manifest.json"
SAMPLE_GLOB = "*.wav"

ProgressCallback = Callable[[int, int, str], None]
"""Called as ``progress(done, total, text)`` after each phrase is handled."""


class NoSamplesError(FileNotFoundError):
    """Raised when the library is built before any voice samples exist."""


class ManifestEntry(TypedDict):
    """What the manifest records about one built phrase.

    Attributes
    ----------
    category : str
        Id of the phrase's category.
    text : str
        The phrase text that was spoken.
    text_hash : str
        SHA-256 hex digest of `text`, used to detect edits.
    path : str
        WAV location relative to the library folder, with ``/`` separators.
    """

    category: str
    text: str
    text_hash: str
    path: str


@dataclass
class BuildSummary:
    """What one `build_library` run did.

    Attributes
    ----------
    built : list[str]
        Ids of phrases whose WAV was (re)generated.
    skipped : list[str]
        Ids of phrases whose existing WAV was kept.
    removed : list[str]
        Ids of deleted phrases whose WAV was removed.
    seconds : float
        Wall-clock time of the run.
    """

    built: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    seconds: float = 0.0

    def __str__(self) -> str:
        """Return a one-line summary, e.g. for the CLI or the Caregiver tab."""
        return (
            f"Built {len(self.built)}, skipped {len(self.skipped)}, "
            f"removed {len(self.removed)} in {self.seconds:.1f} s."
        )


def text_hash(text: str) -> str:
    """Return the SHA-256 hex digest of phrase text.

    Parameters
    ----------
    text : str
        Phrase text.

    Returns
    -------
    str
        64-character lowercase hex digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_path() -> Path:
    """Return the path of the library manifest.

    Returns
    -------
    Path
        ``<data root>/library/manifest.json``. The file itself is not created.
    """
    return library_dir() / MANIFEST_FILE


def load_manifest() -> dict[str, ManifestEntry]:
    """Read the library manifest.

    Returns
    -------
    dict[str, ManifestEntry]
        Phrase id → manifest entry. Empty if the manifest is missing or
        unreadable, which makes the next build regenerate everything.
    """
    path = manifest_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        phrases = data["phrases"]
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Ignoring unreadable library manifest: %s", path)
        return {}
    return phrases if isinstance(phrases, dict) else {}


def find_samples() -> list[Path]:
    """Return the caregiver's preprocessed voice samples in name order.

    Returns
    -------
    list[Path]
        Every ``*.wav`` file in the samples folder.
    """
    return sorted(samples_dir().glob(SAMPLE_GLOB))


def build_library(
    progress: ProgressCallback | None = None,
    force: bool = False,
    engine: str | Engine | None = None,
    lang: str = "en",
) -> BuildSummary:
    """Generate a WAV for every phrase that is new or has changed.

    The manifest is saved after each phrase, so an interrupted build keeps
    the work it finished and resumes where it stopped.

    Parameters
    ----------
    progress : ProgressCallback or None, optional
        Called as ``progress(done, total, text)`` after each phrase, built or
        skipped.
    force : bool, optional
        Rebuild every phrase, e.g. after the caregiver re-records samples.
    engine : str, Engine, or None, optional
        Passed to `synthesize`; ``None`` uses ``FV_ENGINE``.
    lang : str, optional
        Language code the phrases are written in.

    Returns
    -------
    BuildSummary
        Which phrases were built, skipped, and removed.

    Raises
    ------
    NoSamplesError
        If the samples folder has no WAV files. Nothing is changed.
    ValueError
        If the phrase file is invalid.
    """
    start = time.perf_counter()
    samples = find_samples()
    if not samples:
        raise NoSamplesError(
            f"No voice samples found in {samples_dir()}. Record at least one "
            "sample in the Caregiver tab before building the voice library."
        )

    phrases = [
        (category["id"], phrase)
        for category in load_phrases()["categories"]
        for phrase in category["phrases"]
    ]
    root = library_dir()
    manifest = load_manifest()
    summary = BuildSummary()

    current_ids = {phrase["id"] for _, phrase in phrases}
    for phrase_id in [pid for pid in manifest if pid not in current_ids]:
        _remove_wav(root, manifest.pop(phrase_id))
        summary.removed.append(phrase_id)
    if summary.removed:
        _save_manifest(manifest)

    total = len(phrases)
    for done, (category_id, phrase) in enumerate(phrases, start=1):
        entry: ManifestEntry = {
            "category": category_id,
            "text": phrase["text"],
            "text_hash": text_hash(phrase["text"]),
            "path": f"{category_id}/{phrase['id']}.wav",
        }
        old = manifest.get(phrase["id"])
        if not force and _is_up_to_date(root, old, entry):
            summary.skipped.append(phrase["id"])
        else:
            logger.info("Building %s: %s", phrase["id"], phrase["text"])
            _build_one(root, entry, samples, lang, engine)
            if old is not None and old.get("path") != entry["path"]:
                _remove_wav(root, old)  # phrase moved to another category
            manifest[phrase["id"]] = entry
            _save_manifest(manifest)
            summary.built.append(phrase["id"])
        if progress is not None:
            progress(done, total, phrase["text"])

    _remove_empty_dirs(root)
    summary.seconds = time.perf_counter() - start
    return summary


def _is_up_to_date(root: Path, old: ManifestEntry | None, new: ManifestEntry) -> bool:
    """Return True if `old` already describes `new` and its WAV exists."""
    return (
        old is not None
        and old.get("text_hash") == new["text_hash"]
        and old.get("path") == new["path"]
        and (root / new["path"]).is_file()
    )


def _build_one(
    root: Path,
    entry: ManifestEntry,
    samples: Sequence[Path],
    lang: str,
    engine: str | Engine | None,
) -> None:
    """Synthesize one phrase, swapping the WAV in only once it is complete."""
    final = root / entry["path"]
    # Keep the .wav suffix so engines can infer the format from the name.
    partial = final.with_name(final.stem + ".partial.wav")
    try:
        synthesize(entry["text"], samples, lang=lang, out_path=partial, engine=engine)
        partial.replace(final)
    finally:
        partial.unlink(missing_ok=True)


def _remove_wav(root: Path, entry: ManifestEntry) -> None:
    """Delete the WAV a manifest entry points at, if it is there."""
    path = entry.get("path")
    if path:
        (root / path).unlink(missing_ok=True)


def _remove_empty_dirs(root: Path) -> None:
    """Delete category folders left empty after removing WAVs."""
    for child in root.iterdir():
        if child.is_dir() and not any(child.iterdir()):
            child.rmdir()


def _save_manifest(manifest: dict[str, ManifestEntry]) -> None:
    """Write the manifest via a temporary file so it is never half-written."""
    path = manifest_path()
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps({"phrases": manifest}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def _print_progress(done: int, total: int, text: str) -> None:
    """Print one CLI progress line."""
    print(f"[{done}/{total}] {text}", flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the library builder from the command line.

    Parameters
    ----------
    argv : Sequence[str] or None, optional
        Command-line arguments; ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        Process exit code: 0 on success, 1 if there are no samples, the
        phrase file is invalid, or the configured device is unusable.
    """
    parser = argparse.ArgumentParser(
        prog="python -m familiar_voice.voice.build_library",
        description="Generate every reassurance phrase in the caregiver's voice.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rebuild every phrase, e.g. after re-recording voice samples",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        summary = build_library(progress=_print_progress, force=args.force)
    except (NoSamplesError, ValueError, RuntimeError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
