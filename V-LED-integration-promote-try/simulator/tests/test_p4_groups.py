import argparse
import json
import unittest
from unittest import mock

from tools.vled_verify import READ_FLAGS, parse_groups, read_state


class P4GroupSelectionTests(unittest.TestCase):
    def test_accepts_ordered_subsets(self):
        self.assertEqual(parse_groups("cli,commands"), ["cli", "commands"])
        self.assertEqual(parse_groups("concurrency"), ["concurrency"])

    def test_rejects_unknown_empty_and_duplicate_groups(self):
        for value in ("", "boundary", "cli,", "cli,cli"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_groups(value)

    def test_read_state_stops_at_first_complete_p5_snapshot(self):
        first = json.dumps({
            "type": "state", "width": 32, "height": 16, "text": "old",
            "color": [1, 2, 3], "brightness": 50, "mode": "static",
            "version": 7,
        }, separators=(",", ":")).encode()
        second = json.dumps({
            "type": "state", "width": 32, "height": 16, "text": "new",
            "color": [4, 5, 6], "brightness": 60, "mode": "scroll",
            "version": 8,
        }, separators=(",", ":")).encode()
        reads = [first[:17], first[17:], second, BlockingIOError()]

        with mock.patch("tools.vled_verify.os.open", return_value=123) as open_mock, \
             mock.patch("tools.vled_verify.os.read", side_effect=reads) as read_mock, \
             mock.patch("tools.vled_verify.os.close") as close_mock:
            state = read_state("/dev/vled", chunk=17)

        self.assertEqual(state["version"], 7)
        self.assertEqual(state["text"], "old")
        self.assertEqual(read_mock.call_count, 2)
        open_mock.assert_called_once_with("/dev/vled", READ_FLAGS)
        close_mock.assert_called_once_with(123)


if __name__ == "__main__":
    unittest.main()
