# src/simulator

The code of Simulator. It is **general**: it works for any REST API, and nothing here
names or configures one platform. A platform's own settings are given to it from outside.

## Glossary

| Term | Plain meaning |
| --- | --- |
| REST API | The set of web addresses a system answers, such as `POST /projects/7/tasks` to create a task. |
| Endpoint | One method plus one address pattern: `POST /projects/{project}/tasks`. Its id is written exactly like that. |
| Description file | A JSON file that lists an API's endpoints, their inputs and their replies. The old version of the format is called **Swagger 2.0**; the newer ones are **OpenAPI 3.0** and **3.1**. They say the same things in slightly different ways. |
| Schema | A description of what valid data looks like: "an object with a `title` that is a string". Written in **JSON Schema**, a standard way to write such descriptions. |
| Reference (`$ref`) | A pointer inside a description file, such as `#/definitions/Task`, meaning "the schema written under that name". |
| Common form | Simulator's one way of holding a description, whatever the file's version. Every later part of Simulator reads only the common form. |
| Not simulated | An endpoint Simulator will never fake, because it does not send and receive JSON (a file download, a form upload). |
| Command line (CLI) | The `simulator` program typed in a terminal. Every command also has `--json`, which prints one JSON object for another program to read. |

## What `simulator load tasks.json` does

1. `command_line.py` receives the path and calls `api_description.load_description(path)`.
2. The file is checked (it exists, is under 20 MB, is JSON) and its version is read from
   its top: `"swagger": "2.0"`, `"openapi": "3.0.3"` or `"openapi": "3.1.0"`.
3. For every endpoint, the parts that each version writes differently (where parameters
   are, where the request body is, how replies list their content) are read the way that
   version writes them.
4. Every schema then goes through the same cleaning: references are replaced by what
   they point to, "can be null" is written one way, and keys that do not describe shape
   are dropped.
5. The result is a `Description`: the file's version, title and API version, plus one
   `Endpoint` per method and path, sorted by path then method.
6. `command_line.py` prints a summary, one endpoint, or everything as JSON.

## Files

| File | Holds |
| --- | --- |
| `__init__.py` | Marks this folder as the `simulator` Python package. |
| `command_line.py` | The command line. Each command reads its options, calls the code that does the work, and prints. |
| `api_description.py` | The description loader: any supported description file in, the common form out. |
