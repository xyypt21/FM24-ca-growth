# Project Guidelines

- All code, comments, docstrings, error messages, tests, `README.md`, and docs are in English.
- Do not edit `docs/TODO.zh.md`.
- Source code lives in `src/`; game offsets live only in `src/offsets.toml`.
- Python 3.11+, type hints, 88 columns, ruff.
- Unit tests must run without the game by using a fake memory object.
- Never write to game memory without explicit approval.
- When code changes, update `README.md` and the relevant files in `docs/` in the same change.
- Commit after every change.
