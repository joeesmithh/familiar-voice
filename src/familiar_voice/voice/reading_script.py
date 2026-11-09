"""Guided reading script for recording voice-cloning samples.

Improvised speech makes poor reference audio: it tends to be short, flat, and
phonetically narrow. These passages give the speaker something to read that
covers the sounds and intonation a cloner needs. Apart from the spoken consent
line, they come from standard, public-domain speech-recording material:

- The Rainbow Passage (Fairbanks, 1960) is built to contain every English
  phoneme.
- The Harvard sentences (IEEE, 1969) are phonetically balanced.
- The last passage adds questions, an exclamation, and spoken numbers so the
  clone also hears varied intonation.

One passage is recorded per sample. All five together run about 45–55 s,
inside the window set by ``MIN_TOTAL_SECONDS`` and ``MAX_TOTAL_SECONDS``.
"""

CONSENT_PASSAGE = (
    "My name is [your name]. This is my own voice, and I consent to these "
    "recordings being used to create a synthetic copy of it."
)

READING_SCRIPT: tuple[str, ...] = (
    CONSENT_PASSAGE,
    "When the sunlight strikes raindrops in the air, they act as a prism and "
    "form a rainbow. The rainbow is a division of white light into many "
    "beautiful colors.",
    "These take the shape of a long round arch, with its path high above, and "
    "its two ends apparently beyond the horizon. There is, according to "
    "legend, a boiling pot of gold at one end.",
    "The birch canoe slid on the smooth planks. Glue the sheet to the dark "
    "blue background. It's easy to tell the depth of a well. The juice of "
    "lemons makes fine punch.",
    "Did you remember to call Zoe on Thursday? Wow, that's great news! I'll "
    "meet you at seven thirty, just past the bridge near the old mill, okay?",
)

RECORDING_TIPS = """\
- **Quiet room:** no TV, music, fans, or echo. A room with soft furnishings is best.
- **Same microphone every time**, about 15–20 cm (a hand's width) from your mouth.
- **Speak in your normal conversational voice.** The clone copies tone and pace
  as well as timbre, so avoid a flat "reading aloud" delivery.
- **Natural pace.** Don't whisper, shout, or rush.
- **One passage per sample.** Pauses at the start and end are trimmed automatically.
- **Redo mistakes:** if you stumble, cough, or get background noise, record the
  passage again before saving.
- **Listen back** to each saved sample to check it is clear and not distorted.
"""


def passage_markdown(n_saved: int) -> str:
    """Return the passage to read next, as Markdown.

    Parameters
    ----------
    n_saved : int
        How many samples are already saved.

    Returns
    -------
    str
        A heading naming the passage number and the passage as a blockquote,
        or a done message once every passage has been recorded.
    """
    total = len(READING_SCRIPT)
    if n_saved >= total:
        return (
            f"**All {total} passages recorded.** Delete all samples to start "
            "over, or record extra natural speech if you want more."
        )
    index = max(n_saved, 0)
    heading = f"**Read this aloud (passage {index + 1} of {total}):**"
    if index == 0:
        heading += " This passage is your spoken consent."
    return f"{heading}\n\n> {READING_SCRIPT[index]}"
