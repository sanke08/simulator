"""The description loader: reads an API's description file into Simulator's common form.

An API's description file lists its endpoints, their inputs and their replies. Three
versions of the format exist (Swagger 2.0, OpenAPI 3.0, OpenAPI 3.1) and they say the same
things in slightly different places and words. This file reads all three and returns one
`Description`, so every later part of Simulator reads one shape and never cares which
version a platform publishes. It is pure code: no network, no model, no platform.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

type Schema = dict[str, object]
"""A JSON Schema, as a plain dictionary: `{"type": "string", "format": "date-time"}`."""

MAX_FILE_BYTES = 20 * 1024 * 1024
"""The largest description file accepted (20 MB). Real ones are about 1 MB; a far larger
file is more likely a mistake or a hostile input than a real API."""

FORMAT_NAMES = {
    "swagger-2.0": "Swagger 2.0",
    "openapi-3.0": "OpenAPI 3.0",
    "openapi-3.1": "OpenAPI 3.1",
}
"""Each supported format's id in the common form, and its name for people."""

METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
"""The HTTP methods a description file can list under one path, in a fixed order."""

READ_ONLY_METHODS = frozenset({"get", "head", "options"})
"""Methods that only read. Every other method may change data, so it counts as a write."""

NON_SHAPE_KEYS = frozenset(
    {"example", "examples", "xml", "externalDocs", "discriminator", "nullable", "x-nullable"}
)
"""Schema keys that do not change which data is valid, so the common form drops them.
`nullable` and `x-nullable` are not lost: they are rewritten as a `"null"` type."""

SUBSCHEMA_KEYS = frozenset(
    {
        "items",
        "additionalProperties",
        "not",
        "contains",
        "if",
        "then",
        "else",
        "propertyNames",
        "unevaluatedItems",
        "unevaluatedProperties",
    }
)
"""Schema keys whose value is itself one schema (when it is an object)."""

SUBSCHEMA_LIST_KEYS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
"""Schema keys whose value is a list of schemas."""

SUBSCHEMA_MAP_KEYS = frozenset({"properties", "patternProperties", "dependentSchemas"})
"""Schema keys whose value maps names to schemas."""

SWAGGER_PARAMETER_SCHEMA_KEYS = (
    "type",
    "format",
    "items",
    "enum",
    "default",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "multipleOf",
    "x-nullable",
)
"""Swagger 2.0 writes a path or query parameter's schema directly on the parameter. These
are the keys that belong to that schema; the rest (name, in, description) do not."""


class DescriptionError(Exception):
    """A description file that cannot be read. The message says what is wrong and where."""


@dataclass(frozen=True)
class Parameter:
    """One path or query parameter of an endpoint.

    Example: in `GET /projects?page=2`, `page` is
    `Parameter(name="page", location="query", required=False,
    schema={"type": "integer", "minimum": 1})`.
    """

    name: str
    location: str
    required: bool
    schema: Schema


@dataclass(frozen=True)
class Endpoint:
    """One endpoint (a method and a path) in the common form.

    Example: `POST /projects/{project}/tasks` has `name="createTask"`, `kind="tasks"`,
    `writes=True`, `needs_key=True`, one path parameter `project`, a `body` schema titled
    `NewTask`, and `replies` `{"201": <Task>, "404": <Error>, "422": <ValidationError>}`.
    A reply with no body (`204`) maps to `None`. `simulated` is False, with a reason, when
    the endpoint does not send and receive JSON.
    """

    id: str
    method: str
    path: str
    name: str | None
    kind: str
    writes: bool
    needs_key: bool
    parameters: tuple[Parameter, ...]
    body: Schema | None
    replies: dict[str, Schema | None]
    simulated: bool
    not_simulated_reason: str | None


@dataclass(frozen=True)
class Description:
    """A whole description file in the common form.

    `format` is one of `FORMAT_NAMES`. `endpoints` are sorted by path, then by method.
    `defs` holds the schemas that contain themselves (a task whose subtasks are tasks);
    every other reference has been replaced by the schema it pointed to.
    """

    format: str
    title: str
    version: str
    endpoints: tuple[Endpoint, ...]
    defs: dict[str, Schema]

    def endpoint(self, endpoint_id: str) -> Endpoint | None:
        """Find one endpoint by its id; the method may be written in any case.

        Example: `description.endpoint("post /projects/{project}/tasks")` returns the
        create-task endpoint; an id that is not in the file returns None.
        """
        method, _, path = endpoint_id.strip().partition(" ")
        wanted = f"{method.upper()} {path.strip()}"
        for endpoint in self.endpoints:
            if endpoint.id == wanted:
                return endpoint
        return None


def load_description(path: Path) -> Description:
    """Read one description file into the common form.

    Called by `simulator load` and by every later step that needs an API's endpoints.
    Raises DescriptionError, with a sentence saying what to fix, when the file is missing,
    too large, not JSON, of an unsupported version, or has a reference to nothing.

    Example: `load_description(Path("task-tracker-swagger-2.0.json"))` and
    `load_description(Path("task-tracker-openapi-3.1.json"))`, two files describing the same API,
    return equal descriptions apart from `format`.
    """
    document = read_document(path)
    file_format = read_format(document, path)
    info = as_object(document.get("info"))
    cleaner = SchemaCleaner(document, path)

    if file_format == "swagger-2.0":
        endpoints = read_swagger_endpoints(document, cleaner)
    else:
        endpoints = read_openapi_endpoints(document, cleaner)
    
    endpoints.sort(key=lambda endpoint: (endpoint.path, METHODS.index(endpoint.method.lower())))
    
    return Description(
        format=file_format,
        title=str(info.get("title", "")),
        version=str(info.get("version", "")),
        endpoints=tuple(endpoints),
        defs=cleaner.defs,
    )


def read_document(path: Path) -> dict[str, object]:
    """Read the file as one JSON object, refusing anything that cannot be a description.

    Example: a 25 MB file, a YAML file or a JSON list each raise DescriptionError.
    """

    if not path.is_file():
        raise DescriptionError(f"{path} does not exist or is not a file.")
    
    size = path.stat().st_size
    
    if size > MAX_FILE_BYTES:
        raise DescriptionError(
            f"{path} is {size // (1024 * 1024)} MB; description files larger than "
            f"{MAX_FILE_BYTES // (1024 * 1024)} MB are refused."
        )
    
    text = path.read_text(encoding="utf-8")
    
    try:
        document: object = json.loads(text)
    except json.JSONDecodeError as error:
        start = text.lstrip()
        if start.startswith(("openapi:", "swagger:", "---")):
            raise DescriptionError(
                f"{path} looks like YAML; Simulator reads JSON description files. "
                "Convert it to JSON first."
            ) from error
        raise DescriptionError(f"{path} is not valid JSON: {error}.") from error
    
    if not isinstance(document, dict):
        raise DescriptionError(f"{path} must hold one JSON object at its top.")
    
    return cast(dict[str, object], document)


def read_format(document: dict[str, object], path: Path) -> str:
    """Tell which version of the format a file uses, from the first key of the file.

    Example: `{"swagger": "2.0"}` gives "swagger-2.0"; `{"openapi": "3.0.3"}` gives
    "openapi-3.0"; `{"openapi": "3.1.0"}` gives "openapi-3.1"; anything else raises
    DescriptionError.
    """

    swagger = document.get("swagger")
    openapi = document.get("openapi")
    
    if swagger == "2.0":
        return "swagger-2.0"
    
    if isinstance(openapi, str) and openapi.startswith("3.0"):
        return "openapi-3.0"
    
    if isinstance(openapi, str) and openapi.startswith("3.1"):
        return "openapi-3.1"
    
    found = swagger or openapi or "no version"
    
    raise DescriptionError(
        f"{path} says {found!r}; Simulator reads Swagger 2.0, OpenAPI 3.0 and OpenAPI 3.1."
    )


def read_swagger_endpoints(document: dict[str, object], cleaner: SchemaCleaner) -> list[Endpoint]:
    """Read every endpoint of a Swagger 2.0 file.

    Swagger 2.0 keeps the request body as a parameter with `"in": "body"`, writes path and
    query parameter schemas directly on the parameter, and states media types once for the
    file (`consumes`, `produces`), which an endpoint may override. It cannot give one reply
    its own media type, so `produces` is read as the type of the successful replies; an
    error reply with a schema is read as JSON, which is how real APIs send errors.

    Example: a parameter `{"name": "page", "in": "query", "type": "integer"}` becomes
    `Parameter("page", "query", False, {"type": "integer"})`.
    """
    
    file_consumes = strings(document.get("consumes")) or ["application/json"]
    file_produces = strings(document.get("produces")) or ["application/json"]

    endpoints: list[Endpoint] = []
    
    for path, method, path_item, operation in operations(document):
        consumes = strings(operation.get("consumes")) or file_consumes
        produces = strings(operation.get("produces")) or file_produces

        parameters: list[Parameter] = []
        body: Schema | None = None
        problems: list[str] = []

        for raw in merged_parameters(path_item, operation, cleaner):
            location = raw.get("in")
            if location in ("path", "query"):
                schema = {key: raw[key] for key in SWAGGER_PARAMETER_SCHEMA_KEYS if key in raw}
                parameters.append(make_parameter(raw, cleaner.clean(schema)))
            elif location == "body":
                body = cleaner.clean(raw.get("schema"))
                if not any(is_json(media) for media in consumes):
                    problems.append(f"request body is {consumes[0]}, not JSON")
            elif location == "formData":
                form_type = next((media for media in consumes if not is_json(media)), "a form")
                problems.append(f"request body is {form_type}, not JSON")
        
        replies: dict[str, Schema | None] = {}

        for status, raw_reply in reply_entries(operation):
            reply = cleaner.follow_references(raw_reply)
            if "schema" not in reply:
                replies[status] = None
            elif not is_error_status(status) and not any(is_json(media) for media in produces):
                problems.append(f"reply {status} is {produces[0]}, not JSON")
                replies[status] = None
            elif cleaner.follow_references(reply["schema"]).get("type") == "file":
                problems.append(f"reply {status} is a file, not JSON")
                replies[status] = None
            else:
                replies[status] = cleaner.clean(reply["schema"])
        endpoints.append(
            make_endpoint(document, path, method, operation, parameters, body, replies, problems)
        )
    return endpoints


def read_openapi_endpoints(document: dict[str, object], cleaner: SchemaCleaner) -> list[Endpoint]:
    """Read every endpoint of an OpenAPI 3.0 or 3.1 file.

    OpenAPI 3 keeps the request body in `requestBody` and each reply's body under
    `content`, keyed by media type (`application/json`, `multipart/form-data`).

    Example: a reply `{"content": {"application/octet-stream": {...}}}` makes the endpoint
    "not simulated", with the reason "reply 200 is application/octet-stream, not JSON".
    """
    endpoints: list[Endpoint] = []
    for path, method, path_item, operation in operations(document):

        parameters: list[Parameter] = []
        body: Schema | None = None
        problems: list[str] = []

        for raw in merged_parameters(path_item, operation, cleaner):
            if raw.get("in") in ("path", "query"):
                parameters.append(make_parameter(raw, cleaner.clean(raw.get("schema", {}))))

        if "requestBody" in operation:
            content = as_object(cleaner.follow_references(operation["requestBody"]).get("content"))
            json_type = next((media for media in content if is_json(media)), None)
            if json_type is not None:
                body = cleaner.clean(as_object(content[json_type]).get("schema", {}))
            elif content:
                problems.append(f"request body is {next(iter(content))}, not JSON")

        replies: dict[str, Schema | None] = {}
        
        for status, raw_reply in reply_entries(operation):
            content = as_object(cleaner.follow_references(raw_reply).get("content"))
            json_type = next((media for media in content if is_json(media)), None)
            if json_type is not None:
                replies[status] = cleaner.clean(as_object(content[json_type]).get("schema", {}))
            else:
                replies[status] = None
                if content:
                    problems.append(f"reply {status} is {next(iter(content))}, not JSON")
        endpoints.append(
            make_endpoint(document, path, method, operation, parameters, body, replies, problems)
        )
    return endpoints


def operations(
    document: dict[str, object],
) -> list[tuple[str, str, dict[str, object], dict[str, object]]]:
    """List every (path, method, path item, operation) in the file, in file order.

    A path item is everything written under one path; an operation is one method of it.
    Example: `"/status": {"get": {...}}` gives `("/status", "get", <path item>, <operation>)`.
    """
    found: list[tuple[str, str, dict[str, object], dict[str, object]]] = []
    for path, raw_item in as_object(document.get("paths")).items():
        path_item = as_object(raw_item)
        for method in METHODS:
            if method in path_item:
                found.append((path, method, path_item, as_object(path_item[method])))
    return found


def merged_parameters(
    path_item: dict[str, object], operation: dict[str, object], cleaner: SchemaCleaner
) -> list[dict[str, object]]:
    """Combine the parameters written for the whole path with the operation's own.

    An operation's parameter replaces a path-level one with the same name and location.
    References (`{"$ref": "#/parameters/ProjectParam"}`) are followed first.

    Example: path-level `project` (path) plus operation-level `state` (query) gives both.
    """
    by_key: dict[tuple[str, str], dict[str, object]] = {}
    for raw in [*as_list(path_item.get("parameters")), *as_list(operation.get("parameters"))]:
        parameter = cleaner.follow_references(raw)
        by_key[(str(parameter.get("name")), str(parameter.get("in")))] = parameter
    return list(by_key.values())


def reply_entries(operation: dict[str, object]) -> list[tuple[str, object]]:
    """List an operation's replies as (status, reply), skipping vendor extension keys.

    Example: `{"201": {...}, "404": {...}, "x-note": "..."}` gives the 201 and 404 entries.
    """
    responses = as_object(operation.get("responses"))
    return [
        (str(status), reply) for status, reply in responses.items() if not status.startswith("x-")
    ]


def make_parameter(raw: dict[str, object], schema: Schema) -> Parameter:
    """Build a Parameter; a path parameter is always required, whatever the file says.

    Example: `{"name": "project", "in": "path"}` gives `required=True`.
    """
    location = str(raw.get("in"))
    required = location == "path" or raw.get("required") is True
    return Parameter(name=str(raw.get("name")), location=location, required=required, schema=schema)


def make_endpoint(
    document: dict[str, object],
    path: str,
    method: str,
    operation: dict[str, object],
    parameters: list[Parameter],
    body: Schema | None,
    replies: dict[str, Schema | None],
    problems: list[str],
) -> Endpoint:
    """Build one Endpoint from the parts the format readers found.

    Example: method "post", path "/projects/{project}/tasks" gives id
    "POST /projects/{project}/tasks", kind "tasks" and `writes=True`.
    """
    unique_problems = list(dict.fromkeys(problems))
    name = operation.get("operationId")
    return Endpoint(
        id=f"{method.upper()} {path}",
        method=method.upper(),
        path=path,
        name=name if isinstance(name, str) else None,
        kind=object_kind(path),
        writes=method not in READ_ONLY_METHODS,
        needs_key=needs_key(document, operation),
        parameters=tuple(parameters),
        body=body,
        replies=replies,
        simulated=not unique_problems,
        not_simulated_reason="; ".join(unique_problems) or None,
    )


def object_kind(path: str) -> str:
    """Guess which kind of object an endpoint works on: the last fixed part of its path.

    Example: "/projects/{project}/tasks/{task}" gives "tasks"; "/status" gives "status";
    "/" gives "root".
    """
    fixed_parts = [part for part in path.split("/") if part and not part.startswith("{")]
    return fixed_parts[-1] if fixed_parts else "root"


def needs_key(document: dict[str, object], operation: dict[str, object]) -> bool:
    """Tell whether a caller must send a key, from the endpoint's or the file's security list.

    The list names the ways a caller may prove who they are. An empty list, or an empty
    entry `{}` in it, means "no key is also accepted".

    Example: `"security": [{"Token": []}]` gives True; `"security": []` gives False.
    """
    requirements = operation["security"] if "security" in operation else document.get("security")
    entries = as_list(requirements)
    return bool(entries) and all(as_object(entry) for entry in entries)


def is_error_status(status: str) -> bool:
    """Tell whether a reply status is an error: 4xx, 5xx, or "default" (any other status).

    Example: "404", "500" and "default" are errors; "200" and "204" are not.
    """
    return status == "default" or status.startswith(("4", "5"))


def is_json(media_type: str) -> bool:
    """Tell whether a media type is JSON.

    Example: "application/json", "application/json; charset=utf-8" and
    "application/problem+json" are JSON; "multipart/form-data" is not.
    """
    base = media_type.split(";", 1)[0].strip().lower()
    return base == "application/json" or base.endswith("+json")


class SchemaCleaner:
    """Turns the schemas of one file into common-form schemas.

    It holds the file (to follow references) and what it has already cleaned, so each named
    schema is cleaned once however often it is used. A large real file uses some schemas
    hundreds of times.

    Cleaning a schema means:
      - every reference is replaced by the schema it points to, which gets the
        reference's name as its `title` when it has none ("Task");
      - a schema that contains itself is stored once in `defs` and pointed to with
        `{"$ref": "#/$defs/Task"}`;
      - "can be null" is written one way: `type: [T, "null"]`;
      - an old-style exclusive bound (`minimum: 0, exclusiveMinimum: true`) is written the
        new way (`exclusiveMinimum: 0`);
      - keys that do not describe shape (`x-...`, `example`, `xml`, ...) are dropped.
    """

    def __init__(self, document: dict[str, object], path: Path) -> None:
        self.document = document
        self.path = path
        self.defs: dict[str, Schema] = {}
        self.finished: dict[str, Schema] = {}
        self.in_progress: set[str] = set()
        self.recursive: set[str] = set()

    def clean(self, value: object) -> Schema:
        """Clean one schema and everything inside it.

        Example: `{"type": "string", "x-nullable": true, "example": "hi"}` becomes
        `{"type": ["string", "null"]}`.
        """
        schema = as_object(value)
        reference = schema.get("$ref")
        if isinstance(reference, str):
            cleaned = self.clean_reference(reference)
        else:
            cleaned: Schema = {}
            for key, item in schema.items():
                if key in NON_SHAPE_KEYS or key.startswith("x-"):
                    continue
                cleaned[key] = self.clean_inside(key, item)
            cleaned = unify_exclusive_bounds(cleaned)
            cleaned = unify_type_list(cleaned)
        if schema.get("nullable") is True or schema.get("x-nullable") is True:
            cleaned = allow_null(cleaned)
        return cleaned

    def clean_inside(self, key: str, item: object) -> object:
        """Clean the value of one schema key: schemas inside it are cleaned, other values kept.

        Example: for "properties", each property's schema is cleaned; for "enum", the list
        of allowed values is kept as it is.
        """
        if key in SUBSCHEMA_KEYS and as_object(item):
            return self.clean(item)
        if key in SUBSCHEMA_LIST_KEYS:
            return [self.clean(entry) for entry in as_list(item)]
        if key in SUBSCHEMA_MAP_KEYS:
            return {name: self.clean(entry) for name, entry in as_object(item).items()}
        return item

    def clean_reference(self, pointer: str) -> Schema:
        """Replace a reference by the cleaned schema it points to, once per pointer.

        While a schema is being cleaned, its pointer is "in progress". Meeting the same
        pointer again inside it means the schema contains itself: that inner place becomes
        `{"$ref": "#/$defs/<name>"}` and the finished schema is stored in `defs`.

        Example: `#/definitions/Task`, whose `subtasks` are Tasks, gives
        `{"$ref": "#/$defs/Task"}`, and `defs["Task"]` holds the schema.
        """
        name = pointer.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
        if pointer in self.in_progress:
            self.recursive.add(pointer)
            return {"$ref": f"#/$defs/{name}"}
        if pointer not in self.finished:
            self.in_progress.add(pointer)
            target: Schema = self.clean(self.look_up(pointer))
            self.in_progress.discard(pointer)
            if "title" not in target and "$ref" not in target:
                target = {"title": name, **target}
            if pointer in self.recursive:
                self.defs[name] = target
                target = {"$ref": f"#/$defs/{name}"}
            self.finished[pointer] = target
        return self.finished[pointer]

    def follow_references(self, value: object) -> dict[str, object]:
        """Follow references until reaching a real entry, without cleaning it.

        Used for parameters, request bodies and replies, which are not schemas.
        Example: `{"$ref": "#/responses/NotFound"}` gives the NotFound reply entry.
        """
        entry = as_object(value)
        seen: set[str] = set()
        while isinstance(reference := entry.get("$ref"), str):
            if reference in seen:
                raise DescriptionError(
                    f"{self.path} has references that point to each other in a loop: {reference!r}."
                )
            seen.add(reference)
            entry = as_object(self.look_up(reference))
        return entry

    def look_up(self, pointer: str) -> object:
        """Find what a reference inside the file points to.

        A reference is `#/` followed by keys separated by `/`; `~1` stands for `/` and `~0`
        for `~` inside a key. Example: `#/definitions/Task` gives the Task schema.
        Raises DescriptionError when the reference leaves the file or points to nothing.
        """
        if not pointer.startswith("#/"):
            raise DescriptionError(
                f"{self.path} uses the reference {pointer!r}, which points outside the file; "
                "only references inside the file (starting with #/) are supported."
            )
        node: object = self.document
        for raw_key in pointer[2:].split("/"):
            key = raw_key.replace("~1", "/").replace("~0", "~")
            container = as_object(node)
            if key not in container:
                raise DescriptionError(
                    f"{self.path} uses the reference {pointer!r}, but nothing is written there."
                )
            node = container[key]
        return node


def allow_null(schema: Schema) -> Schema:
    """Make a schema also accept null, written as `type: [T, "null"]`.

    Example: `{"type": "string"}` becomes `{"type": ["string", "null"]}`. A schema with no
    `type` (a reference to a schema that contains itself) becomes
    `{"anyOf": [<schema>, {"type": "null"}]}`.
    """
    types = schema.get("type")
    if isinstance(types, str):
        return {**schema, "type": [types, "null"]}
    type_list = as_list(types)
    if type_list:
        return unify_type_list({**schema, "type": [*type_list, "null"]})
    return {"anyOf": [schema, {"type": "null"}]}


def unify_type_list(schema: Schema) -> Schema:
    """Write a list of types one way: each once, "null" last, one type as a plain string.

    Example: `["null", "string"]` becomes `["string", "null"]`; `["integer"]` becomes
    `"integer"`. A schema whose type is not a list is returned unchanged.
    """
    type_list = as_list(schema.get("type"))
    if not type_list:
        return schema
    names = list(dict.fromkeys(str(name) for name in type_list))
    if "null" in names:
        names = [name for name in names if name != "null"] + ["null"]
    return {**schema, "type": names[0] if len(names) == 1 else names}


def unify_exclusive_bounds(schema: Schema) -> Schema:
    """Write exclusive bounds the new way.

    Swagger 2.0 and OpenAPI 3.0 write "above 0, not 0 itself" as
    `{"minimum": 0, "exclusiveMinimum": true}`; OpenAPI 3.1 writes `{"exclusiveMinimum": 0}`.
    Example: the first becomes the second; `"exclusiveMinimum": false` is simply removed.
    """
    unified = dict(schema)
    for bound, exclusive in (("minimum", "exclusiveMinimum"), ("maximum", "exclusiveMaximum")):
        flag = unified.get(exclusive)
        if flag is True and bound in unified:
            unified[exclusive] = unified.pop(bound)
        elif isinstance(flag, bool):
            del unified[exclusive]
    return unified


def as_object(value: object) -> dict[str, object]:
    """Treat a JSON value as an object; anything that is not an object reads as empty.

    Example: `{"a": 1}` stays itself; `None` or `[1]` give `{}`.
    """
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    """Treat a JSON value as a list; anything that is not a list reads as empty.

    Example: `[1, 2]` stays itself; `None` gives `[]`.
    """
    return cast(list[object], value) if isinstance(value, list) else []


def strings(value: object) -> list[str]:
    """Keep the text entries of a JSON list.

    Example: `["application/json", 3]` gives `["application/json"]`; `None` gives `[]`.
    """
    return [entry for entry in as_list(value) if isinstance(entry, str)]
