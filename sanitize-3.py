#!/usr/bin/env python3

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from string import Formatter


DEFAULT_CONFIG_DIR = Path("./config")
DEFAULT_INVENTORY_FILE = "switches.json"
MODEL_DIRECTORY = "sw-models"
SUPPORTED_OPERATIONS = {"sanitize", "reboot", "upload", "download"}
SUPPORTED_PLACEHOLDERS = {
    "device_name",
    "switch_alias",
    "username",
    "password",
    "ftp_host",
    "ftp_user",
    "ftp_pass",
    "config_name",
    "filename",
}


class ConfigurationError(ValueError):
    """Raised when configuration cannot safely describe an operation."""


class OperationError(RuntimeError):
    """Raised when a switch operation cannot complete safely."""


@dataclass
class Configuration:
    switches: dict
    ftp: dict
    models: dict


def _read_json(path: Path):
    try:
        with path.open(encoding="utf-8") as config_file:
            return json.load(config_file)
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"Invalid JSON in {path}: {error}") from error


def _validate_switches(switches):
    if not isinstance(switches, dict) or not switches:
        raise ConfigurationError("Switch inventory must be a non-empty JSON object")

    aliases = set()
    for alias, switch in switches.items():
        if alias.lower() == "all":
            raise ConfigurationError("The reserved alias 'all' cannot be used")
        if alias.lower() in aliases:
            raise ConfigurationError(f"Duplicate switch alias: {alias}")
        aliases.add(alias.lower())
        required = {"name", "address", "model", "username", "password"}
        missing = required - set(switch)
        if missing:
            missing_fields = ", ".join(sorted(missing))
            raise ConfigurationError(f"Switch {alias} is missing: {missing_fields}")


def _validate_ftp(ftp):
    required = {"host", "user", "password"}
    missing = required - set(ftp) if isinstance(ftp, dict) else required
    if missing:
        missing_fields = ", ".join(sorted(missing))
        raise ConfigurationError(f"FTP configuration is missing: {missing_fields}")


def _validate_step_template(step, location):
    if not isinstance(step, dict) or not isinstance(step.get("send"), str):
        raise ConfigurationError(f"Invalid command step at {location}: 'send' must be a string")
    if "expect" in step and step["expect"] is not None and not isinstance(step["expect"], str):
        raise ConfigurationError(f"Invalid command step at {location}: 'expect' must be a string")
    fields = {
        field_name
        for value in step.values()
        if isinstance(value, str)
        for _, field_name, _, _ in Formatter().parse(value)
        if field_name
    }
    unknown = fields - SUPPORTED_PLACEHOLDERS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigurationError(f"Unsupported placeholders at {location}: {names}")


def load_configuration(config_dir: Path, inventory_file: str = DEFAULT_INVENTORY_FILE):
    config_dir = Path(config_dir)
    switches = _read_json(config_dir / inventory_file)
    ftp = _read_json(config_dir / "ftp.json")
    _validate_switches(switches)
    _validate_ftp(ftp)

    models = {}
    for switch in switches.values():
        model_name = switch["model"]
        if model_name in models:
            continue
        model = _read_json(config_dir / MODEL_DIRECTORY / f"{model_name}.json")
        if not isinstance(model, dict):
            raise ConfigurationError(f"Model {model_name} must be a JSON object")
        operations = model.get("operations", {})
        unknown_operations = set(operations) - SUPPORTED_OPERATIONS
        if unknown_operations:
            names = ", ".join(sorted(unknown_operations))
            raise ConfigurationError(f"Model {model_name} has unsupported operations: {names}")
        if not isinstance(model.get("login"), list):
            raise ConfigurationError(f"Model {model_name} must define a login step list")
        if not isinstance(model.get("ready_prompt"), str):
            raise ConfigurationError(f"Model {model_name} must define a ready_prompt string")
        for index, step in enumerate(model["login"]):
            _validate_step_template(step, f"{model_name}.login[{index}]")
        for operation_name, steps in operations.items():
            if not isinstance(steps, list):
                raise ConfigurationError(
                    f"Model {model_name}.{operation_name} must be a command step list"
                )
            for index, step in enumerate(steps):
                _validate_step_template(step, f"{model_name}.{operation_name}[{index}]")
        models[model_name] = model

    return Configuration(switches=switches, ftp=ftp, models=models)


def _placeholder_context(context):
    context = dict(context)
    if "config_name" in context and "device_name" in context:
        context["filename"] = f"{context['config_name']}-{context['device_name']}.cfg"

    unknown = set(context) - SUPPORTED_PLACEHOLDERS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigurationError(f"Unsupported placeholder values: {names}")
    return context


def render_step(step: dict, context: dict):
    if not isinstance(step, dict) or "send" not in step:
        raise ConfigurationError("Each command step must contain a 'send' value")

    values = _placeholder_context(context)
    fields = {
        field_name
        for value in step.values()
        if isinstance(value, str)
        for _, field_name, _, _ in Formatter().parse(value)
        if field_name
    }
    unknown = fields - SUPPORTED_PLACEHOLDERS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigurationError(f"Unsupported placeholders: {names}")
    missing = fields - values.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise ConfigurationError(f"Missing placeholder values: {names}")

    return {
        key: value.format_map(values) if isinstance(value, str) else value
        for key, value in step.items()
    }


def validate_operation(configuration: Configuration, switch_alias: str, operation: str):
    if switch_alias not in configuration.switches:
        raise ConfigurationError(f"Unknown switch alias: {switch_alias}")
    if operation not in SUPPORTED_OPERATIONS:
        raise ConfigurationError(f"Unsupported operation: {operation}")
    model_name = configuration.switches[switch_alias]["model"]
    steps = configuration.models[model_name].get("operations", {}).get(operation)
    if not steps:
        raise ConfigurationError(
            f"Operation '{operation}' is not configured for model {model_name}"
        )
    return steps


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Sanitize and transfer Raisecom switch configurations")
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument("-s", "--sanitize", dest="sanitize_target", nargs="?", const="all", metavar="SWITCH")
    operations.add_argument("-r", "--reboot", dest="reboot_target", nargs="?", const="all", metavar="SWITCH")
    operations.add_argument("-u", "--upload", dest="upload_target", nargs="?", const="all", metavar="SWITCH")
    operations.add_argument("-d", "--download", dest="download_target", nargs="?", const="all", metavar="SWITCH")
    parser.add_argument("-c", "--config-name", dest="config_name")
    parser.add_argument("-l", "--list", dest="inventory_file", default=DEFAULT_INVENTORY_FILE)
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    arguments = parser.parse_args(argv)

    selected_operations = [
        name
        for name, option in (
            ("sanitize", arguments.sanitize_target),
            ("reboot", arguments.reboot_target),
            ("upload", arguments.upload_target),
            ("download", arguments.download_target),
        )
        if option is not None
    ]
    if not selected_operations:
        arguments.operation = None
        arguments.target = "all"
        arguments._parser = parser
        return arguments
    arguments.operation = selected_operations[0]
    arguments.target = getattr(arguments, f"{arguments.operation}_target")
    if arguments.operation in {"upload", "download"} and not arguments.config_name:
        parser.error("--config-name is required for upload and download")
    return arguments


def select_switches(configuration: Configuration, selector):
    if selector is None or selector.strip().casefold() == "all":
        return [dict(switch, alias=alias) for alias, switch in configuration.switches.items()]

    normalized = selector.strip().casefold()
    for alias, switch in configuration.switches.items():
        if alias.casefold() == normalized:
            return [dict(switch, alias=alias)]
    raise ConfigurationError(f"Unknown switch alias: {selector}")


class Switch:
    def __init__(
        self,
        switch_alias,
        configuration,
        telnet_factory=None,
        swap_runner=None,
        helper_dir=None,
        timeout=10,
    ):
        if switch_alias not in configuration.switches:
            raise ConfigurationError(f"Unknown switch alias: {switch_alias}")
        self.switch_alias = switch_alias
        self.configuration = configuration
        self.switch = configuration.switches[switch_alias]
        self.model = configuration.models[self.switch["model"]]
        self.telnet_factory = telnet_factory or self._default_telnet_factory
        self.swap_runner = swap_runner or self._default_swap_runner
        self.helper_dir = Path(helper_dir) if helper_dir else Path(__file__).parent
        self.timeout = timeout
        self.t = None

    @staticmethod
    def _default_telnet_factory(address, timeout):
        try:
            import telnetlib
        except ImportError as error:
            raise OperationError("telnetlib dependency is not installed") from error
        return telnetlib.Telnet(address, timeout=timeout)

    def _default_swap_runner(self, device_name):
        helper = self.helper_dir / "swap_files.sh"
        if not helper.exists():
            raise OperationError(f"File swap helper not found: {helper}")
        subprocess.run(["bash", str(helper), device_name], check=True, cwd=self.helper_dir)

    def _context(self, context):
        values = {
            "device_name": self.switch["name"],
            "switch_alias": self.switch_alias,
            "username": self.switch["username"],
            "password": self.switch["password"],
            "ftp_host": self.configuration.ftp["host"],
            "ftp_user": self.configuration.ftp["user"],
            "ftp_pass": self.configuration.ftp["password"],
        }
        values.update(context)
        return values

    def execute(self, operation, context):
        try:
            steps = validate_operation(self.configuration, self.switch_alias, operation)
            if operation == "sanitize" and self.model.get("needs_file_swap"):
                self.swap_runner(self.switch["name"])

            values = self._context(context)
            login_steps = [render_step(step, values) for step in self.model["login"]]
            operation_steps = [render_step(step, values) for step in steps]
            self.t = self.telnet_factory(self.switch["address"], self.timeout)
            for rendered in login_steps:
                expected = rendered.get("expect")
                if expected:
                    response = self.t.read_until(expected.encode("ascii"), self.timeout)
                    if expected.encode("ascii") not in response:
                        raise OperationError(
                            f"Unexpected prompt for {self.switch_alias}: expected {expected!r}"
                        )
                    if response:
                        print(response.decode("ascii", errors="replace"), end="")
                self.t.write(rendered["send"].encode("ascii") + b"\n")
            ready_prompt = self.model["ready_prompt"]
            response = self.t.read_until(ready_prompt.encode("ascii"), self.timeout)
            if ready_prompt.encode("ascii") not in response:
                raise OperationError(
                    f"Unexpected ready prompt for {self.switch_alias}: expected {ready_prompt!r}"
                )
            if response:
                print(response.decode("ascii", errors="replace"), end="")
            for rendered in operation_steps:
                self.t.write(rendered["send"].encode("ascii") + b"\n")
                expected = rendered.get("expect")
                if expected:
                    response = self.t.read_until(expected.encode("ascii"), self.timeout)
                    if expected.encode("ascii") not in response:
                        raise OperationError(
                            f"Unexpected prompt for {self.switch_alias}: expected {expected!r}"
                        )
                    if response:
                        print(response.decode("ascii", errors="replace"), end="")
        except (ConfigurationError, OperationError):
            raise
        except (EOFError, OSError, TimeoutError) as error:
            raise OperationError(f"Operation {operation} failed on {self.switch_alias}: {error}") from error
        finally:
            self.close_session()

    def close_session(self):
        if self.t is not None:
            self.t.close()
            self.t = None


def main(argv=None):
    arguments = parse_args(argv)
    if arguments.operation is None:
        arguments._parser.print_help()
        return 0

    configuration = load_configuration(arguments.config_dir, arguments.inventory_file)
    selected = select_switches(configuration, arguments.target)
    for switch in selected:
        validate_operation(configuration, switch["alias"], arguments.operation)

    failures = []
    for switch in selected:
        runner = Switch(switch["alias"], configuration)
        context = {}
        if arguments.config_name:
            context["config_name"] = arguments.config_name
        try:
            runner.execute(arguments.operation, context)
        except Exception as error:
            failures.append((switch["alias"], error))
            print(f"{switch['alias']}: {error}")
        finally:
            runner.close_session()
    if arguments.operation == "sanitize":
        try:
            miniusers_setup()
        except Exception as error:
            failures.append(("miniusers", error))
            print(f"miniusers: {error}")
    return 1 if failures else 0


def miniusers_setup():
    helper_dir = Path(__file__).parent
    stop_script = helper_dir / "muser_stop.sh"
    start_script = helper_dir / "muser_start.sh"
    missing = [str(path) for path in (stop_script, start_script) if not path.exists()]
    if missing:
        raise OperationError("Mini-user helper script(s) not found: " + ", ".join(missing))
    subprocess.run(["bash", str(stop_script)], check=True, cwd=helper_dir)
    time.sleep(1)
    subprocess.run(["bash", str(start_script)], check=True, cwd=helper_dir)


if __name__ == "__main__":
    raise SystemExit(main())
