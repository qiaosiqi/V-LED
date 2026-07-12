import argparse
import unittest

from tools.vled_verify import parse_groups


class P4GroupSelectionTests(unittest.TestCase):
    def test_accepts_ordered_subsets(self):
        self.assertEqual(parse_groups("cli,commands"), ["cli", "commands"])
        self.assertEqual(parse_groups("concurrency"), ["concurrency"])

    def test_rejects_unknown_empty_and_duplicate_groups(self):
        for value in ("", "boundary", "cli,", "cli,cli"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_groups(value)


if __name__ == "__main__":
    unittest.main()
