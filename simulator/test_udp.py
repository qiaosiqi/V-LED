import argparse
import json
import socket

try:
    from simulator.vled_protocol import ProtocolError, validate_state_message
except ModuleNotFoundError:
    from vled_protocol import ProtocolError, validate_state_message

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000

def main() -> int:
    parser = argparse.ArgumentParser(description="Send one validated VLED state datagram")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--text", default="Test Demo Text")
    parser.add_argument("--mode", choices=("static", "scroll"), default="scroll")
    parser.add_argument("--brightness", type=int, default=70)
    parser.add_argument("--color", type=int, nargs=3, default=(0, 255, 255),
                        metavar=("R", "G", "B"))
    parser.add_argument("--version", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in 1..65535")

    message = {
        "type": "state", "width": 32, "height": 16, "text": args.text,
        "color": list(args.color), "brightness": args.brightness,
        "mode": args.mode, "version": args.version,
    }
    try:
        validate_state_message(message)
    except ProtocolError as exc:
        parser.error(str(exc))
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sent = sock.sendto(payload, (args.host, args.port))
    if sent != len(payload):
        raise RuntimeError(f"short UDP send: {sent}/{len(payload)}")
    print(f"sent {sent} bytes to {args.host}:{args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
