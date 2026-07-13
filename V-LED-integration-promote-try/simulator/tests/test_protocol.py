import json
import unittest

from simulator.vled_protocol import (
    MAX_DATAGRAM_BYTES,
    MAX_TEXT_BYTES,
    ProtocolError,
    VledState,
    parse_datagram,
)


def valid_message(**overrides):
    message = {
        "type": "state",
        "width": 32,
        "height": 16,
        "text": "Hello 中文",
        "color": [1, 2, 255],
        "brightness": 70,
        "mode": "static",
        "version": 3,
    }
    message.update(overrides)
    return message


def encode(message):
    return json.dumps(message, ensure_ascii=False).encode("utf-8")


class ProtocolTests(unittest.TestCase):
    def test_accepts_complete_static_and_scroll_states(self):
        for mode in ("static", "scroll"):
            with self.subTest(mode=mode):
                state = parse_datagram(encode(valid_message(mode=mode)))
                self.assertIsInstance(state, VledState)
                self.assertEqual(state.mode, mode)
                self.assertEqual(state.color, (1, 2, 255))
                self.assertEqual(state.text, "Hello 中文")

    def test_rejects_missing_fields_without_partial_state(self):
        for field in valid_message():
            message = valid_message()
            del message[field]
            with self.subTest(field=field), self.assertRaises(ProtocolError):
                parse_datagram(encode(message))

    def test_rejects_wrong_types_ranges_and_modes(self):
        invalid = [
            {"width": True},
            {"width": 0},
            {"height": 129},
            {"width": 128, "height": 128},
            {"text": 7},
            {"text": "x" * (MAX_TEXT_BYTES + 1)},
            {"color": [1, 2]},
            {"color": [1, 2, 256]},
            {"color": [1, False, 3]},
            {"brightness": -1},
            {"brightness": 101},
            {"mode": "blink"},
            {"version": -1},
            {"version": 1.5},
        ]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ProtocolError):
                parse_datagram(encode(valid_message(**change)))

    def test_rejects_bad_encoding_json_root_and_type(self):
        invalid_payloads = [
            b"\xff\xfe",
            b"not-json",
            b"[]",
            encode(valid_message(type="frame")),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload[:20]), self.assertRaises(ProtocolError):
                parse_datagram(payload)

    def test_rejects_oversize_datagram_before_decoding(self):
        with self.assertRaisesRegex(ProtocolError, "datagram exceeds"):
            parse_datagram(b" " * (MAX_DATAGRAM_BYTES + 1))


if __name__ == "__main__":
    unittest.main()
