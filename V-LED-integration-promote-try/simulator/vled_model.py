"""GUI-independent simulator display and bounded-log model."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Iterable

try:
    from .vled_protocol import DEFAULT_STATE, VledState
except ImportError:  # Direct script execution from simulator/.
    from vled_protocol import DEFAULT_STATE, VledState


@dataclass(slots=True)
class SimulatorModel:
    udp_state: VledState = DEFAULT_STATE
    manual_color: tuple[int, int, int] | None = None
    manual_brightness: int | None = None
    local_text_cleared: bool = False

    def apply_udp(self, state: VledState) -> None:
        self.udp_state = state
        self.local_text_cleared = False

    def set_manual_color(self, color: Iterable[int]) -> None:
        candidate = tuple(color)
        if len(candidate) != 3 or any(type(value) is not int for value in candidate):
            raise ValueError("manual color must contain three integers")
        if any(value < 0 or value > 255 for value in candidate):
            raise ValueError("manual color channels must be in 0..255")
        self.manual_color = candidate

    def restore_udp_color(self) -> None:
        self.manual_color = None

    def set_manual_brightness(self, brightness: int) -> None:
        if type(brightness) is not int or not 0 <= brightness <= 100:
            raise ValueError("manual brightness must be in 0..100")
        self.manual_brightness = brightness

    def restore_udp_brightness(self) -> None:
        self.manual_brightness = None

    def clear_local_preview(self) -> None:
        self.local_text_cleared = True

    @property
    def display_state(self) -> VledState:
        return replace(
            self.udp_state,
            text="" if self.local_text_cleared else self.udp_state.text,
            color=self.manual_color or self.udp_state.color,
            brightness=(
                self.manual_brightness
                if self.manual_brightness is not None
                else self.udp_state.brightness
            ),
        )


class BoundedLog:
    def __init__(self, max_entries: int = 200) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._entries: deque[str] = deque(maxlen=max_entries)

    def append(self, entry: str) -> None:
        self._entries.append(entry)

    @property
    def entries(self) -> tuple[str, ...]:
        return tuple(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
