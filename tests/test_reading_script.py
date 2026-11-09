from familiar_voice.voice.preprocess import MAX_TOTAL_SECONDS, MIN_TOTAL_SECONDS
from familiar_voice.voice.reading_script import (
    CONSENT_PASSAGE,
    READING_SCRIPT,
    passage_markdown,
)

WORDS_PER_SECOND = 2.5  # typical natural reading pace


def test_first_passage_is_consent():
    assert READING_SCRIPT[0] == CONSENT_PASSAGE
    text = passage_markdown(0)
    assert "passage 1 of 5" in text
    assert "consent" in text
    assert CONSENT_PASSAGE in text


def test_passage_markdown_advances():
    assert READING_SCRIPT[4] in passage_markdown(4)
    assert "passage 5 of 5" in passage_markdown(4)


def test_passage_markdown_when_done():
    assert "All 5 passages recorded" in passage_markdown(5)
    assert "All 5 passages recorded" in passage_markdown(9)


def test_negative_count_starts_at_first_passage():
    assert "passage 1 of 5" in passage_markdown(-1)


def test_script_length_fits_cloning_window():
    words = sum(len(p.split()) for p in READING_SCRIPT)
    seconds = words / WORDS_PER_SECOND
    assert MIN_TOTAL_SECONDS < seconds < MAX_TOTAL_SECONDS
