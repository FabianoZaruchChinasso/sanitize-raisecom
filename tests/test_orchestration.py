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
                "RING-S1": {"name": "RING-S1", "address": "a", "model": "M"},
                "RING-S2": {"name": "RING-S2", "address": "b", "model": "M"},
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
        result = self.run_main(["--sanitize", "RING-S2"])

        self.assertEqual(result, 0)
        self.assertEqual(FakeSwitch.events, [("execute", "RING-S2", "sanitize"), ("close", "RING-S2")])

    def test_omitted_and_explicit_all_run_inventory_in_order(self):
        self.assertEqual(self.run_main(["--reboot"]), 0)
        omitted_events = list(FakeSwitch.events)
        FakeSwitch.events = []
        self.assertEqual(self.run_main(["--reboot", "all"]), 0)

        self.assertEqual(omitted_events, FakeSwitch.events)
        self.assertEqual(
            omitted_events,
            [
                ("execute", "RING-S1", "reboot"),
                ("close", "RING-S1"),
                ("execute", "RING-S2", "reboot"),
                ("close", "RING-S2"),
            ],
        )

    def test_failure_closes_before_next_switch_and_returns_failure(self):
        FakeSwitch.fail_alias = "RING-S1"

        result = self.run_main(["--sanitize"])

        self.assertEqual(result, 1)
        self.assertEqual(
            FakeSwitch.events,
            [
                ("execute", "RING-S1", "sanitize"),
                ("close", "RING-S1"),
                ("execute", "RING-S2", "sanitize"),
                ("close", "RING-S2"),
            ],
        )

    def test_no_operation_prints_help_without_running_switches(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.run_main([])

        self.assertEqual(result, 0)
        self.assertIn("--sanitize", output.getvalue())
        self.assertEqual(FakeSwitch.events, [])

    def test_sanitize_does_not_run_miniusers_setup(self):
        with patch.object(sanitize_3, "load_configuration", return_value=self.configuration), patch.object(
            sanitize_3, "Switch", FakeSwitch
        ), patch.object(sanitize_3, "miniusers_setup") as setup:
            result = sanitize_3.main(["--sanitize", "RING-S2"])

        self.assertEqual(result, 0)
        setup.assert_not_called()

    def test_miniusers_flag_runs_setup_without_switches(self):
        with patch.object(sanitize_3, "miniusers_setup") as setup:
            result = sanitize_3.main(["-m"])

        self.assertEqual(result, 0)
        setup.assert_called_once()

    def test_print_all_lists_only_switch_aliases(self):
        output = io.StringIO()
        with patch.object(sanitize_3, "load_configuration", return_value=self.configuration), contextlib.redirect_stdout(output):
            result = sanitize_3.main(["--print"])

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().splitlines(), ["RING-S1", "RING-S2"])

    def test_print_selector_outputs_switch_json(self):
        output = io.StringIO()
        with patch.object(sanitize_3, "load_configuration", return_value=self.configuration), contextlib.redirect_stdout(output):
            result = sanitize_3.main(["--print", "RING-S2"])

        self.assertEqual(result, 0)
        self.assertIn('"name": "RING-S2"', output.getvalue())
        self.assertNotIn('"RING-S1"', output.getvalue())

    def test_print_dump_outputs_complete_inventory_json(self):
        output = io.StringIO()
        with patch.object(sanitize_3, "load_configuration", return_value=self.configuration), contextlib.redirect_stdout(output):
            result = sanitize_3.main(["--print", "dump"])

        self.assertEqual(result, 0)
        self.assertIn('"RING-S1"', output.getvalue())
        self.assertIn('"RING-S2"', output.getvalue())

    def test_combined_sanitize_and_miniusers_runs_setup_after_switches(self):
        with patch.object(sanitize_3, "load_configuration", return_value=self.configuration), patch.object(
            sanitize_3, "Switch", FakeSwitch
        ), patch.object(sanitize_3, "miniusers_setup") as setup:
            result = sanitize_3.main(["--sanitize", "RING-S2", "--miniusers"])

        self.assertEqual(result, 0)
        self.assertEqual(FakeSwitch.events[0], ("execute", "RING-S2", "sanitize"))
        setup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
