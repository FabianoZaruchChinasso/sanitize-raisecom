import importlib.util
import contextlib
import io
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "sanitize-3.py"
SPEC = importlib.util.spec_from_file_location("sanitize_3_switch", MODULE_PATH)
sanitize_3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sanitize_3)


class FakeTelnet:
    def __init__(self, reads=None, failure=None):
        self.reads = list(reads or [])
        self.failure = failure
        self.read_prompts = []
        self.writes = []
        self.events = []
        self.closed = False

    def read_until(self, prompt, timeout):
        self.read_prompts.append((prompt, timeout))
        self.events.append(("read", prompt))
        if self.failure:
            raise self.failure
        return self.reads.pop(0) if self.reads else b""

    def write(self, value):
        self.writes.append(value)
        self.events.append(("write", value))

    def close(self):
        self.closed = True


def make_configuration(needs_file_swap=False):
    return sanitize_3.Configuration(
        switches={
            "RINGS2": {
                "name": "RING-S2",
                "address": "10.30.0.201",
                "model": "RAX711",
                "username": "user",
                "password": "pass",
            }
        },
        ftp={"host": "ftp", "user": "ftp-user", "password": "ftp-pass"},
        models={
            "RAX711": {
                "needs_file_swap": needs_file_swap,
                "ready_prompt": "#",
                "login": [{"expect": "gin:", "send": "{username}"}],
                "operations": {
                    "sanitize": [
                        {"expect": "#", "send": "boot next-startup system1"},
                        {"expect": "#", "send": "write"},
                    ],
                    "reboot": [{"expect": "#", "send": "reboot"}],
                },
            }
        },
    )


class SwitchTests(unittest.TestCase):
    def make_switch(self, fake, configuration, swap_runner=None):
        return sanitize_3.Switch(
            "RINGS2",
            configuration,
            telnet_factory=lambda address, timeout: fake,
            swap_runner=swap_runner,
            timeout=3,
        )

    def test_execute_logs_in_and_sends_ordered_model_commands(self):
        fake = FakeTelnet(reads=[b"gin:", b"#", b"#", b"#"])
        configuration = make_configuration()
        switch = self.make_switch(fake, configuration)

        switch.execute("sanitize", {"config_name": "backup"})

        self.assertEqual(
            fake.writes,
            [b"user\n", b"boot next-startup system1\n", b"write\n"],
        )
        self.assertTrue(all(timeout == 3 for _, timeout in fake.read_prompts))
        self.assertTrue(fake.closed)

    def test_upload_sends_each_command_before_waiting_for_its_response(self):
        fake = FakeTelnet(reads=[b"gin:", b"#", b"#", b"#", b"#"])
        configuration = make_configuration()
        configuration.models["RAX711"]["operations"]["upload"] = [
            {"expect": "#", "send": "write backup-config"},
            {"expect": "#", "send": "upload backup-config ftp host user pass file.cfg"},
        ]
        switch = self.make_switch(fake, configuration)

        switch.execute("upload", {"config_name": "backup"})

        self.assertEqual(
            fake.events,
            [
                ("read", b"gin:"),
                ("write", b"user\n"),
                ("read", b"#"),
                ("write", b"write backup-config\n"),
                ("read", b"#"),
                ("write", b"upload backup-config ftp host user pass file.cfg\n"),
                ("read", b"#"),
            ],
        )

    def test_download_waits_for_confirmation_then_copies_startup_config(self):
        fake = FakeTelnet(reads=[b"gin:", b"#", b"place it", b"#", b"#"])
        configuration = make_configuration()
        configuration.models["RAX711"]["operations"]["download"] = [
            {"expect": "place it", "send": "download backup-config"},
            {"expect": "#", "send": "yes"},
            {"expect": "#", "send": "copy backup-config startup-config"},
        ]
        switch = self.make_switch(fake, configuration)

        switch.execute("download", {"config_name": "backup"})

        self.assertEqual(
            fake.writes,
            [
                b"user\n",
                b"download backup-config\n",
                b"yes\n",
                b"copy backup-config startup-config\n",
            ],
        )

    def test_sanitize_swaps_files_but_reboot_does_not(self):
        fake = FakeTelnet(reads=[b"gin:", b"#", b"#"])
        swap_calls = []
        configuration = make_configuration(needs_file_swap=True)
        switch = self.make_switch(fake, configuration, swap_calls.append)

        switch.execute("reboot", {})
        self.assertEqual(swap_calls, [])

        fake = FakeTelnet(reads=[b"gin:", b"#", b"#", b"#"])
        switch = self.make_switch(fake, configuration, swap_calls.append)
        switch.execute("sanitize", {})
        self.assertEqual(swap_calls, ["RING-S2"])

    def test_command_response_is_printed(self):
        fake = FakeTelnet(reads=[b"gin:\n", b"#", b"#\ncommand output\n#"])
        switch = self.make_switch(fake, make_configuration())
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            switch.execute("reboot", {})

        self.assertIn("command output", output.getvalue())

    def test_invalid_step_is_rejected_before_telnet_connection(self):
        configuration = make_configuration()
        configuration.models["RAX711"]["operations"]["reboot"][0]["send"] = "{invalid}"
        connection_attempts = []
        switch = sanitize_3.Switch(
            "RINGS2",
            configuration,
            telnet_factory=lambda address, timeout: connection_attempts.append(address),
        )

        with self.assertRaises(sanitize_3.ConfigurationError):
            switch.execute("reboot", {})

        self.assertEqual(connection_attempts, [])

    def test_timeout_closes_session_and_raises_operation_error(self):
        fake = FakeTelnet(failure=TimeoutError("prompt timeout"))
        switch = self.make_switch(fake, make_configuration())

        with self.assertRaises(sanitize_3.OperationError):
            switch.execute("reboot", {})

        self.assertTrue(fake.closed)

    def test_eof_and_connection_errors_close_session(self):
        for failure in (EOFError("eof"), OSError("connection failed")):
            with self.subTest(failure=type(failure).__name__):
                fake = FakeTelnet(failure=failure)
                switch = self.make_switch(fake, make_configuration())

                with self.assertRaises(sanitize_3.OperationError):
                    switch.execute("reboot", {})

                self.assertTrue(fake.closed)


if __name__ == "__main__":
    unittest.main()
