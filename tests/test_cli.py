import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "sanitize-3.py"
SPEC = importlib.util.spec_from_file_location("sanitize_3_cli", MODULE_PATH)
sanitize_3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sanitize_3)


class CliTests(unittest.TestCase):
    def configuration(self):
        return sanitize_3.Configuration(
            switches={
                "RINGS1": {"name": "RING-S1", "model": "ISCOM"},
                "RINGS2": {"name": "RING-S2", "model": "RAX711"},
            },
            ftp={},
            models={},
        )

    def test_operation_without_target_defaults_to_all(self):
        arguments = sanitize_3.parse_args(["--sanitize"])

        self.assertEqual(arguments.operation, "sanitize")
        self.assertEqual(arguments.target, "all")

    def test_explicit_all_selects_full_inventory(self):
        configuration = self.configuration()

        selected = sanitize_3.select_switches(configuration, "all")

        self.assertEqual([switch["name"] for switch in selected], ["RING-S1", "RING-S2"])

    def test_implicit_none_selects_full_inventory(self):
        configuration = self.configuration()

        selected = sanitize_3.select_switches(configuration, None)

        self.assertEqual([switch["name"] for switch in selected], ["RING-S1", "RING-S2"])

    def test_upload_requires_config_name(self):
        with self.assertRaises(SystemExit):
            sanitize_3.parse_args(["--upload"])

    def test_upload_accepts_config_name_and_short_flag(self):
        arguments = sanitize_3.parse_args(["-u", "RINGS2", "--config-name", "backup"])

        self.assertEqual(arguments.operation, "upload")
        self.assertEqual(arguments.target, "RINGS2")
        self.assertEqual(arguments.config_name, "backup")

    def test_defaults_and_overrides_are_parsed(self):
        defaults = sanitize_3.parse_args(["--reboot"])
        overridden = sanitize_3.parse_args(
            ["--download", "--config-name", "nightly", "--config-dir", "/tmp/config", "--list", "rack.json"]
        )

        self.assertEqual(defaults.config_dir, Path("./config"))
        self.assertEqual(defaults.inventory_file, "switches.json")
        self.assertEqual(overridden.config_dir, Path("/tmp/config"))
        self.assertEqual(overridden.inventory_file, "rack.json")

    def test_unknown_selector_is_rejected(self):
        with self.assertRaises(sanitize_3.ConfigurationError):
            sanitize_3.select_switches(self.configuration(), "missing")

    def test_alias_all_is_rejected_when_loading_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sw-models").mkdir()
            (root / "ftp.json").write_text('{"host":"h","user":"u","password":"p"}')
            (root / "switches.json").write_text(
                '{"ALL":{"name":"bad","address":"a","model":"M","username":"u","password":"p"}}'
            )
            (root / "sw-models" / "M.json").write_text(
                '{"login":[],"operations":{"sanitize":[]}}'
            )

            with self.assertRaises(sanitize_3.ConfigurationError):
                sanitize_3.load_configuration(root)

    def test_two_operations_are_rejected(self):
        with self.assertRaises(SystemExit):
            sanitize_3.parse_args(["--sanitize", "--reboot"])


if __name__ == "__main__":
    unittest.main()
