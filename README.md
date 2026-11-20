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

For mini-user setup, keep the helper scripts under `scripts/` beside
`sanitize-3.py`:

```text
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

To install the command system-wide:

```bash
sudo ./scripts/install.sh
sanitize-3 --help
```

The installer places the script at `/etc/sanitize/sanitize-3.py`, creates the
`/usr/bin/sanitize-3` command, copies configuration to `/etc/sanitize/config`,
and copies helper scripts to `/etc/sanitize/scripts`. When running outside a
checkout without a local `./config` directory, `sanitize-3` automatically uses
`/etc/sanitize/config`.

## Configuration

The default configuration directory is `./config`. Override it with
`--config-dir PATH`.

`config/switches.json` maps user-facing aliases to device data:

```json
{
  "RING-S2": {
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
  "host": "10.30.0.220",
  "user": "raisecom",
  "password": "r@is3c0m"
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

Any command step may also define a positive `timeout` in seconds when the
switch operation is expected to take longer than the default prompt timeout.

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
python sanitize-3.py --miniusers
python sanitize-3.py --print
python sanitize-3.py --print RING-S2
python sanitize-3.py --print dump
```

Run one switch by passing its inventory alias:

```bash
python sanitize-3.py --sanitize RING-S2
python sanitize-3.py --reboot RAX-MPLS1
python sanitize-3.py --upload RING-S2 --config-name nightly
python sanitize-3.py --download RING-S2 --config-name nightly
```

Short operation flags are also available:

```text
-s/--sanitize
-r/--reboot
-u/--upload
-d/--download
-m/--miniusers
-p/--print [all|SWITCH|dump]
-c/--config-name PREFIX
-l/--list FILE
--config-dir PATH
```

`--list FILE` selects an inventory file relative to the configuration
directory and defaults to `switches.json`. Upload and download require
`--config-name`; for example, `--config-name nightly` and device `RING-S2`
produce `nightly-RING-S2.cfg`.

`--print` without a value, or with `all`, lists switch aliases. A switch alias
prints that switch's JSON values, while `dump` prints the complete inventory
JSON.

`--sanitize` performs the model's factory-reset procedure. `--reboot` runs
only the model's reboot procedure.

## Failure Behavior

Configuration errors are reported before any Telnet connection is opened.
Switches selected by `all` are processed serially. If one switch fails, its
session is closed, the failure is reported, and the next switch is attempted.
The process exits with status `1` if any selected switch fails and `0` when all
selected operations succeed.
