"""Caregiver tab: set up voice samples, phrases, check-ins, and view the log.

For now it only lays out an empty tab so the app shell can be built and
launched; the setup tools are added in later features.
"""

import gradio as gr

TAB_LABEL = "Caregiver"


def build_caregiver_tab() -> gr.Tab:
    """Add the Caregiver tab to the enclosing ``gr.Blocks``.

    Must be called inside a ``with gr.Blocks():`` context.

    Returns
    -------
    gr.Tab
        The tab component, so callers can select or wire it.
    """
    with gr.Tab(TAB_LABEL, id="caregiver") as tab:
        gr.Markdown("Caregiver setup tools will appear here.")
    return tab
