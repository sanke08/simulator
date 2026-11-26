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
| `import simulator.command_line` | `import "mod/simulator/command_line"` | `require("./simulator/command_line")` |

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
- `tests/` (not made yet): arrives with the later testing pass.
- `examples/api-descriptions/`: three sample description files (a made-up task tracker)
  for trying `simulator load` by hand.
- `docs/PLAN.md`: build plan and progress. `Simulator.md`: product spec.

**The tools (all dev-only)**: `ruff` = lint (style mistakes) and format; `pyright` = type
checker (strict); `pytest` = runs tests; `hypothesis` = generates many test inputs.
Node equivalents: ruff = eslint + prettier, pyright = tsc, pytest = jest, hypothesis =
fast-check. "dev" = like `devDependencies`; `dependencies = []` means no runtime library
yet (libraries like Typer and httpx come with the features that need them).

**Typer** = a library for building command-line programs from plain Python functions
(function name -> command, parameters -> arguments and `--flags`, type hints -> checks).
Like Go's `cobra` or Node's `commander`. Simulator's `simulator` command is built with it.

**`@app.command()`** is a **decorator**: a line above a function that passes the function
to another function when the file is loaded. `@x` above `def f` means `f = x(f)`.
Typer's version saves `f` in `app`'s list of commands (name `f`, parameters read from its
signature) and returns `f` unchanged. Running `app()` later reads the terminal words and
calls the matching saved function. Like registering a route in Express (`app.get(...)`).

**`@app.command()` / `@app.callback()` step by step**: with `()` after the name the
decorator is called in two steps: `app.command()` runs first and returns the real
decorator, which then receives the function: `load = app.command()(load)`. It saves the
function in `app` and returns it unchanged (the "register" kind). `@app.callback()` works
the same, but its saved function is run by Typer before any command, and having it keeps
the command name (`simulator load FILE`) when there is only one command.

**Decorator in general**: a function that takes a function and returns a function (often a
wrapper that adds behaviour before/after the call, like Node middleware). `@x` above
`def f` is shorthand for `f = x(f)`. Two kinds: registers `f` and returns it unchanged
(Typer's `@app.command()`), or returns a wrapper that replaces `f` (timing, logging).

**What `uv add typer` put in `uv.lock`**: `typer` (direct) and what it needs: `rich`
(coloured terminal output; needs `markdown-it-py`, `mdurl`, `pygments`), `pydantic`
(needs `pydantic-core`, `annotated-types`, `typing-inspection`), `shellingham`,
`annotated-doc`, `typing-extensions`, and `colorama` (Windows only). Also
`[project.scripts] simulator = "simulator.command_line:app"` in `pyproject.toml` makes the
terminal command `simulator` call `app` in `simulator/command_line.py`.

**Direct vs indirect libraries**: `pyproject.toml` lists only what we ask for (direct).
`uv.lock` also lists what those libraries need themselves (indirect), like Node's nested
`node_modules`. Example: `pydantic` is in `uv.lock` only because `typer` needs it; we did
not add it ourselves. If our own code imports a library, add it directly.

## `src/simulator/command_line.py` overview (the front door)

Job: read the `simulator load FILE` command, call the worker, print the result. It does
no real work itself; `api_description.py` does.
Top to bottom: imports -> `app = typer.Typer(...)` (the command list) -> `JsonOption`
(the `--json` flag, defined once) -> `@app.callback() main` (the program's `--help` text)
-> `@app.command() load(...)` (the one command) -> helpers `fail`, `summary_text`,
`endpoint_text`, `schema_label`, `yes_no`.
Flow of `load`: `load_description(file)` (error -> `fail`, exit code 1) -> no `--endpoint`:
print the summary (or all as JSON) -> with `--endpoint`: find it, print it (or as JSON).
`--json` = machine-readable output for programs; default = text for people.

## `load()` in `command_line.py`, with its try/except

Flow of `simulator load FILE [--endpoint ID] [--json]`:
1. Typer calls `main()` (empty callback), then `load(file, endpoint, json_output)`.
2. `try: description = load_description(file)` runs the worker in `api_description.py`:
   `read_document` (file exists? under 20 MB? valid JSON? one object?) -> `read_format`
   (`swagger: 2.0` / `openapi: 3.0.x` / `3.1.x`, else error) -> read endpoints -> a
   `Description` (format, title, version, endpoints, defs).
3. Any problem inside raises `DescriptionError("a sentence saying what to fix")`.
4. `except DescriptionError as error: fail(str(error), json_output)`: `try` = attempt,
   `except` = what to do if that error type is raised (like JS try/catch).
   `fail` prints the sentence (stderr, or `{"error": ...}` with `--json`) and raises
   `typer.Exit(code=1)` (exit code 1 = failure; 0 = success). It is typed `NoReturn`.
5. No `--endpoint`: print `summary_text` (or all as JSON). With it: `description.endpoint(id)`
   finds one (None if missing -> `fail`), then print `endpoint_text` (or JSON).
`return` with no value just ends the function early.

**Key terms of an `Endpoint`**: *endpoint* = one action of an API = method + path
(`GET /tasks`). *reply* = what the API sends back: a status code (201, 404) plus an
optional body. `simulated` = "can Simulator make a fake of this endpoint?" (True when its
input and replies are JSON; False for e.g. file downloads, with the reason in
`not_simulated_reason`). It is not in the JSON file: the loader works it out while reading.
`problems` = a list of reason strings collected per endpoint; `simulated = not problems`
(no reason found -> True).

**Schema** = a description of the shape of a JSON value (its type, and for objects its
fields), written as a dict: `{"type": "object", "properties": {"id": {"type": "integer"}}}`.
`body` and each reply hold one. **`schema_label(schema)`** = a short human name for a
schema, tried in order: (1) its `title`; (2) the last part of its `$ref` (a pointer like
`"#/$defs/Task"`; `.rsplit("/", 1)[-1]` keeps the part after the last `/`); (3) if
`type` is `array` and it has `items`, `"array of "` + the label of the items (the function
calls itself: recursion); (4) its `type`, or the word `schema`. `schema.get("x")` returns
`None` instead of an error when the key is missing. `isinstance(v, str)` checks that `v`
is text. `as_object(v)` turns a non-dict into `{}`.

**set / frozenset**: a `set` is a collection of unique items with no order (`{"get", "head"}`;
no duplicates; fast `x in the_set`). A `frozenset` is a set that cannot be changed after it
is made (like JS `Object.freeze`). Ours: `READ_ONLY_METHODS = frozenset({"get", "head",
"options"})`, used as `writes = method not in READ_ONLY_METHODS`: any method not in that
list changes data.

**`NON_SHAPE_KEYS`** (in `api_description.py`): a frozenset of schema key names that do not
change which data is valid (`example`, `examples`, `xml`, `externalDocs`, `discriminator`,
`nullable`, `x-nullable`). In `SchemaCleaner.clean`, any key in it (or starting with
`x-`) is skipped (`continue`), so the common form holds only the shape and the three file
formats (which differ in such extras) load to equal results. `nullable` / `x-nullable`
are not lost: they are rewritten as a `"null"` type (`allow_null`).

**`SUBSCHEMA_KEYS`, `SUBSCHEMA_LIST_KEYS`, `SUBSCHEMA_MAP_KEYS`**: a schema can hold other
schemas inside it. These three frozensets name the keys whose value contains schemas:
one schema (`items`, `not`, ...), a list of schemas (`allOf`, `anyOf`, `oneOf`,
`prefixItems`), or a name -> schema map (`properties`, ...). `clean_inside(key, item)`
checks which group a key is in and calls `self.clean(...)` on each inner schema
(recursion: `clean` -> `clean_inside` -> `clean`), so cleaning reaches every level. Any
other key (`type`, `enum`, `minimum`) is kept as it is.

**`class DescriptionError(Exception)`**: a new error type of our own. `(Exception)` means
it inherits everything an error already has (a message, `raise`, `except`), so the body
needs no functions, only a docstring. Its value is its **name**: `raise DescriptionError(
"sentence")` in the loader, and `except DescriptionError` in `load()` catches only these
file problems, not other bugs. Like JS `class DescriptionError extends Error {}`.

**Endpoint objects are built, not checked against requests**: no API call is sent in step
0.2. `Endpoint` records what the description FILE says about each endpoint. Data flow:
JSON file -> `read_document` (Python dict) -> `read_*_endpoints` loops over paths and
methods, builds `Parameter`s, `body`, `replies`, `problems` -> `make_endpoint` -> frozen
`Endpoint` -> list inside `Description` -> `load()` prints it. Later steps (fake server,
comparison) will use these objects.

**`Description`** = the whole file in the common form: `format` ("openapi-3.0"), `title`,
`version` (the API's own, from `info`), `endpoints` (tuple of `Endpoint`, sorted by path
then method), `defs`, and the method `endpoint(id)` that finds one endpoint (or None).
**`defs`** = "definitions": the schemas that contain themselves (a `Task` whose `subtasks`
are `Task`s), stored once by name. Why: the loader replaces every `$ref` pointer with the
schema it points to, but doing that for a self-containing schema would never end, so the
inner spot becomes `{"$ref": "#/$defs/Task"}` and the full schema lives in `defs["Task"]`.
Built in `SchemaCleaner.clean_reference` (marks a pointer "in progress"; meeting it again
inside itself = recursive), passed into `Description(defs=cleaner.defs)` at the end of
`load_description`. `defs` is `{}` when no schema contains itself. Its printed JSON appears
only with `--json`.

**`Description.endpoint(endpoint_id)`**: a method (a function inside a class; `self` = the
object it is called on) that finds one endpoint by its id text, or returns `None`. Steps:
`endpoint_id.strip().partition(" ")` splits at the first space into method / separator /
path (`"post /tasks"` -> `"post"`, `" "`, `"/tasks"`; `_` = a value we ignore); build
`wanted = METHOD.upper() + " " + path.strip()` (so `post` equals `POST`); loop over
`self.endpoints` and return the first whose `.id == wanted`; else `None`. Called by
`load()` for `--endpoint`.

**`load_description(path)`**: the main function of `api_description.py`; turns one file
(Swagger 2.0 / OpenAPI 3.0 / 3.1) into one `Description`. Flow: (1) `read_document(path)`:
checks the file exists, is under 20 MB, is valid JSON and a JSON object (else
`DescriptionError`); returns a dict. (2) `read_format(document, path)`: looks at the
`swagger` / `openapi` key, returns `"swagger-2.0"`, `"openapi-3.0"` or `"openapi-3.1"`.
(3) `info = as_object(document.get("info"))`: the file's title/version block (`{}` if
missing). (4) `cleaner = SchemaCleaner(document, path)`: an object that turns every schema
into the common form and collects `defs`. (5) swagger -> `read_swagger_endpoints`, else
`read_openapi_endpoints`: each returns a list of `Endpoint`. (6) `endpoints.sort(key=lambda
endpoint: (endpoint.path, METHODS.index(endpoint.method.lower())))`: `.sort` sorts the list
in place (returns nothing). `key=` takes a function that gives each item its sort value
(JS has no `key`; it uses a comparator). `lambda x: ...` = JS arrow function `x => ...`,
no `return` needed. The value is a tuple, compared part by part: path first, then the
method's position in `METHODS` (`"post"` -> 2), so same-path endpoints go get, put, post,
delete... not alphabetical. Result is the same order for every file format. (7) Return
`Description(format, title, version, endpoints=tuple(endpoints), defs=cleaner.defs)`.
`str(info.get("title", ""))`: `.get(key, default)` = value or `""` if missing; `str()`
makes sure it is text. Called by `load()` in `command_line.py`.

**`read_document(path)`**: step 1 of `load_description`; turns a file path into a dict, or
raises `DescriptionError`. Checks in order, each one stops on failure: (1) `path.is_file()`
false -> "does not exist or is not a file". (2) `path.stat().st_size` (size in bytes) over
`MAX_FILE_BYTES` -> "too large" (`//` = whole-number division, bytes -> MB). (3)
`path.read_text(encoding="utf-8")` reads the file as one string. (4) `try: json.loads(text)`
turns the string into Python data (JS `JSON.parse`); on `json.JSONDecodeError as error`: if
the text starts with `openapi:`, `swagger:` or `---` it is YAML -> "looks like YAML, convert
to JSON", else "is not valid JSON: ...". `raise ... from error` keeps the original error as
the cause. `text.lstrip()` removes leading spaces/newlines; `startswith((a, b, c))` accepts
a tuple = "starts with any of these". (5) `isinstance(document, dict)` false (e.g. a JSON
list) -> "must hold one JSON object". (6) `cast(dict[str, object], document)` only tells
pyright the type; it does nothing at run time. Returns the dict.

**`read_format(document, path)`**: step 2 of `load_description`; says which version the file
is. `document.get("swagger")` and `document.get("openapi")` give the value or `None` (no
crash if the key is missing). Checks in order: `swagger == "2.0"` -> `"swagger-2.0"`;
`openapi` is text starting with `"3.0"` -> `"openapi-3.0"`; starting with `"3.1"` ->
`"openapi-3.1"`. `isinstance(openapi, str)` comes first so `.startswith` is never called on
a number or `None`. Nothing matched -> `found = swagger or openapi or "no version"` (first
value that is not empty/None) and `raise DescriptionError(... says {found!r} ...)`; `!r`
prints the value with quotes (`'2.5'`), so empty or odd values are visible. `path` is only
used in the error message. Note: the docstring says "from the first key of the file", but
the code looks the two keys up by name, wherever they are at the top level.

**`read_swagger_endpoints(document, cleaner)`**: step 5 (Swagger 2.0 files). Returns a list
of `Endpoint`. Swagger 2.0 facts: request body is a parameter with `"in": "body"`; path/query
parameter schemas sit directly on the parameter; media types are named once per file
(`consumes` = what the API accepts, `produces` = what it sends back), an endpoint may
override; a reply cannot have its own media type. Flow: (1) `file_consumes` / `file_produces`
= `strings(document.get(...)) or ["application/json"]` (`a or b`: `b` when `a` is empty, so
JSON is the default). Example: file says `"consumes": ["application/json"]`,
`"produces": ["application/json"]` -> every endpoint sends/returns JSON; one upload
endpoint says `"consumes": ["multipart/form-data"]` -> only that endpoint is "not JSON".
`file_consumes`/`file_produces` = the file-wide default; the endpoint's own value wins. (2) `for path, method, path_item, operation in operations(document)`
(JS destructuring): one pass per endpoint; the endpoint's own `consumes` / `produces`
replace the file's. (3) New empty `parameters`, `body = None`, `problems = []`. (4) For each
parameter from `merged_parameters`: `in` is path/query -> schema = dict comprehension
copying only keys in `SWAGGER_PARAMETER_SCHEMA_KEYS` from the parameter, cleaned, wrapped
by `make_parameter`; `in` is body -> `body = cleaner.clean(raw.get("schema"))`, and if no
`consumes` entry is JSON, add problem "request body is X, not JSON"; `in` is formData ->
add the same kind of problem (`next((m for m in consumes if not is_json(m)), "a form")` =
first non-JSON media type, else "a form"). (5) For each `status, raw_reply` in
`reply_entries(operation)`: `reply = cleaner.follow_references(raw_reply)` (resolves a
`$ref`), then four cases in order: no `schema` -> `replies[status] = None` (e.g. 204);
success status and no JSON in `produces` -> problem + `None`; schema type is `file` ->
problem + `None`; else `replies[status] = cleaner.clean(reply["schema"])`. Error statuses
(`is_error_status`) skip the `produces` check because Swagger cannot say, and real APIs send
errors as JSON. (6) `make_endpoint(...)` builds the `Endpoint` from the parts and
`problems` (`simulated = no problems`); append it. Return the list.

**`endpoint_text(endpoint)`**: builds the text for `--endpoint ID`. It first makes three
strings, then joins nine lines. `parameters`: `", ".join(f"name (location, required)" for
each parameter)`. `replies`: for each `status, schema` pair in `endpoint.replies.items()`
(a dict: status -> schema or None), `"201 Task"` if a schema exists, else just the status
(`"204"`). `simulated`: `"yes"` or `"no (reason)"`. `x if cond else y` = JS `cond ? x : y`.
`a or '-'` = `a`, unless `a` is empty/None, then `'-'`. `yes_no(bool)` -> "yes"/"no".
`schema_label(schema)` gives a short name: its `title`, else the last part of its `$ref`
(`"#/$defs/Task".rsplit("/", 1)[-1]` = "Task"), else "array of X" (calls itself for the
items), else its `type`.

**`summary_text(file, description)`**: builds the text `simulator load FILE` prints.
Step 1: list comprehension `[e for e in description.endpoints if not e.simulated]` = JS
`.filter(...)`. Step 2: a list `lines` with two f-strings (`f"...{x}..."` puts values in
text, like JS template strings): title line and counts line. Step 3: if any are not
simulated, `lines.append(...)` the header and `lines += [...]` one line each. Step 4:
`"\n".join(lines)` glues the lines with newlines into one string. It returns the string;
`load` prints it.

**`fail(message, json_output)`**: the one place errors are shown. `--json`: `print` a
`{"error": ...}` JSON line to stdout (a program reading output always gets JSON). Else:
`typer.echo(message, err=True)` to stderr (the error stream; a person sees it, and it is
kept out of normal output when piped). Then `raise typer.Exit(code=1)` stops the program
quietly (no traceback) with exit code 1 (0 = success, non-zero = failure; scripts check
it). `-> NoReturn` = never returns, so pyright knows code after a `fail(...)` call is not
reached.

## All the ways to sort in Python

- `items.sort()`: sorts the list itself, returns `None`. `sorted(items)`: returns a NEW
  sorted list, leaves the original; works on any collection (list, tuple, dict, set).
- `reverse=True`: biggest first. `sorted(items, reverse=True)`.
- `key=function`: the function gives each item its sort value (JS has no `key`; it uses a
  comparator). The function can be a built-in (`key=len`, `key=str.lower`), your own `def`,
  a `lambda` (`lambda x: x.age`), or `operator.attrgetter("age")` / `itemgetter(1)`.
- Several values: return a tuple; compares part by part: `key=lambda x: (x.path, x.age)`.
- Mixed directions: negate a number (`key=lambda x: (x.path, -x.age)`), or sort twice (sort is
  stable: equal items keep their earlier order).
- JS-style comparator: `functools.cmp_to_key(lambda a, b: a.age - b.age)`; rarely needed.
- Dict: `sorted(d)` sorts keys; `sorted(d.items(), key=lambda pair: pair[1])` sorts by value.
- Default order with no `key`: numbers by value, strings alphabetically (capitals first),
  tuples part by part.
- `min(items, key=...)` / `max(items, key=...)` take the same `key`.
In this project: `endpoints.sort(key=lambda endpoint: (endpoint.path, METHODS.index(...)))`.

## try / except / else / finally (Python's try/catch)

```python
try:        # attempt this
    ...
except ValueError as error:   # JS catch; runs only if that error type is raised
    ...
else:       # runs only if try had NO error
    ...
finally:    # always runs (cleanup), error or not
    ...
```
`raise SomeError("msg")` = JS `throw`. Several `except` blocks can follow one `try`; the
first matching type runs. A `try` needs at least one `except` or a `finally`.
Our code uses `try` + `except DescriptionError` only.

## Imports at the top of `command_line.py`

`import x` brings in a whole module (use as `x.name`); `from x import a, b` brings in just
those names. All four below are in Python's standard library (nothing to install).
- `json` (Node: `JSON.stringify/parse`): `json.dumps(obj)` = Python data -> JSON text,
  `json.loads(text)` = JSON text -> Python data. Why: programs read JSON, not Python
  objects; `--json` output and reading description files both need it.
- `dataclasses` (Go: `struct`): `@dataclass class Endpoint: name: str ...` writes the
  `__init__` and printing for you; `asdict(obj)` -> plain dict. Why: a named, typed
  record is safer than a loose dict (typo `ep.nmae` is caught; `ep["nmae"]` is not).
- `pathlib.Path` (Go: `path/filepath`, Node: `path` + `fs`): a path as an object:
  `Path("a/b.json").exists()`, `.read_text()`, `.name`, `/` joins (`Path("a") / "b"`).
  Why: works on Mac and Windows alike; no string slicing. Typer turns text into `Path`.
- `typing` (TypeScript types): Python has no compile step, so a type hint is just a label
  you write (`age: int`). Python ignores labels when running; `pyright` reads them and
  reports a clash (`age = "ten"`) before you run.
  `Annotated[bool, typer.Option("--json")]` = "a bool" (pyright reads it) + a sticky note
  (Typer reads it and makes a `--json` flag). Python itself ignores the note.
  `typer.Argument(...)` / `typer.Option(...)` do not convert anything: they only create a
  settings note ("plain word by position" / "a `--flag`", plus help text). Typer finds the
  words in the command and converts them to the type. Useful because it replaces
  hand-written `sys.argv` parsing, type conversion, error messages and `--help` text. The `typing` module only holds the
  special labels the built-in names cannot say (`Annotated`, `NoReturn`, ...).
  Do not mix up with dataclass: `dataclass` CREATES a new type (`Endpoint`, a record with
  fields); `typing` only LABELS what type a variable/parameter has (`e: Endpoint`).
  `str | None` = string or nothing; `Annotated[T, note]` = type plus a note for a library
  (Typer reads it for `--flag` and help); `NoReturn` = never returns (`fail` exits).
  Why: catches mistakes before running; also documents the code.
Then `import typer` (library, installed by uv) and `from simulator.api_description import
...` (our own file).

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
