#!/usr/bin/env python3
"""Black-box P3 probe for bridge validation, UDP delivery and signal exit."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge", default=str(Path(__file__).with_name("vled_bridge")))
    args = parser.parse_args()

    valid = json.dumps({
        "type": "state", "width": 32, "height": 16, "text": "bridge-probe",
        "color": [1, 2, 3], "brightness": 44, "mode": "static", "version": 9,
    }, separators=(",", ":"))

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(0.35)
        port = receiver.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix="vled-bridge-") as directory:
            state_file = Path(directory, "state.json")
            state_file.write_text('{"type":"state"}', encoding="utf-8")
            process = subprocess.Popen(
                [args.bridge, "127.0.0.1", str(port), str(state_file), "50"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                try:
                    receiver.recvfrom(4096)
                except TimeoutError:
                    pass
                else:
                    raise RuntimeError("bridge transmitted an invalid partial state")

                state_file.write_text(valid, encoding="utf-8")
                payload, _ = receiver.recvfrom(4096)
                if payload.decode("utf-8") != valid:
                    raise RuntimeError("bridge payload differs from validated source state")
            finally:
                started = time.monotonic()
                process.terminate()
                stdout, stderr = process.communicate(timeout=2)
                elapsed = time.monotonic() - started
            if process.returncode != 0:
                raise RuntimeError(f"bridge signal exit={process.returncode}; stderr={stderr}")
            if elapsed > 2:
                raise RuntimeError(f"bridge took {elapsed:.3f}s to stop")
            if "skip non-state payload" not in stderr:
                raise RuntimeError("bridge did not diagnose rejected payload")
            if "UDP bridge stopped" not in stdout:
                raise RuntimeError("bridge did not report clean shutdown")

    print("PASS T-BRIDGE-01..04 validation, UDP delivery and SIGTERM cleanup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
