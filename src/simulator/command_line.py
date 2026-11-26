"""The `simulator` command line.

One function per command. A command reads its options, calls the code that does the work,
and prints the result: as text for a person, or with `--json` as one JSON object for a
program. The work itself lives in the other modules, so tests and later commands reuse it.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from simulator.api_description import (
    FORMAT_NAMES,
    Description,
    DescriptionError,
    Endpoint,
    Schema,
    as_object,
    load_description,
)

app = typer.Typer(
    help="Builds measured fakes of REST APIs and tests AI agents on them.",
    no_args_is_help=True,
    add_completion=False,
)

JsonOption = Annotated[bool, typer.Option("--json", help="Print one JSON object instead of text.")]
"""The `--json` flag, defined once and used by every command."""


@app.callback()
def main() -> None:
    """Builds measured fakes of REST APIs and tests AI agents on them."""


@app.command()
def load(
    file: Annotated[Path, typer.Argument(help="An API description file (JSON).")],
    endpoint: Annotated[
        str | None,
        typer.Option(help='Show one endpoint, for example "POST /projects/{project}/tasks".'),
    ] = None,
    json_output: JsonOption = False,
) -> None:
    """Read a description file into the common form and show it.

    Without `--endpoint`, prints a summary: the file's format, how many endpoints it has,
    and which ones are not simulated and why. With `--endpoint`, prints that endpoint. With
    `--json`, prints the whole common form (or the one endpoint) as JSON.

    Example: `simulator load tasks.json --endpoint "POST /projects/{project}/tasks"` prints
    the endpoint's name, kind, whether it writes and needs a key, its parameters, its body
    and its replies. A missing file or unknown endpoint prints a sentence and exits with 1.
    """
    try:
        description = load_description(file)
    except DescriptionError as error:
        fail(str(error), json_output)

    if endpoint is None:
        if json_output:
            print(json.dumps(asdict(description), indent=2))
        else:
            print(summary_text(file, description))
        return
    
    found = description.endpoint(endpoint)
    
    if found is None:
        fail(
            f"{file} has no endpoint {endpoint!r}. An endpoint is a method and a path, "
            'for example "GET /items/{item}"; run without --endpoint to see the file\'s summary.',
            json_output,
        )
        
    if json_output:
        print(json.dumps(asdict(found), indent=2))
    else:
        print(endpoint_text(found))


def fail(message: str, json_output: bool) -> NoReturn:
    """Report an error the user can act on and stop with exit code 1.

    With `--json` the error is printed as `{"error": "<message>"}` on standard output, so a
    program reading the output always gets JSON; otherwise it goes to standard error.
    Example: `fail("tasks.json does not exist or is not a file.", False)`.
    """
    if json_output:
        print(json.dumps({"error": message}))
    else:
        typer.echo(message, err=True)
    raise typer.Exit(code=1)


def summary_text(file: Path, description: Description) -> str:
    """The text `simulator load FILE` prints.

    Example:
        tasks.json: OpenAPI 3.0, "Task tracker" version 1.0.0
        endpoints: 8 (6 simulated, 2 not simulated)
        not simulated:
          GET /projects/{project}/files/{file}: reply 200 is application/octet-stream, not JSON
    """
    not_simulated = [endpoint for endpoint in description.endpoints if not endpoint.simulated]
    lines = [
        f'{file.name}: {FORMAT_NAMES[description.format]}, "{description.title}" '
        f"version {description.version}",
        f"endpoints: {len(description.endpoints)} "
        f"({len(description.endpoints) - len(not_simulated)} simulated, "
        f"{len(not_simulated)} not simulated)",
    ]
    if not_simulated:
        lines.append("not simulated:")
        lines += [f"  {endpoint.id}: {endpoint.not_simulated_reason}" for endpoint in not_simulated]
    return "\n".join(lines)


def endpoint_text(endpoint: Endpoint) -> str:
    """The text `simulator load FILE --endpoint ID` prints.

    Example:
        POST /projects/{project}/tasks
          name: createTask
          kind: tasks
          writes: yes
          needs key: yes
          parameters: project (path, required)
          body: NewTask
          replies: 201 Task, 404 Error, 422 ValidationError
          simulated: yes
    """
    parameters = ", ".join(
        f"{parameter.name} ({parameter.location}{', required' if parameter.required else ''})"
        for parameter in endpoint.parameters
    )
    replies = ", ".join(
        f"{status} {schema_label(schema)}" if schema is not None else status
        for status, schema in endpoint.replies.items()
    )
    simulated = "yes" if endpoint.simulated else f"no ({endpoint.not_simulated_reason})"
    return "\n".join(
        [
            endpoint.id,
            f"  name: {endpoint.name or '-'}",
            f"  kind: {endpoint.kind}",
            f"  writes: {yes_no(endpoint.writes)}",
            f"  needs key: {yes_no(endpoint.needs_key)}",
            f"  parameters: {parameters or '-'}",
            f"  body: {schema_label(endpoint.body) if endpoint.body is not None else '-'}",
            f"  replies: {replies or '-'}",
            f"  simulated: {simulated}",
        ]
    )


def schema_label(schema: Schema) -> str:
    """A short name for a schema: its title, the name it points to, or its type.

    Example: `{"title": "Task", ...}` gives "Task"; `{"$ref": "#/$defs/Task"}` gives
    "Task"; `{"type": "array", "items": {"title": "Task"}}` gives "array of Task".
    """
    title = schema.get("title")
    if isinstance(title, str):
        return title
    reference = schema.get("$ref")
    if isinstance(reference, str):
        return reference.rsplit("/", 1)[-1]
    items = as_object(schema.get("items"))
    if schema.get("type") == "array" and items:
        return f"array of {schema_label(items)}"
    return str(schema.get("type", "schema"))


def yes_no(value: bool) -> str:
    """Example: True gives "yes", False gives "no"."""
    return "yes" if value else "no"
