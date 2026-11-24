# Simulator

A tool that builds a local fake of the tested part of any REST API, measures how closely
the fake matches the real system by sending both the same calls, and then tests AI agents
on the fake, grading them by the data they change. Written in Python. It is a flagship
project for the author's AI-engineer job search, and the code is also their learning
material.

## Read first

- `Simulator.md` is the product spec: what Simulator is, its scenarios, features and
  milestones. It says **what** to build. It is not edited during the build; when the
  build decides something different, the decision is recorded in `docs/PLAN.md`.
- `docs/PLAN.md` is the build plan: **how** and in what order. Its **Progress** section
  at the bottom says which step is done and which is next. Start there in every session.
- `README.md` (from step 0.1) is the project's public page. Keep it in sync in the same
  piece of work whenever a feature, command, flag or requirement changes. Only describe
  what a test has actually run.
- `learning.md` (from the first learning question) holds the author's current
  understanding. Read it before explaining a Simulator concept.
- `src/simulator/README.md` (from the first feature) explains the code. Read it before
  touching `src/`.

## Rules

- **One step at a time**, in the order in `docs/PLAN.md`. A step is done only when it
  runs, its tests pass, and the Progress section is updated. Then stop for the author's
  OK before the next step.
- **Simulator is general. No platform code or files in this repository.** Nothing in
  the repository names or configures a specific platform (Gitea, GitHub, Slack, ...):
  no adapter files, compose files, checks or downloaded description files for one
  platform. Ask: "would this line work for any REST API?" If not, it does not go in.
- **Features first, platform check after.** Build Simulator's features one by one as
  generic code, each tested on its own. Only then check them against a real platform
  (Gitea is the first). Where that platform's settings live is decided at that step,
  with the author, and recorded under Decisions.
- **No placeholder or dummy code.** A file, function, field, flag or folder appears in
  the step that uses it. No code written only for a test or for a later step. Tests run
  the real thing (real Gitea, real gitleaks, real files); a test double is allowed only
  where the spec asks for one, and its reason is written next to it.
- **The layout is fixed.** `docs/PLAN.md` section 0.5 is the layout. Files are added
  inside it; nothing is moved or renamed without the author's yes.
- **Decisions before dependent code.** A choice the spec leaves open is written under
  Decisions in the Progress section before the code that depends on it.
- **If a fact in the spec turns out wrong** (a Gitea version detail, a path, a library
  behaviour), stop and tell the author. Never work around it silently.
- **Git:** only `git init` (step 0.1) is run by Claude. Every other git command,
  commits included, is the author's. When a step is done, say it is ready to commit.
- **Ask before anything big or new:** installing software, starting Docker, deleting
  files.
- **Services start only when needed.** Never start Docker Desktop, a container or any
  other service ahead of time. Write a step's code and its Docker-free tests first; ask
  just before the first command that needs a running service; stop it again afterwards.

## Working with the author

- The author is a backend developer, new to agents, evals and code generation.
- Before each step, explain what it builds with **one concrete worked example**.
- Chat is short; code comments and READMEs carry the detail.
- Explain code as an execution story: start from one real command and follow it through
  each function in the order it runs.
- After every learning question, add the compact final answer to `learning.md`,
  replacing earlier wording rather than keeping two versions.

## Code style

- **Simple, readable, maintainable.** Plain functions and small modules. A class only
  when it really holds state. No abstraction until a second real use exists. No clever
  tricks.
- **Names are full words, by purpose, as short as clear:** `reset_reference`, not
  `rst_ref`; `admin_key`, not `tok`. A name does not repeat its module.
- **One source of truth.** Every value (number, name, path, default, list) and every type
  is defined once and imported everywhere else. Tests are the exception: they write
  expected values as literals on purpose.
- **Typed.** pyright strict passes. pydantic models for anything read from or saved to a
  file.
- Every file starts with a docstring: what it holds and why it is its own file.
- Every function has a docstring: what it does, when it is called, what failure means,
  and one concrete example (real input and what comes out). Plain everyday words; a
  technical word is explained where it first appears.
- Error messages are full sentences a user can act on: "Gitea did not answer on
  http://localhost:3000 within 60 seconds; is Docker running?", not "timeout".

## Architecture in one line

CLI (Typer) → core (`src/simulator/`, generic) reading one API's settings, given from
outside the core → two sides (the real system and a candidate) over HTTP → a comparison
report. See `docs/PLAN.md` section 0.3.
