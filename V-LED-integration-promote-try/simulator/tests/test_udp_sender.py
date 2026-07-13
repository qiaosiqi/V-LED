import contextlib
import io
import json
import socket
import sys
import unittest
from unittest import mock

from simulator import test_udp


class UdpSenderTests(unittest.TestCase):
    def test_sends_one_validated_datagram(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1)
            port = receiver.getsockname()[1]
            argv = ["test_udp.py", "--host", "127.0.0.1", "--port", str(port),
                    "--text", "中文 smoke", "--mode", "static",
                    "--brightness", "50", "--color", "1", "2", "3", "--version", "7"]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(test_udp.main(), 0)
            payload, _ = receiver.recvfrom(4096)
        message = json.loads(payload.decode("utf-8"))
        self.assertEqual(message["text"], "中文 smoke")
        self.assertEqual(message["color"], [1, 2, 3])
        self.assertEqual(message["version"], 7)

    def test_rejects_invalid_state_before_send(self):
        argv = ["test_udp.py", "--brightness", "101"]
        with mock.patch.object(sys, "argv", argv), self.assertRaises(SystemExit) as raised:
            test_udp.main()
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
