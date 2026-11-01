"""Launch the Familiar Voice Gradio app."""

import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Start the app.

    The Gradio UI is added in roadmap feature F07; until then this only reports
    that the UI is not available yet.
    """
    logging.basicConfig(level=logging.INFO)
    logger.info("Familiar Voice UI is not implemented yet (see roadmap F07).")
