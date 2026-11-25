## Build `fio`: CLI Wrapper On Top Of `fio-sdk`

### Summary
Build a focused CLI (`fio ...`) that calls `fio-sdk` directly.
CLI owns UX, argument parsing, output formatting, config loading, and exit behavior.
SDK owns HTTP, auth wiring, API models, and endpoint methods.

### Goals
- Ship a reliable CLI for common PrUn workflows quickly.
- Reduce custom API client code to near-zero.
- Keep upgrade path simple: bump `fio-sdk`, adapt thin wrappers when needed.

### Non-Goals
- No OpenAPI ingestion or codegen in this repo.
- No duplicate HTTP stack unless SDK has a hard gap.

### Architecture
- **CLI layer (this repo)**
  - Framework: `Typer`.
  - Commands map to intent-oriented tasks (example: `materials list`, `buildings list`, `exchange orderbook`).
  - Parse flags/options and call SDK methods.
  - Output is API response (or cached copy)
  - Centralized error handling and exit codes.
- **SDK layer (`fio-sdk`)**
  - API client/session creation.
  - Auth header behavior.
  - Request/response schemas.
  - Transport retries/timeouts if provided by SDK.

### Command Strategy

Top level commands are:
`list` lists available commands with brief description
`search` finds endpoints/commands by fuzzy term
`get` requires the endpoint as first parameter, without leading/trailing slashes (e.g. `fio get material/resources`)

`get` commands must support every GET endpoint in the SDK.
The CLI does not support any other methods. Only GET.

Command model is hybrid:
- Dynamic core: `fio get <endpoint>` is canonical and must cover all SDK GET endpoints.
- Explicit aliases: intent-oriented commands remain optional thin wrappers for common workflows.
- Single execution path: aliases resolve into the same SDK adapter path used by `get` to prevent drift.

Discovery requirements:
- `fio list`: grouped command and endpoint catalog with short descriptions.
- `fio search <term>`: fuzzy find by endpoint path and description.
- `fio get --help`: generic dynamic usage including query parameter format.
- `fio get <endpoint> --help`: endpoint-specific params/examples when metadata exists.
- Shell completion for endpoint paths on `fio get`.

Endpoint catalog source:
- SDK currently does not expose a first-class endpoint registry API.
- Generate and ship a local manifest (example: `endpoints.json`) from installed SDK introspection.
- Manifest includes at minimum: path, method, params, summary/description, and auth hint.

Validation and drift control:
- `get` validates endpoint against manifest (no arbitrary blind paths).
- CI fails when SDK GET endpoints change and manifest was not regenerated.
- SDK version bumps require manifest refresh in same change.

`AGENTS.md` must have an index of available commands with brief description of purpose, params, and data returned.

### Config Strategy
- `FIO_API_KEY` in .env file
- Keep secrets out of output/logs.

### Error Model
Map SDK/runtime failures to consistent CLI exits/messages:
- `2`: CLI usage/validation error.
- `3`: auth/config error.
- `4`: upstream/API not found or invalid request.
- `5`: transport/network/timeout.
- `1`: unknown internal failure.

### Operational Notes
- Pin SDK version in `uv.lock`; upgrade intentionally.
- Track SDK breaking changes in one adapter module, not across commands.
- Keep command surface small until real usage shows what to expand.

### Acceptance Criteria
- CLI performs read operations via `fio-sdk` only.
- Initial command set works with env-based auth.
- Errors are concise and deterministic.
