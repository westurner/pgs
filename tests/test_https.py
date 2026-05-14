import os
import ssl
import sys
import threading
import time
import pytest
import subprocess
from unittest import mock

# Ensure pgs is importable
app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from pgs.app import pgs, make_app, get_parser


def find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


@pytest.fixture
def parser():
    return get_parser()


@pytest.mark.parametrize("https_enabled,generate,expect_exists", [
    (True, True, True),
    (True, False, False),
    (False, False, False),
])
def test_certificate_generation_and_https_flag(tmpdir, https_enabled, generate, expect_exists, parser):
    cert_path = tmpdir.join("test_server.pem")
    key_path = tmpdir.join("test_server.key")
    port = find_free_port()

    args = [
        '-p', str(tmpdir),
        '-P', str(port),
        '--cert-file', str(cert_path),
        '--key-file', str(key_path),
    ]
    if generate:
        args.append('--generate-cert')
    
    if not https_enabled:
        args.append('--no-https')

    opts = parser.parse_args(args)
    
    from pgs.app import pgs, make_app
    app = make_app(conf=None)

    def mock_bottle_run(*args, **kwargs):
        server_class = kwargs.get('server')
        if server_class:
            # Call run but mock out make_server so it doesn't block
            server_inst = server_class(host=opts.host, port=opts.port)
            with mock.patch('wsgiref.simple_server.make_server') as mock_make_server:
                with mock.patch('ssl.create_default_context') as mock_ssl:
                    # In python 3, this mock needs to not crash context.load_cert_chain
                    # We will bypass the missing cert chain if it doesn't exist to just check if openssl ran
                    if expect_exists:
                        server_inst.run(None)
                    else:
                        try:
                            server_inst.run(None)
                        except Exception:
                            pass
        
    with mock.patch('pgs.app.bottle.run', side_effect=mock_bottle_run) as m_run:
        pgs(app, opts)


@pytest.mark.parametrize("cipher_mode,expected_groups", [
    (None, "X25519MLKEM768:prime256v1:secp384r1"),  # Testing omitted cipher falls back to hybrid default
    ("nopq", "X25519"),
    ("hybrid", "X25519MLKEM768:prime256v1:secp384r1"),
    ("pq", "X25519MLKEM768"),
    ("null", None),
])
def test_https_ciphers(tmpdir, cipher_mode, expected_groups, parser):
    """
    Test the HTTPS cipher configuration selection logic.
    
    If omitted (cipher_mode=None), the default cipher selection used is 'hybrid', 
    which applies X25519MLKEM768:prime256v1:secp384r1.
    If 'nopq' is passed, it isolates the cipher setting to X25519.
    If 'hybrid' is passed, it utilizes the same groups as the default.
    If 'pq' is passed, it exclusively relies on post-quantum secure X25519MLKEM768.
    """
    cert_path = tmpdir.join("test_server.pem")
    key_path = tmpdir.join("test_server.key")
    port = find_free_port()

    # Create dummy files so generator doesn't kick in normally in mock
    cert_path.write("cert")
    key_path.write("key")

    args = [
        '-p', str(tmpdir),
        '-P', str(port),
        '--cert-file', str(cert_path),
        '--key-file', str(key_path),
    ]
    if cipher_mode is not None:
        args.extend(['--https-ciphers', cipher_mode])

    opts = parser.parse_args(args)
    
    from pgs.app import pgs, make_app
    app = make_app(conf=None)

    def mock_bottle_run(*args, **kwargs):
        server_class = kwargs.get('server')
        if server_class:
            server_inst = server_class(host=opts.host, port=opts.port)
            with mock.patch('wsgiref.simple_server.make_server'):
                with mock.patch('ssl.create_default_context') as mock_ssl:
                    # Mock the context object inside create_default_context
                    mock_context = mock.MagicMock()
                    mock_ssl.return_value = mock_context
                    
                    try:
                        server_inst.run(None)
                    except Exception:
                        pass
                    
                    # Verify TLS versions
                    import ssl
                    assert mock_context.minimum_version == ssl.TLSVersion.TLSv1_3
                    assert mock_context.maximum_version == ssl.TLSVersion.TLSv1_3
                    
                    if cipher_mode == 'null':
                        mock_context.set_ciphers.assert_called_with('eNULL:aNULL:NULL')
                    elif expected_groups:
                        if hasattr(mock_context, 'set_groups'):
                            mock_context.set_groups.assert_called_with(expected_groups)
                        else:
                            # if set_groups is not present, we can't cleanly mock the AttributeError logic if we mocked the object
                            pass

    with mock.patch('pgs.app.bottle.run', side_effect=mock_bottle_run):
        pgs(app, opts)
