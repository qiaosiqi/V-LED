import importlib
import unittest

from simulator.vled_model import BoundedLog, SimulatorModel
from simulator.vled_protocol import VledState


def state(version, color=(10, 20, 30), brightness=40, text="udp"):
    return VledState(32, 16, text, color, brightness, "static", version)


class ModelTests(unittest.TestCase):
    def test_manual_overrides_survive_udp_and_restore_latest_values(self):
        model = SimulatorModel()
        model.apply_udp(state(1))
        model.set_manual_color((200, 201, 202))
        model.set_manual_brightness(77)

        model.apply_udp(state(2, color=(1, 2, 3), brightness=4, text="latest"))
        display = model.display_state
        self.assertEqual(display.color, (200, 201, 202))
        self.assertEqual(display.brightness, 77)
        self.assertEqual(display.text, "latest")
        self.assertEqual(model.udp_state.color, (1, 2, 3))
        self.assertEqual(model.udp_state.brightness, 4)

        model.restore_udp_color()
        model.restore_udp_brightness()
        self.assertEqual(model.display_state.color, (1, 2, 3))
        self.assertEqual(model.display_state.brightness, 4)

    def test_local_clear_is_preview_only_and_new_udp_restores_text(self):
        model = SimulatorModel()
        model.apply_udp(state(1, text="driver text"))
        model.clear_local_preview()
        self.assertEqual(model.display_state.text, "")
        self.assertEqual(model.udp_state.text, "driver text")

        model.apply_udp(state(2, text="new driver text"))
        self.assertEqual(model.display_state.text, "new driver text")

    def test_bounded_log_never_exceeds_limit(self):
        history = BoundedLog(max_entries=5)
        for index in range(20):
            history.append(f"entry-{index}")
        self.assertEqual(len(history), 5)
        self.assertEqual(history.entries[0], "entry-15")
        self.assertEqual(history.entries[-1], "entry-19")

    def test_importing_gui_module_does_not_create_a_window(self):
        module = importlib.import_module("simulator.vled_sim")
        self.assertIsNone(module.tk._default_root)


if __name__ == "__main__":
    unittest.main()
