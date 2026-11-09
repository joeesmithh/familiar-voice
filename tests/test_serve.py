from pathlib import Path

from cryptography import x509

from familiar_voice.app import serve
from familiar_voice.core.config import ServerConfig


def test_ensure_cert_creates_valid_files_once(tmp_path: Path) -> None:
    cert_path, key_path = serve.ensure_cert(tmp_path / "certs")
    cert_bytes = cert_path.read_bytes()

    assert key_path.is_file()
    cert = x509.load_pem_x509_certificate(cert_bytes)
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    assert "localhost" in names.value.get_values_for_type(x509.DNSName)

    # A second call reuses the existing files instead of making new ones.
    assert serve.ensure_cert(tmp_path / "certs") == (cert_path, key_path)
    assert cert_path.read_bytes() == cert_bytes


def _use_server(monkeypatch, **settings) -> None:
    cfg = serve.config.__class__(server=ServerConfig(**settings))
    monkeypatch.setattr(serve, "config", cfg)


def test_launch_kwargs_http(data_dir, monkeypatch) -> None:
    _use_server(monkeypatch, host="0.0.0.0", https=False)

    kwargs = serve.launch_kwargs(9000)

    assert kwargs["server_name"] == "0.0.0.0"
    assert kwargs["server_port"] == 9000
    assert kwargs["allowed_paths"] == [str(data_dir.resolve())]
    assert "ssl_certfile" not in kwargs


def test_launch_kwargs_https(data_dir, tmp_path, monkeypatch) -> None:
    _use_server(monkeypatch, https=True)
    monkeypatch.setattr(serve, "CERT_DIR", tmp_path / "certs")

    kwargs = serve.launch_kwargs(9000)

    assert Path(kwargs["ssl_certfile"]).is_file()
    assert Path(kwargs["ssl_keyfile"]).is_file()
    assert kwargs["ssl_verify"] is False


def test_launch_passes_kwargs_to_blocks(data_dir, monkeypatch) -> None:
    _use_server(monkeypatch, https=False)
    received = {}

    class StubBlocks:
        def launch(self, **kwargs) -> None:
            received.update(kwargs)

    serve.launch(StubBlocks(), 9001)

    assert received["server_port"] == 9001
