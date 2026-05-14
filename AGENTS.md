# AI Agent Instructions for `pgs`

Welcome, AI Agent! This document outlines the general structure and important context for working on this project.

## Project Overview
`pgs` is a Bottle-based Python web application for serving static files either from the local filesystem or directly from a Git branch, preserving the `Last-Modified` headers according to git timestamps.

## Key Files and Directories
- `pgs/`: The main application package containing:
  - `app.py`: Logic for building the WSGI application and routing.
  - `bottle.py`: The micro web-framework itself (vendored).
  - `pgs.py`: CLI bindings and configuration flags parsing.
- `tests/`: Project tests utilizing the standard library's `unittest` module or `pytest`.
- `pyproject.toml`, `setup.cfg`, `requirements.txt`: Describe project metadata and dependencies.
- `tox.ini`: Used for testing across multiple Python local environments.

## Development Constraints and Guidelines
- **Python Version:** Ensure compatibility with standard Python 3 environments.
- **Vendored Dependencies:** The project vendors `bottle.py`. Do not modify or replace it without explicit consent.
- **Git Integration:** Interface with the Git CLI using `subprocess.check_output` or existing codebase patterns.
- **Environment:** A Dev Container environment based on fedora-toolbox:44 is available in `.devcontainer`.

## Task Tips
- **Dependencies:** If adding a new dependency, ensure it is added to `requirements.txt` (or `requirements.test.txt` if only for testing).
- **Testing:** Make sure to run `pytest` or `tox` to verify any modifications you introduce.
- **Documentation:** Consider updating the `README.rst` and the documentation in `docs/` if you add new command-line features or APIs.
