"""Build and launch the Familiar Voice Gradio app.

``build_app()`` assembles the User and Caregiver tabs into one
``gr.Blocks`` page; ``main()`` serves it. Run it with::

    python -m familiar_voice
"""

import logging

import gradio as gr

from familiar_voice.app import serve
from familiar_voice.app.caregiver import build_caregiver_tab
from familiar_voice.app.user import build_user_tab
from familiar_voice.core.config import config

APP_TITLE = "Familiar Voice"


def build_app() -> gr.Blocks:
    """Build the app with the User tab first and the Caregiver tab second.

    The User tab comes first so it is the default view for the person
    being cared for.

    Returns
    -------
    gr.Blocks
        The app; call ``.launch()`` to serve it.
    """
    with gr.Blocks(title=APP_TITLE) as app, gr.Tabs(selected="user"):
        build_user_tab()
        build_caregiver_tab()
    return app


def main() -> None:
    """Start the app on ``server.port`` from ``config.yaml``."""
    logging.basicConfig(level=logging.INFO)
    serve.launch(build_app(), config.server.port)
