# Learning notes

My current understanding, one compact answer per topic. Newer wording replaces older wording.

## Step 0.1: what the project folder is made of

**Go / Node comparison** (author knows both):
| Python | Go | Node |
|---|---|---|
| package = folder + `__init__.py` | package = folder (files share `package x`) | folder + `index.js` |
| `pyproject.toml` | `go.mod` | `package.json` |
| `uv.lock` | `go.sum` | `package-lock.json` |
| `.venv/` | module cache (shared) | `node_modules/` |
| `uv` | `go` tool | `npm` |
| `uv run` | `go run` | `npm run` / `npx` |
| `import simulator.cli` | `import "mod/simulator/cli"` | `require("./simulator/cli")` |

**Python** is the language. It runs code directly (no compile step). A **package** is a
folder of Python files that other code can `import`. Ours is `src/simulator/`; the file
`__init__.py` marks a folder as a package and runs once, the first time the package is
imported (`import simulator`). Ours holds only a docstring (a description in triple
quotes), so importing does nothing else. `uv` has no official full form.

**uv** is a command-line program (written in Rust, by Astral, the makers of ruff) that
manages a Python project end to end. One tool instead of three older ones:
`pyenv` (install Python versions), `venv` (make the private environment) and `pip`
(install libraries), plus a lock file. It reads `pyproject.toml` and `.python-version`.
- `uv init`: start a project (writes `pyproject.toml` etc.).
- `uv add [--dev] <lib>`: add a library to `pyproject.toml`, lock it, install it.
- `uv sync`: read `pyproject.toml` and `uv.lock`, make `.venv/`, install exactly what the
  lock says. Installs Python 3.14 first if the machine lacks it.
- `uv run <cmd>`: run a command inside `.venv/` (`uv run pytest`, `uv run ruff check .`),
  syncing first if needed. No need to "activate" anything.
- Also the build tool: `uv_build` in `[build-system]` packages `src/simulator/`.

**Files at the root**
- `pyproject.toml`: the project's one settings file. `[project]` = name, version, the
  Python it needs (`>=3.14`) and runtime libraries (`dependencies`, empty for now).
  `[dependency-groups] dev` = tools only for building (pytest, ruff, pyright, hypothesis).
  `[build-system]` = how to package it (uv's own builder). `[tool.ruff]`, `[tool.pyright]`,
  `[tool.pytest]` = each tool's settings.
- `uv.lock`: the exact version of every library, written by uv, never edited by hand.
  It makes every machine install the same thing. Committed.
- `.python-version`: one line, `3.14`. Tells uv which Python to use here.
- `.venv/`: the **virtual environment**, a private folder holding this project's Python and
  its libraries, so projects do not disturb each other. Made by `uv sync`, deleted and
  rebuilt any time, never committed (it is in `.gitignore`).
- `.gitignore`: names git must not track (`.env`, `var/`, `.venv/`, caches).
- `.gitleaks.toml` + `.githooks/pre-commit`: the secret scan. A **git hook** is a script
  git runs at a fixed moment; this one runs before every commit, runs gitleaks on the
  staged changes and, if it finds a key, exits with an error so the commit is refused.
  `git config core.hooksPath .githooks` tells git to look in that folder.
- `.ruff_cache/`: a cache ruff makes for speed. Ignored.

**Folders**
- `src/simulator/`: the product code. `src/` layout keeps code apart from tests and
  prevents accidental imports of unbuilt code.
- `tests/` (not made yet): arrives with the first feature (step 0.2).
- `docs/PLAN.md`: build plan and progress. `Simulator.md`: product spec.

**The tools (all dev-only)**: `ruff` = lint (style mistakes) and format; `pyright` = type
checker (strict); `pytest` = runs tests; `hypothesis` = generates many test inputs.

## How the project is initialized (the flow, top to bottom)

Start: an empty folder `simulator/`.
1. `git init` -> creates `.git/`. The folder is now tracked by git.
2. `uv init --package --python 3.14` -> creates `pyproject.toml` (name, version, Python
   needed, build system), `.python-version` (`3.14`), and `src/simulator/__init__.py`
   (the empty package). Nothing is installed yet.
3. `uv add --dev pytest ruff pyright hypothesis` -> does three things: writes the four
   names into `pyproject.toml` under `[dependency-groups] dev`; resolves exact versions
   (and their own dependencies) into `uv.lock`; creates `.venv/` and installs them.
   (`uv sync` repeats the last two from the files alone, e.g. on a fresh clone.)
4. Hand-written config: `[tool.ruff]`, `[tool.pyright]`, `[tool.pytest]` in
   `pyproject.toml`; `.gitignore`; `.gitleaks.toml`; `.githooks/pre-commit`; `README.md`.
5. `git config core.hooksPath .githooks` -> git now runs the pre-commit script before every
   commit (stored in `.git/config`, so every fresh clone must run it once).
6. Check: `uv run ruff check . && uv run pyright` -> both clean.

Order matters: folder -> git -> Python project -> libraries -> config -> hook -> check.
(Commands are inferred from the files on disk, not watched.)
