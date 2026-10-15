# Raisecom Switch Sanitizer

`sanitize-3.py` runs the configured Telnet procedures for Raisecom switches.
The older `sanitize.py` and `sanitize-2.py` scripts are kept for reference and
are not required by the new workflow.

## Installation

Copy these files to the target host:

```text
sanitize-3.py
requirements.txt
config/
  switches.json
  ftp.json
  sw-models/
    RAX711.json
    ISCOM.json
    OCNOS.json
```

For sanitize operations, also copy the helper scripts used by the deployment
beside `sanitize-3.py`:

```text
swap_files.sh
muser_stop.sh
muser_start.sh
```

The helper scripts must be executable. Create a virtual environment and
install the Telnet compatibility dependency:

```bash
python3 -m venv venv
. venv/bin/activate
python -m pip install -r requirements.txt
```

Run the commands manually from the directory containing `sanitize-3.py`.

## Configuration

The default configuration directory is `./config`. Override it with
`--config-dir PATH`.

`config/switches.json` maps user-facing aliases to device data:

```json
{
  "RINGS2": {
    "name": "RING-S2",
    "address": "10.30.0.201",
    "model": "RAX711",
    "username": "master",
    "password": "America.1"
  }
}
```

The alias `all` is reserved and cannot be used as a switch alias.

`config/ftp.json` contains the FTP server configuration:

```json
{
  "host": "10.147.20.159",
  "user": "venko",
  "password": "V3nk0"
}
```

Model files under `config/sw-models/` define login prompts, a `ready_prompt`
shell prompt reached after login, and ordered
`sanitize`, `reboot`, `upload`, and `download` operations. Login steps wait for
their `expect` prompt before sending `send`; operation steps send `send` first,
then wait for their `expect` response prompt. Set `expect` to `null` when a
command has no response prompt to wait for. Supported command placeholders are:

- `{device_name}` and `{switch_alias}`
- `{username}` and `{password}`
- `{ftp_host}`, `{ftp_user}`, and `{ftp_pass}`
- `{config_name}` and `{filename}`

`{filename}` is generated as `{config_name}-{device_name}.cfg`.

These files contain plaintext switch and FTP credentials. Protect them on the
target host, for example:

```bash
chmod 700 config
chmod 600 config/*.json config/sw-models/*.json
```

## Commands

Exactly one operation is selected per invocation. If no switch is supplied,
the operation runs serially for every switch in `switches.json`:

```bash
python sanitize-3.py --sanitize
python sanitize-3.py --reboot
python sanitize-3.py --upload --config-name backup
python sanitize-3.py --download --config-name backup
```

Run one switch by passing its inventory alias:

```bash
python sanitize-3.py --sanitize RINGS2
python sanitize-3.py --reboot RAX-MPLS1
python sanitize-3.py --upload RINGS2 --config-name nightly
python sanitize-3.py --download RINGS2 --config-name nightly
```

Short operation flags are also available:

```text
-s/--sanitize
-r/--reboot
-u/--upload
-d/--download
-c/--config-name PREFIX
-l/--list FILE
--config-dir PATH
```

`--list FILE` selects an inventory file relative to the configuration
directory and defaults to `switches.json`. Upload and download require
`--config-name`; for example, `--config-name nightly` and device `RING-S2`
produce `nightly-RING-S2.cfg`.

`--sanitize` performs the model's factory-reset procedure and runs the model's
file-swap helper when configured. `--reboot` runs only the model's reboot
procedure.

## Failure Behavior

Configuration errors are reported before any Telnet connection is opened.
Switches selected by `all` are processed serially. If one switch fails, its
session is closed, the failure is reported, and the next switch is attempted.
The process exits with status `1` if any selected switch fails and `0` when all
selected operations succeed.
