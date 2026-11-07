"""User tab: the default view for the person being cared for.

The tab will hold a few large, high-contrast buttons that play a reassurance
phrase in the caregiver's voice. For now it only lays out an empty tab so the
app shell can be built and launched.
"""

import gradio as gr

TAB_LABEL = "User"


def build_user_tab() -> gr.Tab:
    """Add the User tab to the enclosing ``gr.Blocks``.

    Must be called inside a ``with gr.Blocks():`` context.

    Returns
    -------
    gr.Tab
        The tab component, so callers can select or wire it.
    """
    with gr.Tab(TAB_LABEL, id="user") as tab:
        gr.Markdown("Your Voice Helper buttons will appear here.")
    return tab
