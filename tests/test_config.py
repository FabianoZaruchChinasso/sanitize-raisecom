import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "sanitize-3.py"
SPEC = importlib.util.spec_from_file_location("sanitize_3", MODULE_PATH)
sanitize_3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sanitize_3)


class ConfigurationTests(unittest.TestCase):
    def write_config(self, root):
        (root / "sw-models").mkdir()
        (root / "ftp.json").write_text(
            json.dumps({"host": "10.147.20.159", "user": "ftp-user", "password": "ftp-pass"})
        )
        (root / "switches.json").write_text(
            json.dumps(
                {
                    "RINGS2": {
                        "name": "RING-S2",
                        "address": "10.30.0.201",
                        "model": "RAX711",
                        "username": "master",
                        "password": "switch-pass",
                    }
                }
            )
        )
        (root / "sw-models" / "RAX711.json").write_text(
            json.dumps(
                {
                    "needs_file_swap": False,
                    "ready_prompt": "#",
                    "login": [{"expect": "gin:", "send": "{username}"}],
                    "operations": {
                        "sanitize": [{"expect": "#", "send": "reboot"}],
                        "reboot": [{"expect": "#", "send": "reboot"}],
                        "upload": [],
                        "download": [],
                    },
                }
            )
        )

    def test_load_configuration_reads_switch_and_ftp_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_config(root)

            configuration = sanitize_3.load_configuration(root, "switches.json")

            self.assertEqual(configuration.switches["RINGS2"]["model"], "RAX711")
            self.assertEqual(configuration.ftp["host"], "10.147.20.159")

    def test_render_step_supports_standard_placeholders(self):
        context = {
            "device_name": "RING-S2",
            "switch_alias": "RINGS2",
            "username": "master",
            "password": "switch-pass",
            "ftp_host": "10.147.20.159",
            "ftp_user": "ftp-user",
            "ftp_pass": "ftp-pass",
            "config_name": "backup",
        }
        step = {
            "expect": "#",
            "send": (
                "{device_name}|{switch_alias}|{username}|{password}|"
                "{ftp_host}|{ftp_user}|{ftp_pass}|{config_name}|{filename}"
            ),
        }

        rendered = sanitize_3.render_step(step, context)

        self.assertEqual(
            rendered["send"],
            "RING-S2|RINGS2|master|switch-pass|10.147.20.159|ftp-user|"
            "ftp-pass|backup|backup-RING-S2.cfg",
        )

    def test_render_step_rejects_unknown_placeholder(self):
        with self.assertRaises(sanitize_3.ConfigurationError):
            sanitize_3.render_step({"expect": "#", "send": "{not_supported}"}, {})

    def test_missing_operation_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_config(root)
            configuration = sanitize_3.load_configuration(root, "switches.json")

            with self.assertRaises(sanitize_3.ConfigurationError):
                sanitize_3.validate_operation(configuration, "RINGS2", "upload")

    def test_production_rax_sanitize_contains_factory_reset_sequence(self):
        configuration = sanitize_3.load_configuration(
            Path(__file__).parents[1] / "config", "switches.json"
        )

        steps = configuration.models["RAX711"]["operations"]["sanitize"]

        self.assertEqual(
            [step["send"] for step in steps],
            ["boot next-startup system1", "write", "reboot", "yes"],
        )

    def test_production_rax_download_starts_with_confirmation_prompt(self):
        configuration = sanitize_3.load_configuration(
            Path(__file__).parents[1] / "config", "switches-mpls.json"
        )

        steps = configuration.models["RAX711"]["operations"]["download"]

        self.assertEqual(
            [step["expect"] for step in steps],
            ["place it", "#", "#"],
        )

    def test_production_rax_reboot_waits_for_confirmation_prompt(self):
        configuration = sanitize_3.load_configuration(
            Path(__file__).parents[1] / "config", "switches-mpls.json"
        )

        reboot_steps = configuration.models["RAX711"]["operations"]["reboot"]
        sanitize_steps = configuration.models["RAX711"]["operations"]["sanitize"][-2:]

        self.assertEqual(
            [step["expect"] for step in reboot_steps],
            ["Please input 'yes' to confirm", None],
        )
        self.assertEqual(
            [step["expect"] for step in sanitize_steps],
            ["Please input 'yes' to confirm", None],
        )

    def test_invalid_model_placeholder_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_config(root)
            model_path = root / "sw-models" / "RAX711.json"
            model = json.loads(model_path.read_text())
            model["operations"]["reboot"][0]["send"] = "{not_supported}"
            model_path.write_text(json.dumps(model))

            with self.assertRaises(sanitize_3.ConfigurationError):
                sanitize_3.load_configuration(root, "switches.json")


if __name__ == "__main__":
    unittest.main()
