
import io
import os
import pytest
import urllib.parse
from unittest.mock import MagicMock, patch

from pgs.app import (
    RepositoryFS,
    DirectoryRepositoryFS,
    SubprocessGitRepositoryFS,
    DulwichGitRepositoryFS,
    Libgit2GitRepositoryFS,
    sanitize_path,
)
from tests.test_pgs import GIT_REPO_PATH, TEST_WWW_DIR

# --- 1. Test Base Interface using mocks ---


def test_interface_raises_not_implemented():
    fs = RepositoryFS()

    with pytest.raises(NotImplementedError):
        fs.exists("/path")
    with pytest.raises(NotImplementedError):
        fs.isdir("/path")
    with pytest.raises(NotImplementedError):
        fs.isfile("/path")
    with pytest.raises(NotImplementedError):
        fs.getinfo("/path")
    with pytest.raises(NotImplementedError):
        fs.listdir("/path")
    with pytest.raises(NotImplementedError):
        next(fs.listdirinfo("/path"))
    with pytest.raises(NotImplementedError):
        fs.get_fileobj("/path")
    with pytest.raises(NotImplementedError):
        fs.getsyspath("/path")


def test_interface_mocking():
    # Demonstrating how the interface is mocked out by dependents
    mock_fs = MagicMock(spec=RepositoryFS)
    mock_fs.exists.return_value = True
    mock_fs.isdir.return_value = False
    mock_fs.isfile.return_value = True
    mock_fs.getinfo.return_value = {"size": 100}

    assert mock_fs.exists("/index.html") is True
    assert mock_fs.isdir("/index.html") is False
    assert mock_fs.isfile("/index.html") is True
    assert mock_fs.getinfo("/index.html")["size"] == 100
    mock_fs.exists.assert_called_once_with("/index.html")


# --- 2. Parametrized Implementation Tests ---


@pytest.fixture
def conf_dir():
    return {"pgs.root_path": TEST_WWW_DIR}


@pytest.fixture
def conf_subprocess_git():
    return {"pgs.git_repo_path": GIT_REPO_PATH, "pgs.git_repo_rev": "HEAD"}


@pytest.fixture
def conf_dulwich_git():
    return {"pgs.git_repo_path": GIT_REPO_PATH, "pgs.git_repo_rev": b"HEAD"}


@pytest.fixture
def conf_libgit2_git():
    return {"pgs.git_repo_path": GIT_REPO_PATH, "pgs.git_repo_rev": "HEAD"}


@pytest.mark.parametrize(
    "fs_class_name, conf_fixture",
    [
        ("DirectoryRepositoryFS", "conf_dir"),
        ("SubprocessGitRepositoryFS", "conf_subprocess_git"),
        ("DulwichGitRepositoryFS", "conf_dulwich_git"),
        ("Libgit2GitRepositoryFS", "conf_libgit2_git"),
    ],
)
def test_repository_implementations_exist(fs_class_name, conf_fixture, request):
    conf = request.getfixturevalue(conf_fixture)
    cls = globals()[fs_class_name]

    if fs_class_name == "DulwichGitRepositoryFS":
        fs = cls(conf["pgs.git_repo_path"])
        fs.repo_rev = conf["pgs.git_repo_rev"]
    elif fs_class_name == "Libgit2GitRepositoryFS":
        try:
            import pygit2
        except ImportError:
            pytest.skip("pygit2 not installed")
        fs = cls(conf["pgs.git_repo_path"])
        fs.repo_rev = conf["pgs.git_repo_rev"]
    else:
        fs = cls(conf)

    assert isinstance(fs, RepositoryFS)

    try:
        # At least root or some known path should exist
        result = fs.exists("") or fs.exists("/")
        assert isinstance(result, bool)
    except KeyError:  # dulwich handles HEAD as a commit specifically or ref
        pytest.skip("Skipping git tree resolve bounds check for headless tests")


# --- 3. Implementation Specific Tests ---


def test_directory_fs_specifics(conf_dir):
    fs = DirectoryRepositoryFS(conf_dir)
    assert fs.root_path == TEST_WWW_DIR
    syspath = fs.getsyspath("index.html")
    assert syspath.endswith("index.html")


@patch("subprocess.call")
def test_subprocess_git_specifics(mock_call, conf_subprocess_git):
    mock_call.return_value = 0
    fs = SubprocessGitRepositoryFS(conf_subprocess_git)
    assert fs.exists("some_file.txt") is True
    mock_call.assert_called_once()


def test_dulwich_git_specifics(conf_dulwich_git):
    fs = DulwichGitRepositoryFS(conf_dulwich_git["pgs.git_repo_path"])
    assert fs.repo_path == conf_dulwich_git["pgs.git_repo_path"]
    assert hasattr(fs, "repo")


def test_libgit2_git_specifics(conf_libgit2_git):
    try:
        import pygit2
    except ImportError:
        pytest.skip("pygit2 not installed")
    fs = Libgit2GitRepositoryFS(conf_libgit2_git["pgs.git_repo_path"])
    assert fs.repo_path == conf_libgit2_git["pgs.git_repo_path"]
    assert hasattr(fs, "repo")


def test_sanitize_path_exception():
    from pgs.app import sanitize_path
    import pytest

    with pytest.raises(ValueError):
        sanitize_path("/../something")
        
    with pytest.raises(ValueError):
        sanitize_path("../something")

    with pytest.raises(ValueError):
        sanitize_path("a/../../something")

@pytest.mark.parametrize(
    "path, expected",
    [
        # Hidden files/directories
        ("/.env", True),
        ("/a/b/.git/config", True),
        (".hidden_file.txt", True),
        ("path/to/.folder/file", True),
        (".DS_Store", True),
        
        # Valid structural tokens
        (".", False),
        ("..", False),
        ("./file.txt", False),
        ("../file.txt", False),
        ("a/./b/../c", False),

        # Normal files
        ("index.html", False),
        ("/css/style.main.css", False),
        ("a.b.c.txt", False),
        ("", False),
        ("/", False),
    ]
)
def test_is_hidden_path(path, expected):
    from pgs.app import is_hidden_path
    
    assert is_hidden_path(path) == expected


def test_hidden_files_integration():
    from pgs.app import serve_static_files, HTTPError
    from unittest.mock import patch, MagicMock

    with patch("pgs.app.request") as mock_req:
        mock_req.app = MagicMock()
        mock_req.app.config = {'pgs.block_hidden_files': True}
        from pgs.app import DirectoryRepositoryFS
        mock_fs = MagicMock(spec=DirectoryRepositoryFS)
        mock_fs.exists.return_value = False
        mock_req.app.config['pgs.FS'] = mock_fs
        mock_req.app.config['pgs.root_path'] = '.'
        
        result = serve_static_files("/.env", block_hidden_files=True)
        assert isinstance(result, HTTPError)
        assert result.status_code == 403

        result = serve_static_files("/a/b/.git/config", block_hidden_files=True)
        assert isinstance(result, HTTPError)
        assert result.status_code == 403
        
        # When block_hidden_files=False, it should not return 403 for hidden files
        # It will instead proceed and return 404 (since mock FS is empty in this test)
        result_allowed = serve_static_files("/.env", block_hidden_files=False)
        assert isinstance(result_allowed, HTTPError)
        assert result_allowed.status_code == 404

# CWE-22: Path Traversal
@pytest.mark.parametrize(
    "payload",
    [
        "../etc/passwd",
        "../../etc/passwd",
        "../../../../../../../../../../../../../etc/passwd",
        "/../../../../../../../../../../../../../etc/passwd",
        "//../../../../../../../../../../../../../etc/passwd",
        "/./../../../../../../../../../../../../../etc/passwd",
        "/%2e%2e/%2e%2e/etc/passwd", # URL encoded
        "/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd", # URL encoded
        "a/../../something",
        "..%2f..%2fetc%2fpasswd",
        "/dir/../../../../etc/passwd",
        "..\\..\\windows\\win.ini", # Windows traversal
        "/..\\..\\windows\\win.ini",
    ]
)
def test_directory_traversal_payloads(payload):
    decoded_payload = urllib.parse.unquote(payload)
    
    with pytest.raises(ValueError, match="Path traversal detected"):
        sanitize_path(decoded_payload)


def test_pgs_app_configurations():
    from pgs.app import pgs, make_app
    from unittest.mock import patch

    with patch("pgs.app.bottle.run") as mock_run:
        app = make_app()
        Config = type(
            "Config",
            (),
            {
                "root_path": ".",
                "git_repo_path": None,
                "host": "localhost",
                "port": 8080,
                "debug": True,
                "reloader": False,
            },
        )
        pgs(app, Config())
        mock_run.assert_called_once()
        Config2 = type(
            "Config",
            (),
            {
                "root_path": None,
                "git_repo_path": ".",
                "git_repo_rev": "develop",
                "host": "localhost",
                "port": 8080,
                "debug": True,
                "reloader": False,
            },
        )
        pgs(app, Config2())


def test_main_cli_options():
    from pgs.app import main
    import sys
    from unittest.mock import patch

    with patch("sys.argv", ["pgs", "-p", ".", "-q"]), patch("pgs.app.pgs"):
        main()
    with patch("sys.argv", ["pgs", "-p", ".", "-v"]), patch("pgs.app.pgs"):
        main()
    with patch("sys.argv", ["pgs", "-t"]), patch("unittest.main"):
        main()


def test_serve_dirlist_and_static_files():
    from pgs.app import explicitly_serve_dirlist, serve_static_files
    from unittest.mock import patch

    with patch("pgs.app.serve_dirlist") as mock_serve:
        mock_serve.return_value = "ok"
        assert explicitly_serve_dirlist("/test@@") == "ok"
    with patch("pgs.app.request") as mock_req:
        mock_req.app = False
        assert serve_static_files("") is None


def test_dulwich_git_fs_fallbacks():
    from pgs.app import DulwichGitRepositoryFS
    from unittest.mock import MagicMock, patch

    fs = DulwichGitRepositoryFS(".")
    fs._walk_tree = MagicMock(return_value=None)
    fs.repo_rev = b"HEAD"
    assert fs.exists("not_found") is False
    assert fs.isdir("not_found") is False
    assert fs.isfile("not_found") is False
    assert getattr(fs, "getinfo")("not_found")
    assert fs.listdir("not_found") == []

    blob_mock = MagicMock()
    blob_mock.data = b"testdata"
    fs._walk_tree = MagicMock(return_value=blob_mock)
    fs.repo = MagicMock()
    with patch("dulwich.objects.Blob", type(blob_mock)):
        assert fs.get_fileobj("found").read() == blob_mock.data
import pytest
from pgs.app import sanitize_path, is_hidden_path
import urllib.parse

@pytest.mark.parametrize(
    "path, expected_raise",
    [
        # Standard traversal
        ("../../../etc/passwd", True),
        # Null bytes
        ("foo/bar\0.txt", True),
        # Encoded traversal
        ("%2e%2e%2f%2e%2e%2fetc%2fpasswd", True),
        # Double encoded traversal
        ("%252e%252e%252f%252e%252e%252fetc%252fpasswd", True),
        # Valid path
        ("css/style.css", False),
    ]
)
def test_sanitize_path_traversal(path, expected_raise):
    if expected_raise:
        with pytest.raises(ValueError, match="Path traversal detected"):
            sanitize_path(path)
    else:
        sanitize_path(path)

@pytest.mark.parametrize(
    "path, expected",
    [
        # Straight hidden files
        (".env", True),
        (".git/config", True),
        ("css/.hidden.css", True),
        # Windows trailing dot or space tricks to bypass?
        (".env ", True), # startswith '.' is true
        (" .env", True), # Trailing spaces before the extension are stripped to prevent bypasses
        # Unicode homoglyphs?
        # Not usually handled by simple startswith unless normalized
    ]
)
def test_is_hidden_path_edge_cases(path, expected):
    assert is_hidden_path(path) == expected

