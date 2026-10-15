# Configurable Switch Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `sanitize-3.py` with JSON-configured switch inventory, model operations, FTP settings, and manual deployment documentation.

**Architecture:** Keep one executable Python script, but separate configuration data into `config/switches.json`, `config/ftp.json`, and one JSON file per model under `config/sw-models/`. `sanitize-3.py` will load and validate these files, render placeholders, execute ordered Telnet steps, and orchestrate serial all-switch or single-switch operations. The existing scripts remain untouched.

**Tech Stack:** Python 3, `argparse`, `json`, `pathlib`, `unittest`, and the existing `telnetlib-313-and-up` dependency.

**Spec:** `docs/superpowers/specs/2026-10-14-configurable-switch-operations-design.md`

## Global Constraints

- New entry point: `sanitize-3.py`.
- Default configuration directory: `./config`.
- Default inventory file: `switches.json` under the configuration directory.
- Model files live under `config/sw-models/`.
- Credentials and FTP settings are JSON-configured plaintext values and must be documented as sensitive.
- Operations are `sanitize`, `reboot`, `upload`, and `download`.
- An omitted operation target means `all`.
- `--sanitize` performs factory reset and configured file swapping; `--reboot` does not file-swap.
- All-switch execution is serial, continues after individual failures, and exits nonzero if any switch fails.
- Prompt matching is substring matching with finite timeouts.
- Invalid configuration and unavailable operations fail before opening Telnet.
- `sanitize.py` and `sanitize-2.py` must not be modified.

## Review Focus

- A prompt timeout, EOF, or connection failure must not hang or report success; test in Task 3.
- A missing model operation must be rejected before network access; test in Task 1.
- A single unknown inventory selector must fail without running another switch; test in Task 2.
- An `all` run must continue after one failure and return a failing process status; test in Task 4.
- Filename and command placeholders must render the configured device name, credentials, FTP settings, and prefix exactly; test in Task 1.

---

### Task 1: Configuration Loading and Model Data

**Files:**
- Create: `sanitize-3.py`
- Create: `config/switches.json`
- Create: `config/ftp.json`
- Create: `config/sw-models/RAX711.json`
- Create: `config/sw-models/ISCOM.json`
- Create: `config/sw-models/OCNOS.json`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: JSON files rooted at a `pathlib.Path` configuration directory.
- Produces: `load_configuration(config_dir: Path, inventory_file: str) -> Configuration`, `render_step(step: dict, context: dict) -> CommandStep`, and `Configuration` data structures usable by CLI and orchestration tasks.

- [ ] **Step 1: Write failing tests for configuration loading and rendering**

  Test `load_configuration()` with the fixture JSON and assert that the
  `RINGS2` selector resolves to model `RAX711` and FTP values load. Test that
  `render_step()` accepts exactly `{device_name}`, `{switch_alias}`,
  `{username}`, `{password}`, `{ftp_host}`, `{ftp_user}`, `{ftp_pass}`,
  `{config_name}`, and `{filename}`, rendering `{filename}` as
  `{config_name}-{device_name}.cfg`. Unknown placeholders must fail. Test that
  a model with no selected operation raises a validation error before any
  connection object is created.

- [ ] **Step 2: Run the focused tests and verify they fail**

  Run: `python -m unittest tests.test_config -v`
  Expected: FAIL because `sanitize-3.py` and its configuration interfaces do not exist.

- [ ] **Step 3: Implement configuration loading in `sanitize-3.py`**

  Define typed or plainly structured data objects for switch records, FTP
  settings, model definitions, and command steps. Load `switches.json` by
  default, derive model paths from `sw-models/<model>.json`, validate required
  fields and operation names, and render only the fixed placeholder schema:
  `{device_name}`, `{switch_alias}`, `{username}`, `{password}`, `{ftp_host}`,
  `{ftp_user}`, `{ftp_pass}`, `{config_name}`, and `{filename}`. Raise an
  actionable error for any unknown placeholder. Keep selector keys distinct
  from device `name`; generated filenames use
  `{config_name}-{device_name}.cfg`.

- [ ] **Step 4: Add representative JSON configuration files**

  Move the current inventory, credentials, FTP server values, and model command
  sequences into the three JSON model files. Use one `operations` object with
  `sanitize`, `reboot`, `upload`, and `download` lists. Preserve RAX backup
  config commands, ISCOM FTP commands and file swapping, and any currently
  supported OCNOS entries without adding new device behavior.

- [ ] **Step 5: Run the focused tests and verify they pass**

  Run: `python -m unittest tests.test_config -v`
  Expected: PASS, including the missing-operation validation and placeholder
  rendering cases.

### Task 2: Command-Line Parsing and Operation Selection

**Files:**
- Modify: `sanitize-3.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Configuration` from Task 1.
- Produces: `parse_args(argv: list[str]) -> argparse.Namespace` and
  `select_switches(configuration: Configuration, selector: str) -> list[SwitchRecord]`.

- [ ] **Step 1: Write failing CLI tests**

  Test long and short operation flags, omitted target and explicit `all` both
  selecting the full configured list, default `config_dir=Path("./config")`,
  default `inventory_file="switches.json"`, explicit `--config-dir`, explicit
  `--list`, and required `--config-name` for upload/download. Test that two
  operation flags, an unknown selector, an alias equal to the reserved
  case-insensitive keyword `all`, and an invalid operation/target combination
  are rejected.

- [ ] **Step 2: Run the focused tests and verify they fail**

  Run: `python -m unittest tests.test_cli -v`
  Expected: FAIL because argument parsing and selection are not implemented.

- [ ] **Step 3: Implement `parse_args()` and `select_switches()`**

  Use an argparse mutually exclusive operation group for `-s/--sanitize`,
  `-r/--reboot`, `-u/--upload`, and `-d/--download`. Each operation accepts an
  optional selector with `const="all"`; `select_switches()` must normalize
  both `None` and the literal `all` to the full configured list. Validate
  inventory aliases case-insensitively so no alias can collide with reserved
  `all`. Add `-c/--config-name`, `-l/--list`, and `--config-dir`. Require a
  nonempty config-name for upload/download and reject unknown selectors before
  any `Switch` instance is constructed.

- [ ] **Step 4: Run the focused tests and verify they pass**

  Run: `python -m unittest tests.test_cli -v`
  Expected: PASS for defaults, aliases, validation, and selector lookup.

### Task 3: Telnet Step Execution and Switch Operations

**Files:**
- Modify: `sanitize-3.py`
- Create: `tests/test_switch.py`

**Interfaces:**
- Consumes: rendered `CommandStep` sequences and model flags from Task 1.
- Produces: `Switch.execute(operation: str, context: dict) -> None`,
  `Switch.close_session() -> None`, and a configurable Telnet factory suitable
  for tests.

- [ ] **Step 1: Write failing fake-Telnet tests**

  Provide a fake Telnet object that records `read_until()` and `write()` calls.
  Test login followed by ordered operation commands, substring prompt reads,
  command response output, file swapping only for sanitize, and RAX-specific
  commands coming from JSON rather than Python model conditionals. Test that a
  timeout, EOF, or connection error raises an operation error and closes the
  session.

- [ ] **Step 2: Run the focused tests and verify they fail**

  Run: `python -m unittest tests.test_switch -v`
  Expected: FAIL because `Switch` does not yet load model operations or execute
  generic command steps.

- [ ] **Step 3: Implement the generic `Switch` executor**

  Replace hardcoded model selection in the new script with the loaded model
  definition. Connect through an injectable Telnet factory, use a finite
  timeout for every prompt wait, send login and operation steps in order, and
  decode output safely for display. Execute the configured file-swap helper
  before sanitize, wait for its completion, and abort sanitize if it fails.
  Keep normal reboot free of file swapping. Implement `Switch` as a context
  manager or use a `try/finally` in `Switch.execute()` so `close_session()` is
  strictly called for every exception before the exception is propagated to
  orchestration; do not rely on `__del__`.

- [ ] **Step 4: Run the focused tests and verify they pass**

  Run: `python -m unittest tests.test_switch -v`
  Expected: PASS with no real network connection.

### Task 4: Orchestration, Samples, and Deployment Documentation

**Files:**
- Modify: `sanitize-3.py`
- Create: `README.md`
- Create: `tests/test_orchestration.py`
- Include: `swap_files.sh`, `muser_stop.sh`, and `muser_start.sh` in the deployment instructions when present on the source host.

**Interfaces:**
- Consumes: CLI and `Switch` interfaces from Tasks 1-3.
- Produces: `main(argv: list[str]) -> int` and a manually deployable directory
  with documented command examples.

- [ ] **Step 1: Write failing orchestration tests**

  Patch the switch factory and operation runner to test that a single selector
  runs exactly one switch, omitted target and explicit `all` run the full
  inventory in order, a failed switch calls `close_session()` before the next
  switch starts, later switches still run, and the final return code is
  nonzero when any switch fails. Test that no-operation invocation prints
  argparse help rather than sanitizing implicitly.

- [ ] **Step 2: Run the focused tests and verify they fail**

  Run: `python -m unittest tests.test_orchestration -v`
  Expected: FAIL because `main()` and all-switch failure aggregation are not
  implemented.

- [ ] **Step 3: Implement orchestration and entry-point behavior**

  Load configuration, select switches, construct a `Switch` per selected
  record, build the filename context for upload/download, execute the selected
  operation serially, collect failures, and return status `0` only when all
  selected operations succeed. Keep the existing mini-user setup behavior for
  sanitize runs only where applicable to the preserved workflow; do not run it
  for upload/download/reboot. Add the `if __name__ == "__main__"` entry point.

- [ ] **Step 4: Write `README.md`**

  Document prerequisites, copying the script/config/model files and helper
  shell scripts to another host, virtual-environment setup, JSON file layout,
  FTP server IP/login/password configuration, file permissions for plaintext
  credentials, all CLI flags, filename generation, single/all examples, and
  expected failure behavior.

- [ ] **Step 5: Run the complete test suite and syntax verification**

  Run: `python -m unittest discover -s tests -v`
  Expected: PASS with no network access required.

  Run: `python -m py_compile sanitize-3.py`
  Expected: exit code `0`.

- [ ] **Step 6: Perform a manual dry configuration check**

  Run: `python sanitize-3.py --help`
  Expected: help output lists all operation flags, `--config-dir`, `--list`,
  and `--config-name` without opening a Telnet connection.
