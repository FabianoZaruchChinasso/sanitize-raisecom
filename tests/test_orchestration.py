import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "sanitize-3.py"
SPEC = importlib.util.spec_from_file_location("sanitize_3_orchestration", MODULE_PATH)
sanitize_3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sanitize_3)


class FakeSwitch:
    events = []
    fail_alias = None

    def __init__(self, alias, configuration, **kwargs):
        self.alias = alias

    def execute(self, operation, context):
        self.events.append(("execute", self.alias, operation))
        if self.alias == self.fail_alias:
            raise sanitize_3.OperationError("failed")

    def close_session(self):
        self.events.append(("close", self.alias))


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        FakeSwitch.events = []
        FakeSwitch.fail_alias = None
        self.configuration = sanitize_3.Configuration(
            switches={
                "RINGS1": {"name": "RING-S1", "address": "a", "model": "M"},
                "RINGS2": {"name": "RING-S2", "address": "b", "model": "M"},
            },
            ftp={"host": "h", "user": "u", "password": "p"},
            models={"M": {"login": [], "operations": {"sanitize": [{"send": "x"}], "reboot": [{"send": "x"}]}}},
        )

    def run_main(self, argv):
        with patch.object(sanitize_3, "load_configuration", return_value=self.configuration), patch.object(
            sanitize_3, "Switch", FakeSwitch
        ), patch.object(sanitize_3, "miniusers_setup"):
            return sanitize_3.main(argv)

    def test_single_selector_runs_only_selected_switch(self):
        result = self.run_main(["--sanitize", "RINGS2"])

        self.assertEqual(result, 0)
        self.assertEqual(FakeSwitch.events, [("execute", "RINGS2", "sanitize"), ("close", "RINGS2")])

    def test_omitted_and_explicit_all_run_inventory_in_order(self):
        self.assertEqual(self.run_main(["--reboot"]), 0)
        omitted_events = list(FakeSwitch.events)
        FakeSwitch.events = []
        self.assertEqual(self.run_main(["--reboot", "all"]), 0)

        self.assertEqual(omitted_events, FakeSwitch.events)
        self.assertEqual(
            omitted_events,
            [
                ("execute", "RINGS1", "reboot"),
                ("close", "RINGS1"),
                ("execute", "RINGS2", "reboot"),
                ("close", "RINGS2"),
            ],
        )

    def test_failure_closes_before_next_switch_and_returns_failure(self):
        FakeSwitch.fail_alias = "RINGS1"

        result = self.run_main(["--sanitize"])

        self.assertEqual(result, 1)
        self.assertEqual(
            FakeSwitch.events,
            [
                ("execute", "RINGS1", "sanitize"),
                ("close", "RINGS1"),
                ("execute", "RINGS2", "sanitize"),
                ("close", "RINGS2"),
            ],
        )

    def test_no_operation_prints_help_without_running_switches(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.run_main([])

        self.assertEqual(result, 0)
        self.assertIn("--sanitize", output.getvalue())
        self.assertEqual(FakeSwitch.events, [])

    def test_sanitize_runs_miniusers_setup_after_switches(self):
        with patch.object(sanitize_3, "load_configuration", return_value=self.configuration), patch.object(
            sanitize_3, "Switch", FakeSwitch
        ), patch.object(sanitize_3, "miniusers_setup") as setup:
            result = sanitize_3.main(["--sanitize", "RINGS2"])

        self.assertEqual(result, 0)
        setup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
