"""Pure VLED UDP protocol parsing and validation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

MAX_DATAGRAM_BYTES = 4096
MAX_TEXT_BYTES = 1023
MAX_DIMENSION = 128
MAX_LED_CELLS = 4096
VALID_MODES = frozenset({"static", "scroll"})
REQUIRED_FIELDS = frozenset(
    {
        "type",
        "width",
        "height",
        "text",
        "color",
        "brightness",
        "mode",
        "version",
    }
)


class ProtocolError(ValueError):
    """A datagram is not a valid, complete VLED state message."""


@dataclass(frozen=True, slots=True)
class VledState:
    width: int
    height: int
    text: str
    color: tuple[int, int, int]
    brightness: int
    mode: str
    version: int


DEFAULT_STATE = VledState(
    width=32,
    height=16,
    text="",
    color=(255, 255, 255),
    brightness=100,
    mode="static",
    version=0,
)


def _require_plain_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise ProtocolError(f"{field} must be an integer")
    return value


def validate_state_message(message: Mapping[str, Any]) -> VledState:
    """Validate one decoded JSON object and return an immutable state."""

    missing = sorted(REQUIRED_FIELDS.difference(message))
    if missing:
        raise ProtocolError(f"missing fields: {', '.join(missing)}")
    if message["type"] != "state":
        raise ProtocolError("type must be 'state'")

    width = _require_plain_int(message["width"], "width")
    height = _require_plain_int(message["height"], "height")
    if not 1 <= width <= MAX_DIMENSION:
        raise ProtocolError(f"width must be in 1..{MAX_DIMENSION}")
    if not 1 <= height <= MAX_DIMENSION:
        raise ProtocolError(f"height must be in 1..{MAX_DIMENSION}")
    if width * height > MAX_LED_CELLS:
        raise ProtocolError(f"width * height must not exceed {MAX_LED_CELLS}")

    text = message["text"]
    if not isinstance(text, str):
        raise ProtocolError("text must be a string")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ProtocolError(f"text must not exceed {MAX_TEXT_BYTES} UTF-8 bytes")

    color = message["color"]
    if not isinstance(color, list) or len(color) != 3:
        raise ProtocolError("color must be a list of exactly three integers")
    channels = tuple(_require_plain_int(value, f"color[{index}]")
                     for index, value in enumerate(color))
    if any(value < 0 or value > 255 for value in channels):
        raise ProtocolError("color channels must be in 0..255")

    brightness = _require_plain_int(message["brightness"], "brightness")
    if not 0 <= brightness <= 100:
        raise ProtocolError("brightness must be in 0..100")

    mode = message["mode"]
    if not isinstance(mode, str) or mode not in VALID_MODES:
        raise ProtocolError("mode must be 'static' or 'scroll'")

    version = _require_plain_int(message["version"], "version")
    if version < 0:
        raise ProtocolError("version must be non-negative")

    return VledState(
        width=width,
        height=height,
        text=text,
        color=channels,
        brightness=brightness,
        mode=mode,
        version=version,
    )


def parse_datagram(payload: bytes) -> VledState:
    """Decode and validate one complete UDP datagram."""

    if len(payload) > MAX_DATAGRAM_BYTES:
        raise ProtocolError(
            f"datagram exceeds {MAX_DATAGRAM_BYTES} bytes"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError(f"invalid UTF-8: {exc}") from exc

    try:
        message = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("JSON root must be an object")
    return validate_state_message(message)
