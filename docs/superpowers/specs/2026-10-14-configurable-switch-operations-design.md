# Configurable Switch Operations Design

## Intent

Create `sanitize-3.py` as a refactored successor to `sanitize-2.py`. The new
script must keep the existing Telnet workflows while moving switch inventory,
FTP settings, and model-specific behavior into JSON files. The original
`sanitize.py` and `sanitize-2.py` files remain unchanged as rollback and
reference versions.

## Goals

- Configure switches, credentials, models, and FTP settings without editing
  Python code.
- Define `sanitize`, `reboot`, `upload`, and `download` behavior in model JSON
  files using ordered prompt/command steps.
- Support all-switch and single-switch operation selection.
- Run manually on another host from a copied directory.
- Document installation, configuration, FTP server setup, and commands.

## Non-goals

- Replacing Telnet with SSH or another transport.
- Changing the existing device command sequences unless required to express
  them in configuration.
- Creating a system service or package installer.
- Removing or rewriting the two existing scripts.

## Anti-goals

- Do not silently select a different switch or model when configuration is
  invalid.
- Do not hardcode credentials, FTP values, switch inventories, or model
  command sequences in `sanitize-3.py`.
- Do not make a failed device operation appear successful.

## Configuration Layout

The default configuration directory is `./config` and can be overridden by a
CLI option:

```text
sanitize-3.py
README.md
config/
  switches.json
  ftp.json
  sw-models/
    RAX711.json
    ISCOM.json
    OCNOS.json
```

`--list FILE` selects the switch inventory file relative to the configuration
directory and defaults to `switches.json`. `ftp.json` contains the FTP server
address, username, and password. Each switch entry contains its alias, device
name, address, model identifier, Telnet username, and password.

Each model file contains shared login behavior, a `ready_prompt` reached after
login, and an `operations` object with
`sanitize`, `reboot`, `upload`, and `download` ordered step lists. A step has an
expected response prompt and a command to send. Login steps wait for their
prompt before sending; operation steps send first and then wait for the
configured response prompt. Commands may use placeholders for
switch credentials, switch name, FTP settings, and the generated configuration
filename. Model flags such as file swapping are also stored in the model file.

The supported placeholder schema is fixed and validated by `render_step()`:

- `{device_name}` and `{switch_alias}` identify the configured device.
- `{username}` and `{password}` are the switch Telnet credentials.
- `{ftp_host}`, `{ftp_user}`, and `{ftp_pass}` are FTP server settings.
- `{config_name}` is the configured filename prefix.
- `{filename}` is the complete `{config_name}-{device_name}.cfg` filename.

## Command-Line Interface

Exactly one operation is selected per invocation:

```text
sanitize-3.py --sanitize [SWITCH]
sanitize-3.py --reboot [SWITCH]
sanitize-3.py --upload [SWITCH] --config-name PREFIX
sanitize-3.py --download [SWITCH] --config-name PREFIX
```

The short forms are `-s`, `-r`, `-u`, and `-d`. An omitted operation target
means `all`. `--config-dir PATH` defaults to `./config`, and `--list FILE`
defaults to `switches.json`. `--config-name PREFIX` produces
`{PREFIX}-{switch_name}.cfg` and is required for upload/download operations.

`--sanitize` performs the current factory-reset procedure, including model
configured file swapping. `--reboot` performs only the configured normal
reboot sequence.

## Constraints

- Use the Python standard library plus the existing
  `telnetlib-313-and-up` dependency.
- Keep command execution ordered and prompt-driven.
- Keep plaintext JSON credentials because that is the requested deployment
  model; document file permissions and the security implication.
- Manual deployment must require only the script, JSON configuration, shell
  helper scripts already used by the workflow, and Python dependencies.
- Prompt matching uses substring matching, consistent with
  `telnetlib.read_until()`.
- Each prompt step has a finite timeout and reports timeout, EOF, connection,
  and unexpected-prompt failures clearly.
- `all` processes switches serially, continues after an individual failure,
  reports all failures, and exits nonzero if any switch failed.
- The inventory key is the user-facing switch selector, such as `RINGS2`;
  the configured device name is used in commands and generated filenames.
- Target normalization maps an omitted target and the explicit target `all` to
  the full configured switch list. Inventory aliases are validated so the
  reserved keyword `all` cannot be used as an alias.
- A model may omit an operation; selecting an unavailable operation fails
  before opening a Telnet connection.
- File-swap helper scripts are copied beside `sanitize-3.py` and their
  location is documented in `README.md`.
- `Switch.execute()` guarantees `close_session()` in exception cleanup before
  propagating the failure to serial orchestration.

## Success Criteria

- The existing RAX upload/download flow can be represented by JSON without
  model-name conditionals in Python.
- The existing sanitize/reboot flows can be represented by JSON, including
  RAX-specific extra commands and ISCOM file swapping.
- A single configured switch and all configured switches can be selected.
- Invalid files, models, operations, and switch names fail with actionable
  errors before a Telnet session is opened.
- Tests cover CLI parsing, JSON loading, placeholder rendering, operation
  selection, and command-step execution with a fake Telnet connection.
