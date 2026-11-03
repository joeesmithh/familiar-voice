import json
from datetime import datetime
from pathlib import Path

import pytest

from familiar_voice.core import log

# --- Writing ---


def test_log_event_appends_one_json_line(data_dir: Path) -> None:
    event = log.log_event("button", category="worried", phrase_id="worried-1")

    lines = (data_dir / "log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == event
    assert event["kind"] == "button"
    assert event["category"] == "worried"
    assert event["phrase_id"] == "worried-1"
    assert event["flagged"] is False


def test_log_event_timestamp_is_iso8601_with_timezone(data_dir: Path) -> None:
    event = log.log_event("checkin")

    parsed = datetime.fromisoformat(event["ts"])
    assert parsed.tzinfo is not None


def test_log_event_stores_extra_fields(data_dir: Path) -> None:
    event = log.log_event("distress", flagged=True, text="I'm scared")

    assert log.read_events() == [event]
    assert event["text"] == "I'm scared"
    assert event["flagged"] is True


def test_log_event_rejects_unknown_kind(data_dir: Path) -> None:
    with pytest.raises(ValueError, match="Unknown event kind"):
        log.log_event("explosion")
    assert not (data_dir / "log.jsonl").exists()


def test_log_event_rejects_reserved_extra_field(data_dir: Path) -> None:
    with pytest.raises(ValueError, match="reserved"):
        log.log_event("button", ts="yesterday")


# --- Reading ---


def test_read_events_returns_empty_list_when_log_missing(data_dir: Path) -> None:
    assert log.read_events() == []


def test_read_events_returns_newest_first(data_dir: Path) -> None:
    for category in ("worried", "lonely", "routine"):
        log.log_event("button", category=category)

    categories = [event["category"] for event in log.read_events()]
    assert categories == ["routine", "lonely", "worried"]


def test_read_events_limit_keeps_newest(data_dir: Path) -> None:
    for number in range(5):
        log.log_event("button", phrase_id=f"worried-{number}")

    events = log.read_events(limit=2)
    assert [event["phrase_id"] for event in events] == ["worried-4", "worried-3"]
    assert log.read_events(limit=0) == []
    assert len(log.read_events(limit=99)) == 5


def test_read_events_rejects_negative_limit(data_dir: Path) -> None:
    with pytest.raises(ValueError):
        log.read_events(limit=-1)


def test_read_events_skips_malformed_lines(data_dir: Path) -> None:
    log.log_event("button", category="worried")
    with (data_dir / "log.jsonl").open("a", encoding="utf-8") as log_file:
        log_file.write("{not json\n")
        log_file.write("\n")
        log_file.write('["a list, not an object"]\n')
        log_file.write('{"ts": "2026-11-02T10:00:00+00:00", "kind": "checkin"')
        log_file.write("\n")
    log.log_event("button", category="lonely")

    categories = [event["category"] for event in log.read_events()]
    assert categories == ["lonely", "worried"]
