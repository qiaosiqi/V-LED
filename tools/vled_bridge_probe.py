#!/usr/bin/env python3
"""Black-box bridge probe, including P5 event-driven behavior and metrics."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path


def process_cpu_ticks(pid: int) -> int:
    fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").split()
    return int(fields[13]) + int(fields[14])


def open_fifo_writer(path: Path, process: subprocess.Popen[str]) -> int:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("bridge exited before opening the device")
        try:
            return os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as exc:
            if exc.errno != 6:  # ENXIO: reader has not opened the FIFO yet.
                raise
            time.sleep(0.01)
    raise RuntimeError("bridge did not open the device within 2 seconds")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge", default=str(Path(__file__).with_name("vled_bridge")))
    args = parser.parse_args()

    valid = json.dumps({
        "type": "state", "width": 32, "height": 16, "text": "bridge-probe",
        "color": [1, 2, 3], "brightness": 44, "mode": "static", "version": 9,
    }, separators=(",", ":"))
    latest = json.dumps({
        "type": "state", "width": 32, "height": 16, "text": "bridge-latest",
        "color": [4, 5, 6], "brightness": 45, "mode": "scroll", "version": 10,
    }, separators=(",", ":"))

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(0.35)
        port = receiver.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix="vled_bridge-") as directory:
            state_file = Path(directory, "vled.fifo")
            os.mkfifo(state_file)
            process = subprocess.Popen(
                [args.bridge, "127.0.0.1", str(port), str(state_file), "100"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            writer = -1
            try:
                writer = open_fifo_writer(state_file, process)
                os.write(writer, b'{"type":"state"}')
                try:
                    receiver.recvfrom(4096)
                except TimeoutError:
                    pass
                else:
                    raise RuntimeError("bridge transmitted an invalid partial state")

                # A long-lived bridge keeps using this already-open device even
                # after its pathname disappears. A periodic reopen implementation
                # cannot deliver the following two states.
                state_file.unlink()
                os.write(writer, valid.encode("utf-8"))
                payload, _ = receiver.recvfrom(4096)
                if payload.decode("utf-8") != valid:
                    raise RuntimeError("bridge payload differs from validated source state")

                idle_start_ticks = process_cpu_ticks(process.pid)
                idle_started = time.monotonic()
                try:
                    receiver.recvfrom(4096)
                except TimeoutError:
                    pass
                else:
                    raise RuntimeError("bridge resent an unchanged state")
                idle_seconds = time.monotonic() - idle_started
                idle_cpu_ticks = process_cpu_ticks(process.pid) - idle_start_ticks

                sent_at = time.monotonic()
                os.write(writer, latest.encode("utf-8"))
                payload, _ = receiver.recvfrom(4096)
                latency_ms = (time.monotonic() - sent_at) * 1000
                if payload.decode("utf-8") != latest:
                    raise RuntimeError("bridge did not converge to the latest state")
            finally:
                if writer >= 0:
                    os.close(writer)
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
    print("PASS T-POLL-08 event bridge: "
          f"idle={idle_seconds:.3f}s cpu_ticks={idle_cpu_ticks} "
          f"sends=2 response_latency_ms={latency_ms:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
