# Simulator

**Builds a local fake of the tested part of any REST API, measures how closely it matches
the real system, and tests AI agents on it, graded by the data they change.**

The full product spec is [Simulator.md](Simulator.md). The build plan, with progress and
decisions, is [docs/PLAN.md](docs/PLAN.md).

> **Status:** milestone M0 in progress. Steps 0.1 (project setup and secret scan) and
> 0.2 (description loader) are done. Not yet checked against a real platform.

## Features

| Area | Feature | Status |
| --- | --- | --- |
| Project | Secret scan before every commit (gitleaks, with an extra rule for 40-hex access keys) | ✅ Done |
| Description | Swagger 2.0, OpenAPI 3.0 and 3.1 read into one common form (`simulator load`): references resolved, "can be null" written one way, non-JSON endpoints marked "not simulated" | ✅ Done |
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

## Commands

| Command | What it does |
| --- | --- |
| `simulator load FILE [--endpoint ID] [--json]` | Reads a description file (JSON) and prints a summary, one endpoint, or the whole common form as JSON. |

Example:

```bash
uv run simulator load examples/api-descriptions/task-tracker-openapi-3.0.json --endpoint "POST /projects/{project}/tasks"
```

## Checks

Automated tests come in a later testing pass; until then each feature is checked by hand
through its command.

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

## Layout

See [docs/PLAN.md](docs/PLAN.md), section 0.5.
