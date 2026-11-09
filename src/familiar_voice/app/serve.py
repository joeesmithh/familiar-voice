"""Serve a Gradio app on the host, port, and protocol from ``config.yaml``.

Both the main app and the developer console launch through :func:`launch`, so
they share one ``server:`` section. With ``server.https: true`` a self-signed
certificate is created in ``certs/`` on first launch and reused afterwards.
Browsers show a warning for it once; accepting it is fine for a class demo.
HTTPS matters because browsers allow mic recording only over HTTPS or on
localhost.
"""

import datetime
import ipaddress
import logging
from pathlib import Path

import gradio as gr
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from familiar_voice.core.config import config, data_dir

logger = logging.getLogger(__name__)

CERT_DIR = Path("certs")  # git-ignored
CERT_VALID_DAYS = 3650


def ensure_cert(cert_dir: Path | None = None) -> tuple[Path, Path]:
    """Return a self-signed certificate and key, creating them if missing.

    Parameters
    ----------
    cert_dir : Path, optional
        Folder for ``cert.pem`` and ``key.pem``. Defaults to ``CERT_DIR``.

    Returns
    -------
    tuple[Path, Path]
        The certificate path and the private key path.
    """
    cert_dir = CERT_DIR if cert_dir is None else Path(cert_dir)
    cert_path, key_path = cert_dir / "cert.pem", cert_dir / "key.pem"
    if cert_path.is_file() and key_path.is_file():
        return cert_path, key_path

    cert_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Familiar Voice")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=CERT_VALID_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    logger.info("Created self-signed certificate in %s", cert_dir)
    return cert_path, key_path


def launch_kwargs(port: int) -> dict:
    """Build the ``gr.Blocks.launch`` keyword arguments for `port`.

    Parameters
    ----------
    port : int
        The port to listen on.

    Returns
    -------
    dict
        Host, port, allowed file paths, and SSL settings from ``config.server``.
    """
    server = config.server
    kwargs: dict = {
        "server_name": server.host,
        "server_port": port,
        # Let Gradio serve audio from the data folder, wherever FV_DATA_DIR points.
        "allowed_paths": [str(data_dir().resolve())],
    }
    if server.https:
        cert_path, key_path = ensure_cert()
        kwargs.update(
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
            # Gradio checks its own URL at startup; skip verifying the self-signed cert.
            ssl_verify=False,
        )
    return kwargs


def launch(blocks: gr.Blocks, port: int) -> None:
    """Serve `blocks` on `port` with the ``server:`` settings.

    Parameters
    ----------
    blocks : gr.Blocks
        The app to serve.
    port : int
        The port to listen on.
    """
    kwargs = launch_kwargs(port)
    scheme = "https" if config.server.https else "http"
    if config.server.host == "0.0.0.0":
        logger.info(
            "Serving on all interfaces. From other machines open %s://<PC IP>:%d",
            scheme,
            port,
        )
    blocks.launch(**kwargs)
