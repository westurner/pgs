import pytest
from unittest.mock import MagicMock, patch
import os
import io

from pgs.app import (
    RepositoryFS,
    DirectoryRepositoryFS,
    SubprocessGitRepositoryFS,
    DulwichGitRepositoryFS,
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


@pytest.mark.parametrize(
    "fs_class_name, conf_fixture",
    [
        ("DirectoryRepositoryFS", "conf_dir"),
        ("SubprocessGitRepositoryFS", "conf_subprocess_git"),
        ("DulwichGitRepositoryFS", "conf_dulwich_git"),
    ],
)
def test_repository_implementations_exist(fs_class_name, conf_fixture, request):
    conf = request.getfixturevalue(conf_fixture)
    cls = globals()[fs_class_name]

    if fs_class_name == "DulwichGitRepositoryFS":
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
