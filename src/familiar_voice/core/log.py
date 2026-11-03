"""Append-only interaction log stored as JSON Lines in ``log.jsonl``.

Each line is one JSON object describing something that happened, such as a
button press or a scheduled check-in::

    {"ts": "2026-11-02T14:05:09-05:00", "kind": "button", "category": "worried",
     "phrase_id": "worried-1", "flagged": false}

The caregiver tab shows these events as a table, newest first. Lines that
cannot be parsed are skipped on read, so one corrupt line never hides the
rest of the log.
"""

import json
from datetime import datetime
from typing import Any

from familiar_voice.core.config import log_path

EVENT_KINDS = frozenset({"button", "checkin", "conversation", "distress"})

# Fields every event has. `extra` keyword arguments may not reuse these names.
RESERVED_FIELDS = frozenset({"ts", "kind", "category", "phrase_id", "flagged"})


def log_event(
    kind: str,
    category: str | None = None,
    phrase_id: str | None = None,
    flagged: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Append one event to the interaction log.

    Parameters
    ----------
    kind : str
        What happened: one of ``button``, ``checkin``, ``conversation``, or
        ``distress``.
    category : str or None, optional
        Id of the phrase category involved, if any.
    phrase_id : str or None, optional
        Id of the phrase that was played, if any.
    flagged : bool, optional
        True if the caregiver should look at this event (e.g. distress).
    **extra : Any
        Additional JSON-serializable fields, such as ``text`` for a
        conversation turn.

    Returns
    -------
    dict[str, Any]
        The event exactly as written to the log.

    Raises
    ------
    ValueError
        If `kind` is not a known event kind, or `extra` uses a reserved
        field name.
    """
    if kind not in EVENT_KINDS:
        raise ValueError(
            f"Unknown event kind {kind!r}; expected one of {sorted(EVENT_KINDS)}."
        )
    clashes = RESERVED_FIELDS & extra.keys()
    if clashes:
        raise ValueError(f"Extra fields use reserved names: {sorted(clashes)}.")

    event: dict[str, Any] = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "kind": kind,
        "category": category,
        "phrase_id": phrase_id,
        "flagged": flagged,
        **extra,
    }
    line = json.dumps(event, ensure_ascii=False)
    with log_path().open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")
    return event


def read_events(limit: int | None = None) -> list[dict[str, Any]]:
    """Read logged events, newest first.

    Blank lines, lines that are not valid JSON, and lines that are not JSON
    objects are skipped.

    Parameters
    ----------
    limit : int or None, optional
        Maximum number of events to return. ``None`` returns every event.

    Returns
    -------
    list[dict[str, Any]]
        Events in reverse order of logging. Empty if the log does not exist.

    Raises
    ------
    ValueError
        If `limit` is negative.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must not be negative.")

    path = log_path()
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as log_file:
        for line in log_file:
            event = _parse_line(line)
            if event is not None:
                events.append(event)

    # File order is append order, which is more reliable than sorting by
    # timestamp: events logged in the same second keep their true order.
    events.reverse()
    return events if limit is None else events[:limit]


def _parse_line(line: str) -> dict[str, Any] | None:
    """Return the event on one log line, or None if the line is unusable."""
    line = line.strip()
    if not line:
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None
