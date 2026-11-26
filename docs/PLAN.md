# Simulator: the build plan

This is the working plan for building Simulator. The product spec (`Simulator.md`) says
**what** Simulator is and is not. This file says **how** we build it, in what order, and
why. Steps are ordered by engineering merit (risk first, clean interfaces, testability),
the way a production system is built, never by what is easiest to teach. Every step is a
finished, tested, integrated piece that later steps build on and never replace. Each step
carries one worked example, because the author understands a step best from one concrete
case. "Learn:" lines are optional notes on what a step touches, not its purpose.

This plan covers milestone M0 in full. Later milestones are outlines, expanded into steps
when they are reached.

---

## 0. Ground rules

Decided before any code was written. They do not change without a recorded decision.

### 0.1 Project rules

- **One step at a time.** A step is done when it runs, it has been checked by hand
  through its real command, and Progress says so. Then the author gives the OK for the
  next one.
- **Build first, tests later.** No automated tests are written while features are built.
  Each step's "Verify" line is checked by hand by running the real command on real input.
  The automated tests the steps name are written in a separate testing pass, when the
  author asks for it.
- **Build feature by feature.** Every step is a real, lasting slice. No placeholder code:
  a file, function, field, flag or folder appears in the step that uses it. No
  planned-broken states. If two mechanisms only make sense together, they are one step.
- **Simulator is general. No platform code or files in this repository.** Everything here
  must work for any REST API. Nothing names or configures one platform (Gitea, GitHub,
  Slack): no adapter files, compose files, checks or downloaded description files.
- **Features first, platform check after.** Steps 0.2 to 0.4 build the features as
  generic code, each tested on its own. Steps 0.5 to 0.8 then check them against a real
  platform (Gitea first). Each platform is described by **declared settings, not code**,
  kept outside this repository; where they live is decided with the author before step
  0.5 (open question 4). A difference the core cannot express from settings is a core
  change and is recorded as a decision.
- **Decision records before dependent code.** See Decisions in Progress.
- **Libraries only from `Simulator.md` section 11**, plus any recorded under Decisions
  with a one-line reason.
- **Secrets:** real keys live only in `.env` (git-ignored). Local state lives in `var/`
  (git-ignored). gitleaks runs before every commit.
- **Containers:** the reference runs under Docker Compose with its image pinned by
  digest; `docker compose down -v` removes it and its volumes. The clean-state copy of
  its data stays on disk in `var/`.
- **No UI and no CI in M0.**

### 0.2 Code style rules

See `CLAUDE.md`, "Code style". In short: plain functions, full-word names by purpose, one
source of truth, pyright strict, a docstring with a concrete example on every function,
error messages a user can act on.

### 0.3 Architecture in one picture (M0)

```
  simulator CLI (Typer, every command has --json)
     |
     v
  core: src/simulator/  -- generic, names no platform
     |  reads one platform's settings and checks (kept outside this repository)
     |  and its description file
     |
     +--> reference.py : start / health / reset / stop a reference, from its settings
     +--> api_description.py : description file -> common form
     +--> compare.py : runs one check on two sides, maps ids and keys, normalises, reports
     |
     +------------------------+---------------------------+
     v                        v                           v
  side "a": Gitea copy A   side "b": Gitea copy B    side "b": no-store stand-in
  (the reference)          (Scenario A, must match)  (Scenario A, must be caught)
```

- A **side** is one system that receives a check's calls: a base address plus that
  side's own keys. The reference is always side `a`.
- A **check** is a short list of calls: set-up steps, then action steps, then a
  hand-written read-back list. It is a TOML file that belongs to one platform's settings.
- The **comparison** sends each call to both sides, keeps each side's own identifiers and
  keys apart, normalises what always differs, and compares status, body and read-backs.

### 0.4 Why the second Gitea copy must differ from the first

Two fresh Gitea copies hand out the same numbers: the first issue is number 1 on both.
If both also restored one clean-state copy, they would share the same admin key. Then a
check could send side `a`'s issue number or key to side `b` by mistake and still pass,
and property check 11 could never fail. So each copy is bootstrapped on its own (its own
admin key), and copy B gets a few throw-away issues first, so its numbers run ahead of
A's. A mapping bug then sends a call to the wrong issue and the check fails, as it must.

### 0.5 Repository layout (end of M0)

Files appear in the step that needs them; this is the end state, not a scaffold. Nothing
in it is specific to one platform.

```
simulator/
  CLAUDE.md                  shared context every session reads first
  Simulator.md               the product spec (not edited during the build)
  README.md                  public page (0.1)
  learning.md                the author's notes
  docs/PLAN.md               this file
  pyproject.toml uv.lock .python-version
  .gitignore .gitleaks.toml .githooks/pre-commit
  src/simulator/             the generic core, one module per job, README first
    README.md
    command_line.py          the `simulator` command (Typer): load, compare, ref
    api_description.py       reads an API description file into the common form
    checks.py                the check file format and its loading
    normalise.py             what always differs: ids, times, tokens, base address, order
    compare.py               runs checks on two sides; mapping, retry, report
    model_boundary.py        the one door for every future model call
    settings.py              reads one platform's declared settings (0.5)
    reference.py             start, health check, reset, stop; timing and read-back (0.5)
    roles.py                 role users and their keys, once per session (0.6)
  examples/
    api-descriptions/        sample description files of a made-up task tracker, written
                             by us in each format, for trying `simulator load` by hand
  tests/                     written in the later testing pass
    unit/                    pure code: loader, normalise, mapping, property 11, boundary
    integration/             the platform check (0.5 to 0.8)
  var/                       git-ignored local state
```

If `src/simulator/` grows past about ten modules, it is split by area (for example
`compare/`), not by file type, with a recorded decision.

### 0.6 What one platform's settings declare

Settings, not code, kept outside this repository. The core reads every one of them;
none is written in `src/`. For Gitea, as the first example:

- **reference:** how to start it (compose file, ports per copy, health address, data
  folder), how long to wait for health.
- **bootstrap:** how to create the administrator (fixed login, email, full name) and its
  key; the read that proves the clean state.
- **auth:** how a key is sent (`Authorization: token <key>`).
- **errors:** how a failure is recognised, the error body's fields, and which are stable.
- **paging:** style (`page` and `limit`; `X-Total-Count` and `Link` headers).
- **identifiers, times, tokens:** which reply fields hold identifiers, timestamps and
  random values.
- **ordered lists:** endpoints whose list order is promised (default: none).
- **roles:** each role's user, how it is created, and how its key is made.
- **description:** where the platform's description file comes from, at its pinned
  release.

### 0.7 Local state (`var/`, git-ignored) and `.env`

`var/` holds what Simulator downloads or produces on this machine: description files,
clean-state copies of a reference's data, the model cache, compare reports. `.env` holds
real keys. Key names are built from the platform's name, the copy and the role
(`<PLATFORM>_<COPY>_<ROLE>_KEY`), so no platform name is written in `src/`.

### 0.8 Testing approach

- **Unit tests** (`tests/unit/`, no Docker): the loader on our own small samples of each
  description format, normalisation, identifier and key mapping, property check 11 with
  hypothesis, the model boundary with scripted answers and a fake clock.
- **Integration tests** (`tests/integration/`, from step 0.5): the platform check. They
  start real copies of the platform under Docker, reset them, set up roles, run Scenario A. They need Docker running and fail with a clear
  message when it is not. They never skip: a test that skips by default is not a test.
- **No dummy tests.** A test checks behaviour that stays true for good. The only test
  doubles are the two synthetic sides in property check 11, because the spec needs
  identifier spaces that are guaranteed not to overlap, which two real copies of a
  platform cannot promise.
- `uv run pytest` runs everything; `uv run pytest tests/unit` runs without Docker.

---

## Milestone M0: Setup

Goal (`Simulator.md` section 8): a pinned Gitea that resets to a verified clean state in
one command; its description read into one common form; the comparison skeleton with
per-side mapping, minimum normalisation and read-after-write retry; 15 hand-written
checks; two stand-ins; the model boundary; the secret scan.
**Proven by:** Scenario A and property check 11.
**Numbers:** stand-ins caught out of stand-ins planted; time of one reset; memory of two
Gitea copies running together (plus the laptop's memory and Docker's memory limit).

**Step 0.1: Project setup and secret scan.** (Setup only: no feature code, no tests.)
`git init`; uv project on Python 3.14 (`pyproject.toml`, `uv.lock`, `.python-version`) with
an empty `simulator` package; ruff, pyright strict and pytest configured; `.gitignore`
(`.env`, `var/`, caches); `.githooks/pre-commit` running gitleaks on staged changes,
switched on with `git config core.hooksPath .githooks`; `.gitleaks.toml` with gitleaks'
default rules plus one for 40-hex keys assigned to a `*_TOKEN` or `*_KEY` name;
`README.md`.
Example: staging `REF_ADMIN_TOKEN=9c1f…` (40 hex characters) and committing is refused,
and gitleaks names the line; committing a notes file goes through.
Verify (by hand): `uv sync` installs; ruff and pyright are clean; a 40-hex key is refused
by the hook in a throw-away repository and an ordinary file commits; `.env` and `var/`
are ignored. The command line and the first tests arrive with the first feature (0.2).
Learn: uv and lock files; how a git hook stops a commit.

Features first: steps 0.2 to 0.4 build Simulator's features as generic code, with no
platform, no Docker and no running service; each feature is tested right after it is
built. Steps 0.5 to 0.8 are the platform check: the finished features are pointed at a
real platform (Gitea first), whose settings live outside this repository.

**Step 0.2: Description loader and `simulator load`.**
`api_description.py` reads a description file in Swagger 2.0, OpenAPI 3.0 or OpenAPI 3.1 into
one common form. Per endpoint: `id` (method + path), `name` (operationId), `kind` (the
last fixed path part), `writes` (any method but GET/HEAD/OPTIONS), path and query
parameters, body schema, replies by status (JSON Schema with references resolved;
`nullable: true`, `x-nullable` and `type: [T, "null"]` all become `type: [T, "null"]`;
a schema that refers back to itself keeps one `$defs` reference), `needs_key` (from the
security requirements). An endpoint that does not send and receive JSON is marked "not
simulated". `simulator load FILE [--endpoint ID] [--json]` takes the path of any
description file. `src/simulator/README.md` is written first.
Example: with our own small sample of a task-tracker API,
`simulator load examples/api-descriptions/task-tracker-openapi-3.0.json --endpoint "POST /projects/{project}/tasks"`
prints `name createTask, kind tasks, writes yes, needs key yes, body NewTask, replies 201
Task, 404 Error, 422 ValidationError`; its file-download endpoint is marked "not
simulated".
Verify: our own small sample in each format (`examples/api-descriptions/`, the same task-tracker API
written as Swagger 2.0, OpenAPI 3.0 and OpenAPI 3.1) loads to the same expected common
form; `simulator load` prints the counts of endpoints and "not simulated" endpoints. The
loader is checked on a real platform's description file in step 0.5.
Learn: the OpenAPI overview; how 2.0, 3.0 and 3.1 differ.

**Step 0.3: The comparison engine and `simulator compare`.**
`checks.py` (the check file format: set-up steps, action steps, and a read-back list with
the fields each action is expected to change), `normalise.py`, `compare.py`, and
`simulator compare`. It sends every call of a check to two sides and compares the
replies and the read-backs.
- Each check makes its own fresh container object in set-up (for a code host, a
  repository with a unique name, mapped between sides) and reads only inside it.
- Each side keeps its own table of identifiers and keys: `$issue` is number 4 on side `a`
  and 7 on side `b`; a later step "comment on `$issue`" goes to 4 on `a` and 7 on `b`; in
  the comparison both become `<issue#1>`.
- Normalisation: mapped identifiers, timestamps (shape only), random tokens, each side's
  own base address (`http://localhost:3001` becomes `<base>`), unordered lists sorted.
- Read-after-write on side `a` (the reference) only: read again until two reads agree
  and every field the read-back list expects to change has changed (after an error
  reply: two agreeing reads and none changed); give up after 10 s and mark the check
  unsteady. Side `b` is read once.
- The report names, for each mismatch, the call, both replies, both read-backs and the
  rule that flagged it; it is saved in `var/results/`.
Example: side `a` creates issue 4 titled "Login broken", side `b` creates issue 7 with
the same title; after normalisation both read-backs are `{number: <issue#1>, title:
"Login broken", created_at: <time>}`, so the check matches. If side `b` reads back
"Example issue" instead, the report shows a mismatch on the read-back of `$issue`.
Verify (unit): normalisation and mapping; the retry rule with a reference that settles
on the third read and one that never settles; **property check 11** (hypothesis builds
random check sequences against two in-memory sides with non-overlapping numbers and
keys, and fails if any call to one side carries a value the other side made up; a
deliberately broken mapping is shown to be caught). The in-memory sides are the one test
double allowed here: the spec needs identifier spaces that are guaranteed not to
overlap. The engine's first run against real systems is in steps 0.7 and 0.8.
Learn: differential testing; why identifiers are mapped during a check, not after.

**Step 0.4: The model boundary.**
`model_boundary.py`: the one place every future model call goes through. Throttling
(space calls to a set rate), back-off (on a "rate limited" or "unavailable" error, wait
1 s, 2 s, 4 s… up to a limit), a cache for build-time calls only (keyed by a sha256 of
the request, stored in `var/cache/model/`), secret stripping of known values (every value
in `.env`, plus a fixed pattern list, counted per call), and a scripted provider that
returns recorded answers. No live model call and no provider library in M0.
Example: a build-time request "write the issues part" is answered by the scripted
provider and cached; the same request again is served from the cache and the provider is
not asked; an agent-kind request with the same text is never cached; a prompt containing
the admin key reaches the provider as `[REDACTED]`, and the strip count is 1.
Verify (unit): each behaviour above, using a fake clock so back-off waits take no real
time; hypothesis: agent and customer requests never hit the cache.
Learn: rate limits, back-off, why only build-time calls are cached.

**Step 0.5: The Gitea reference: start, stop and a measured reset.** (First use of Docker.)
Gitea's settings (section 0.6: compose file with Gitea pinned by digest, SQLite, install
screen locked; the `reference`, `bootstrap` and `description` parts), kept outside this
repository; `settings.py`, `reference.py`;
`simulator ref start|reset|stop --platform PATH --copy a [--json]`.
- The first start creates the admin (fixed login, email, full name) and its key (saved
  to `.env`), stops Gitea, copies its whole data folder to `var/gitea/a/clean/`, and
  starts again.
- `ref reset`: stop Gitea, empty its data volume, copy the clean folder back (using the
  same pinned Gitea image, so no second image is needed), start, wait for health, then
  read back: exactly one user (the admin, fixed fields) and no repositories. Prints how
  long it took.
- The loader from step 0.2 is checked on Gitea's real description files (Swagger 2.0 and
  OpenAPI 3.0): both load to the same common form, and so does the file the running copy
  serves.
Example: create repository `scratch` and user `temp`, run `simulator ref reset --platform PATH
--copy a`: it prints `reset gitea/a in 6.8 s: users [simadmin], repositories 0,
clean`; `scratch` is gone.
Verify (integration): start, read the admin with its key, fields equal the fixed values;
the reset example above; a reset of a copy that is not running is a clear error;
`ref stop` then `docker compose down -v` leaves no container and no volume.
**M0 number: time of one reset.**
Learn: Docker Compose, image digests, Gitea's command line; why the whole data folder is
restored, not only the database (Gitea keeps repository contents on disk).

**Step 0.6: Role set-up.**
`roles.py` and the adapter's `roles` part: after each full reset, each role user is
created once through the admin route, and its key comes from Gitea's command line. Keys
go to `.env` under the copy's own names. Runs as part of `ref start` and `ref reset`.
Example: after `ref reset`, `maria` exists; `/api/v1/user` with maria's key returns
`login: maria`; with no key it returns 401.
Verify (integration): each role's key returns its own user; after a reset the roles are
recreated with new keys and the old keys are refused.
Learn: why checks name a role, never a key.

**Step 0.7: The 15 Gitea checks against a second Gitea copy (Scenario A, part 1).**
Copy B (`--copy b`, port 3001) started with its own data and keys and skewed with a
few throw-away issues (section 0.4). The checks, each in its own file under
Gitea's settings folder with its own read-back list: create an issue and read it back; edit
an issue; close an issue and list open issues (with the repository's open count); reopen
an issue; add a comment; edit a comment; delete a comment (reading it gives 404); create
a label; put a label on an issue; take it off; delete a label (the issue no longer has
it); assign an issue to a milestone; lock an issue and have maria comment; olga (not a
collaborator) tries to create a label (403) and a call with no key (401); a missing title
(422) and an issue that does not exist (404). The adapter's error fields and ordered
lists are confirmed here from Gitea's real replies.
Example: `simulator compare --platform PATH --a a --b b` prints
`15/15 checks match` and saves a report in `var/results/`.
Verify (integration): 15/15 match. **M0 number: memory of two Gitea copies** (from
`docker stats`), printed with the laptop's memory and Docker's memory limit.
Learn: what a read-back list is and why "the reply matched" is not enough.

**Step 0.8: The no-store stand-in (Scenario A, part 2) and the M0 numbers.**
A small FastAPI program, kept with Gitea's settings (not in this repository), that answers only the endpoints the 15
checks use, with replies that look right and store nothing. `simulator compare --platform
PATH --a a --b standin`. The summary prints the three M0 numbers.
Example: the stand-in answers "create issue *Login broken*" with 201 and that title, but
reading the issue back returns a made-up *Example issue*: the check is a mismatch.
Verify (integration): the stand-in is caught; the report gives both how many checks
caught it and whether the stand-in is caught at all; the three numbers are printed.
**M0 number: stand-ins caught out of stand-ins planted.**

**M0 is done when:** Scenario A passes (15/15 against copy B; the stand-in caught),
property check 11 passes, and the three numbers are printed and recorded in Progress.

---

## Later milestones (outlines, expanded into steps when reached)

- **M1a.** The store, supervisor and control door; key holder; a first working set of 8
  to 10 endpoints; the black-box experiment runner and related-reads list; the first
  generated fake in a capped container; about 30 checks; the score floor; the approval
  record. Provider libraries (google-genai, groq) arrive here.
- **M1b.** The full working set (20 to 40 endpoints), closure check, about 100 checks.
- **M2.** The fix loop, guardrails, held-out score, review and freeze into a bundle.
- **M3.** Tasks, data recipes, snapshots, end-state checks, traps defined.
- **M4.** The baseline agent, simulated customer, trap layer, grading, k runs, report.
- **M5.** The CI gate, injections and hijack rate, the agreement figure.
- **M6 to M9.** Chatwoot, Hyperswitch, GitHub, documentation-only and MCP inputs.

---

## How each step is worked

1. Read the step. Explain it to the author with its worked example. If it starts a new
   folder, write that folder's `README.md` first.
2. Record any decision the step depends on under Decisions.
3. Write the code with the rules in `CLAUDE.md`. Add nothing the step does not use.
4. Check it by hand: run the real command on real input, as the "Verify" line says. Run
   ruff and pyright. (Automated tests come in the later testing pass.)
5. Show the author the result. Update Progress and `README.md`. The author commits by
   hand. Wait for the OK before the next step.

### Definition of done (every step)

1. One feature, describable in one sentence.
2. Decisions it depends on are recorded before its code.
3. Checked by hand through the real command, error paths included, not only the happy
   path.
4. Integrated through the real entry point (the CLI), never a test-only path.
5. No dummy code, no TODOs, nothing that exists only for a later step.
6. Nothing under `src/` names an API; nothing secret outside `.env` and `var/`.
7. ruff and pyright strict clean; Docker left with no stray containers or volumes.
8. Progress, `README.md` and the folder README updated in the same piece of work.

---

## Progress

Updated at the end of every step. A new session reads this first.

**Current step:** 0.3, the comparison engine (not started). Docker is not needed until
step 0.5.

**Done:**
- 0.1 (2026-11-24): setup only. `git init` (branch `main`, no commits). uv project on
  Python 3.14 (`pyproject.toml`, `uv.lock`, `.python-version`) with an empty `simulator`
  package and uv's own build backend. ruff, pyright strict and pytest configured (pytest
  in importlib mode so `tests/unit` and `tests/integration` can hold files with the same
  name). `.gitignore` (`.env`, `var/`, caches). `.gitleaks.toml` (default rules plus
  `hex-access-token`) and `.githooks/pre-commit`, switched on with
  `git config core.hooksPath .githooks`. `README.md`. A `simulator version` command and
  its tests were built and then removed at the author's request: step 0.1 is setup only,
  and the command line starts with the first feature. Verified by hand: `uv sync` installs
  and the package imports; ruff and pyright report no problems; in a throw-away
  repository using this hook, a random 40-hex key is refused and a notes file commits;
  gitleaks' default rules alone miss a low-randomness 40-hex key and ours catch it;
  `git check-ignore` confirms `.env` and `var/` are ignored.

- 0.2 (2026-11-25): description loader and `simulator load`. `src/simulator/README.md`
  (written first), `api_description.py` (`load_description`: file checks, format detection,
  one reader for Swagger 2.0 and one for OpenAPI 3.x, and `SchemaCleaner`, which follows
  references, keeps self-containing schemas in `defs`, writes "can be null" and exclusive
  bounds one way, and drops non-shape keys), `command_line.py` (`simulator load FILE
  [--endpoint ID] [--json]`; errors print a sentence and exit 1, as `{"error": ...}` with
  `--json`). typer added. Samples in `examples/api-descriptions/`: one task-tracker API (8
  endpoints, including a self-containing Task, nullable fields, an exclusive bound, a
  public endpoint, a file upload and a file download) written by us in all three formats.
  Found while comparing them: Swagger 2.0 cannot give one reply its own media type, so
  its `produces` is read as covering successful replies only (Decisions). Checked by hand
  (no automated tests, by the author's rule): ruff and pyright report no problems; all
  three samples load to the same common form apart from their format; `simulator load`
  prints the summary, one endpoint as text and as JSON, and the whole common form as
  JSON; an unknown endpoint and a missing file print a sentence and exit with 1. Not
  yet checked on a real platform's description file: that is step 0.5.

**Facts checked (2026-11-24):**
- Gitea's latest release is v28.4.0 (2026-11-15); Gitea moved from 1.x to 28.x numbering
  after v1.27.3. Its repository ships `templates/swagger/v1-swagger.generated.json`
  (Swagger 2.0) and `v1-openapi3.generated.json` (OpenAPI 3.0.3, not 3.1), 342 paths and
  537 operations each. Gitea 1.26 and older shipped only Swagger 2.0.
- Docker Hub lists `gitea/gitea:28.4.0` as `sha256:aa90e8f0…d309`. Still to confirm in
  step 0.5 that this is the multi-platform index (`docker buildx imagetools inspect`).
- Python 3.14.7 is installed; every library in section 11 installs and imports on it.
- gitleaks 8.30.1 is installed (Homebrew). Its default rules catch a 40-hex key only
  through the generic rule, above a randomness cut-off of 3.5 (a random key scored 3.7),
  hence the extra rule in step 0.1.
- The laptop has 16 GB of memory. Docker Desktop was not running when checked.

**Still to confirm in the step that needs it:** the exact Gitea commands and flags for
creating the admin and making keys (0.5, 0.6); the addresses where a running Gitea serves
its two description files and the `info.version` it reports (0.5); Gitea's error body
fields and which lists promise an order (0.7).

**Decisions (date, what, why):**
- 2026-11-25: **Names say what a file or folder is for.** The author's rule. Renamed:
  `tests/fixtures/` to `examples/api-descriptions/` (they are sample input, not tests),
  `tasks-*.json` to `task-tracker-<format>.json`, `cli.py` to `command_line.py` and
  `description.py` to `api_description.py`.
- 2026-11-25: **Build first, tests later.** The author's choice: features are built and
  checked by hand through their real commands; no automated tests are written until a
  separate testing pass the author asks for. The pytest files written in step 0.2 were
  removed. The sample description files in `examples/api-descriptions/` are kept: they are real
  input for checking `simulator load` by hand.
- 2026-11-25: **Step 0.2 loader details**, recorded before its code.
  - **JSON files only.** Description files are read as JSON; a YAML file is refused with
    a clear message. Reading YAML needs a library section 11 does not list; it is added
    by a recorded decision when a platform needs it.
  - **Size limit for this untrusted input: 20 MB.** Large real files are about 1 MB.
  - **Shape only.** The common form keeps what describes the shape of data. It drops
    vendor extensions (`x-...` keys), examples (`example`, `examples`) and documentation
    keys (`xml`, `externalDocs`, `discriminator`); none of them changes which data is
    valid.
  - **One way to say each thing.** "Can be null" (`nullable: true`, `x-nullable: true`,
    `type: [T, "null"]`) becomes `type: [T, "null"]`. An exclusive bound written the old
    way (`minimum: 0, exclusiveMinimum: true`) becomes the new way (`exclusiveMinimum: 0`).
  - **References are replaced by what they point to**, and each schema that came from a
    named definition gets that name as its `title` when it has none, so a reader still
    sees "Task" rather than a bare object. A schema that contains itself (a task with
    subtasks) is kept once under `$defs` and pointed to with `$ref`.
  - **"Not simulated"** when the request body is not JSON (a form or a file upload) or a
    reply with a body is not JSON (a file download, plain text).
  - **Swagger 2.0's `produces` covers the successful replies only.** Swagger 2.0 states
    one media type per endpoint, so a file download's 404 would read as a file too;
    OpenAPI 3 gives each reply its own. Error replies (4xx, 5xx, `default`) with a schema
    are read as JSON, which is how real APIs send errors. Found while comparing the three
    sample files.
  - **The common form is plain frozen dataclasses**, printed as JSON with `--json`. It is
    not saved to a file yet, so it needs no pydantic model or format version until then.
- 2026-11-25: **No platform code or files in this repository.** Simulator is a general
  tool; Gitea is only the first platform it is checked against. Features are built
  generically first (0.2 to 0.4); the platform check comes after (0.5 to 0.8). The
  loader's samples are our own task-tracker API. Leftover Gitea files from an earlier,
  rewound attempt at 0.2 were removed. The author's rule.
- 2026-11-24: **M0 builds the core first** (loader, comparison engine, model boundary:
  steps 0.2 to 0.4, no Docker), then the Gitea reference and the checks (0.5 to 0.8).
  The author's choice: the system is built before the thing it is pointed at. Start and
  reset of Gitea became one step (0.5). Each step's tests still come right after its code.
- 2026-11-24: **Python 3.14**, not the 3.12 in `Simulator.md` section 11. The author's
  choice; every chosen library installs on 3.14.7.
- 2026-11-24: **Gitea v28.4.0**, the standard image (not rootless), pinned by digest, with
  SQLite, so the whole state is in one data folder. Kept for the whole project.
- 2026-11-24: **Declared files are TOML**, read with Python's built-in `tomllib`, so no
  YAML library is added (section 11 lists none). The compose file stays YAML because
  Docker Compose requires it.
- 2026-11-24: **The secret scan is a plain git hook** in `.githooks/`, switched on with
  `core.hooksPath`, so it is under version control; not the pre-commit framework (a
  tool outside section 11).
- 2026-11-24: **uvicorn** is added: FastAPI (section 11) needs a server to run the
  stand-in.
- 2026-11-24: **Each side's own base address is normalised.** Gitea's replies carry the
  copy's own address (`html_url`), which the spec's four normalisation items do not
  cover; without this no check could match. Generic: every API echoes its host.
- 2026-11-24: **M0 read-back lists carry the fields each action is expected to change**,
  because the retry stopping rule (spec 5.4) needs them and the related-reads list that
  normally holds them arrives at M1a.
- 2026-11-24: **Each Gitea copy has its own bootstrap, clean copy and keys**, and copy B
  is skewed with throw-away issues (section 0.4).
- 2026-11-24: **Provider libraries wait for M1a.** M0 makes no live model call.
- 2026-11-24: **The model boundary is built in M0 without a consumer**, because the spec
  requires it before the first model call (5.16); its first real user is M1a.

**Open questions (answered before the step that needs them):**
1. (0.8) Does the no-store stand-in run inside the test process (it is trusted
   hand-written code; the spec's container rule is for generated code), or in a Docker
   container removed when stopped (`--rm`), which needs an image build? Default: inside
   the test process.
2. (0.8) "The checks must catch it": at least one check, or every one of the 15? Both
   counts are reported either way.
3. (M0 end) The spec's M0 also records the model providers' limits and terms and the
   daily model-call budget. This needs the author's own Gemini and Groq accounts. Default:
   the author records them here before M0 is closed; no code involved.
4. (0.5) Where does a platform's settings folder (Gitea's settings, checks and stand-in)
   live, given that this repository holds no platform files? For example a separate
   folder or repository such as `~/Projects/simulator-platforms/gitea/`, passed to
   commands with `--platform PATH`.
