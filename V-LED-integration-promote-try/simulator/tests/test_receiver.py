from dataclasses import FrozenInstanceError
import inspect
import json
import queue
import socket
import time
import unittest

import simulator.vled_receiver as receiver_module
from simulator.vled_protocol import VledState
from simulator.vled_receiver import ErrorEvent, ListenerEvent, StateEvent, UdpReceiver


def payload(version=1):
    return json.dumps(
        {
            "type": "state",
            "width": 32,
            "height": 16,
            "text": f"state-{version}",
            "color": [1, 2, 3],
            "brightness": 50,
            "mode": "scroll",
            "version": version,
        }
    ).encode("utf-8")


def next_matching(events, event_type, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            event = events.get(timeout=max(0.01, deadline - time.monotonic()))
        except queue.Empty:
            break
        if isinstance(event, event_type):
            return event
    raise AssertionError(f"did not receive {event_type.__name__}")


class ReceiverTests(unittest.TestCase):
    def test_receiver_emits_state_error_and_stops_cleanly(self):
        events = queue.Queue(maxsize=64)
        receiver = UdpReceiver(events, host="127.0.0.1", port=0, socket_timeout=0.05)
        receiver.start()
        listening = next_matching(events, ListenerEvent)
        self.assertEqual(listening.status, "listening")
        self.assertIsNotNone(listening.address)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sender.sendto(payload(9), listening.address)
            state_event = next_matching(events, StateEvent)
            self.assertEqual(state_event.state.version, 9)
            self.assertEqual(state_event.state.text, "state-9")

            sender.sendto(b"not-json", listening.address)
            error_event = next_matching(events, ErrorEvent)
            self.assertIn("invalid JSON", error_event.reason)
        finally:
            sender.close()
            receiver.stop()

        self.assertTrue(receiver.join(1.0))
        self.assertFalse(receiver.is_alive)

    def test_events_are_immutable_and_queue_is_bounded(self):
        events = queue.Queue(maxsize=3)
        receiver = UdpReceiver(events)
        for version in range(20):
            receiver._emit(
                StateEvent(
                    VledState(32, 16, "x", (1, 2, 3), 50, "static", version),
                    ("127.0.0.1", 9000),
                )
            )
        self.assertEqual(events.qsize(), 3)
        queued = []
        while not events.empty():
            queued.append(events.get_nowait())
        self.assertEqual([event.state.version for event in queued], [17, 18, 19])
        with self.assertRaises(FrozenInstanceError):
            queued[-1].state.version = 100

    def test_receiver_module_has_no_tk_dependency(self):
        source = inspect.getsource(receiver_module)
        self.assertNotIn("tkinter", source)
        self.assertNotIn("Tk(", source)


if __name__ == "__main__":
    unittest.main()
