import gradio as gr

from familiar_voice.app import main as app_main
from familiar_voice.app.caregiver import TAB_LABEL as CAREGIVER_LABEL
from familiar_voice.app.user import TAB_LABEL as USER_LABEL


def _tab_labels(app: gr.Blocks) -> list[str]:
    return [b.label for b in app.blocks.values() if isinstance(b, gr.Tab)]


def test_build_app_constructs(data_dir):
    app = app_main.build_app()
    assert isinstance(app, gr.Blocks)


def test_user_tab_comes_first(data_dir):
    assert _tab_labels(app_main.build_app()) == [USER_LABEL, CAREGIVER_LABEL]


def test_main_launches_app_on_configured_port(monkeypatch):
    calls = []
    monkeypatch.setattr(app_main, "build_app", lambda: "app")
    monkeypatch.setattr(
        app_main.serve, "launch", lambda app, port: calls.append((app, port))
    )
    app_main.main()
    assert calls == [("app", app_main.config.server.port)]
