# Simulator

**Builds a local fake of the tested part of any REST API, measures how closely it matches
the real system, and tests AI agents on it, graded by the data they change.**

The full product spec is [Simulator.md](Simulator.md). The build plan, with progress and
decisions, is [docs/PLAN.md](docs/PLAN.md).

> **Status:** milestone M0 in progress. Step 0.1 is done: the project is set up (Python
> 3.14 with uv, lint, type and test tools) and secrets are scanned before every commit.
> No feature code yet.

## Features

| Area | Feature | Status |
| --- | --- | --- |
| Project | Secret scan before every commit (gitleaks, with an extra rule for 40-hex access keys) | ✅ Done |
| Description | Swagger 2.0 and OpenAPI 3.x read into one common form (`simulator load`) | Planned (0.2) |
| Comparison | Checks sent to two sides with per-side identifiers and keys (`simulator compare`) | Planned (0.3) |
| Model boundary | One door for every model call: throttling, back-off, cache, secret stripping | Planned (0.4) |
| Platform check | The features above checked against a real platform (Gitea first, kept outside this repository): start, reset, 15 checks, two stand-ins | Planned (0.5 to 0.8) |

## Requirements

- macOS on Apple Silicon (the author's machine), or Linux.
- [uv](https://docs.astral.sh/uv/). It installs Python 3.14 and every library.
- Docker Desktop (from step 0.5).
- gitleaks: `brew install gitleaks`.

## Setup

```bash
uv sync
```

```bash
git config core.hooksPath .githooks
```

The first command installs Python 3.14 and the libraries pinned in `uv.lock`. The second
switches on the secret scan for this clone.

Real keys go only in `.env`; local state (fetched description files, clean-state copies,
caches, reports) goes in `var/`. Git ignores both.

## Checks

pytest is added to these once the first feature has tests (step 0.2).

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

## Layout

See [docs/PLAN.md](docs/PLAN.md), section 0.5.
