# `familiar_voice.core.log`

Records button presses, check-ins, and conversation events in the
`log.jsonl` interaction log and reads them back newest first.

## Purpose

The caregiver needs to see when the person being cared for asked for comfort
and what they heard. This module appends one JSON object per event to
`log.jsonl` and reads the file back for the caregiver's log table. It does not
display the table or decide when to log; the UI and scheduler call it.

## Key Components

- `log_event()` — appends one event with a timestamp and returns it.
- `read_events()` — returns logged events newest first, optionally capped by
  `limit`.
- `EVENT_KINDS` — the allowed event kinds: `button`, `checkin`,
  `conversation`, and `distress`.

## Usage

```python
from familiar_voice.core.log import log_event, read_events

log_event("button", category="worried", phrase_id="worried-1")
log_event("distress", flagged=True, text="I feel scared")

for event in read_events(limit=10):
    print(event["ts"], event["kind"], event["category"])
```

## Dependencies

- **Uses:** `familiar_voice.core.config` (for `log_path()`).
- **Used by:** nothing yet; the User tab, check-in scheduler, and caregiver
  log view depend on it.

## Design Notes

- JSON Lines (one object per line) lets each event be appended without
  rewriting the file, so a crash loses at most the line being written.
- Every event has the same core fields (`ts`, `kind`, `category`, `phrase_id`,
  `flagged`), so the log table has stable columns. Extra keyword arguments
  add fields but cannot overwrite these.
- `read_events()` skips malformed lines instead of raising. One corrupt line
  must never hide the rest of the caregiver's log.
- Newest-first order comes from file order, not timestamps. Events logged in
  the same second keep their true order.
- Timestamps include the local UTC offset, so the log stays unambiguous across
  daylight-saving changes.
