"""Choose which pre-built phrase WAV to play for a category.

When the person being cared for taps a button, the app plays one phrase from
that category in the caregiver's voice. :func:`pick` chooses at random among
the phrases the library builder has finished, and never plays the same phrase
twice in a row when the category has two or more to choose from. Hearing the
exact same sentence again straight away can feel robotic instead of
comforting.

Only phrases listed in ``library/manifest.json`` whose WAV is on disk are
candidates, so a half-finished or interrupted build is still safe to play
from. Pass a seeded :class:`random.Random` to :class:`Picker` for repeatable
choices in tests.
"""

import random
from pathlib import Path

from familiar_voice.core.config import library_dir
from familiar_voice.voice.build_library import load_manifest


class Picker:
    """Random phrase chooser that remembers the last pick per category.

    Parameters
    ----------
    rng : random.Random or None, optional
        Source of randomness. Pass ``random.Random(seed)`` for repeatable
        picks; ``None`` uses a fresh unseeded generator.
    """

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._last: dict[str, str] = {}

    def candidates(self, category: str) -> list[tuple[str, Path]]:
        """Return the playable phrases of a category.

        Parameters
        ----------
        category : str
            Category id, e.g. ``"worried"``.

        Returns
        -------
        list[tuple[str, Path]]
            ``(phrase_id, wav_path)`` for every manifest entry in `category`
            whose WAV exists, sorted by phrase id so a seeded generator gives
            the same picks on every run.
        """
        root = library_dir().resolve()
        found = []
        for phrase_id, entry in load_manifest().items():
            if not isinstance(entry, dict) or entry.get("category") != category:
                continue
            rel = entry.get("path")
            if not isinstance(rel, str) or not rel:
                continue
            path = (root / rel).resolve()
            # Ignore entries that point outside the library folder.
            if path.is_relative_to(root) and path.is_file():
                found.append((phrase_id, path))
        return sorted(found)

    def pick(self, category: str) -> tuple[str, Path] | None:
        """Choose a random phrase WAV, avoiding the previous pick.

        Parameters
        ----------
        category : str
            Category id, e.g. ``"worried"``.

        Returns
        -------
        tuple[str, Path] or None
            ``(phrase_id, wav_path)`` of the chosen phrase, or ``None`` if the
            category has no built audio.
        """
        options = self.candidates(category)
        if not options:
            return None
        last = self._last.get(category)
        if len(options) > 1:
            options = [option for option in options if option[0] != last]
        choice = self._rng.choice(options)
        self._last[category] = choice[0]
        return choice


_default_picker = Picker()


def pick(category: str) -> tuple[str, Path] | None:
    """Choose a random phrase WAV for a category using the shared picker.

    The app shares one picker, so "no immediate repeat" holds across every
    button press in the running app.

    Parameters
    ----------
    category : str
        Category id, e.g. ``"worried"``.

    Returns
    -------
    tuple[str, Path] or None
        ``(phrase_id, wav_path)`` of the chosen phrase, or ``None`` if the
        category has no built audio.
    """
    return _default_picker.pick(category)
