#!/usr/bin/env python3
"""Executable P3 business, error-path and concurrency acceptance for /dev/vled."""

from __future__ import annotations

import argparse
import errno
import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
REQUIRED_FIELDS = {
    "type", "width", "height", "text", "color", "brightness", "mode", "version"
}


class Failure(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def validate_state(raw: bytes) -> dict[str, Any]:
    check(0 < len(raw) < PAGE_SIZE, f"state length must be 1..{PAGE_SIZE - 1}")
    try:
        state = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Failure(f"invalid UTF-8 JSON: {exc}") from exc
    check(type(state) is dict, "state root is not an object")
    check(set(state) == REQUIRED_FIELDS, f"unexpected fields: {set(state) ^ REQUIRED_FIELDS}")
    check(state["type"] == "state", "type is not state")
    check(type(state["width"]) is int and 1 <= state["width"] <= 128, "invalid width")
    check(type(state["height"]) is int and 1 <= state["height"] <= 128, "invalid height")
    check(state["width"] * state["height"] <= 4096, "invalid LED cell count")
    check(type(state["text"]) is str, "text is not a string")
    check(len(state["text"].encode("utf-8")) <= 1023, "text exceeds protocol limit")
    color = state["color"]
    check(type(color) is list and len(color) == 3, "invalid color shape")
    check(all(type(value) is int and 0 <= value <= 255 for value in color), "invalid color")
    check(type(state["brightness"]) is int and 0 <= state["brightness"] <= 100,
          "invalid brightness")
    check(state["mode"] in {"static", "scroll"}, "invalid mode")
    check(type(state["version"]) is int and state["version"] >= 0, "invalid version")
    return state


def read_state(device: str, chunk: int = PAGE_SIZE) -> dict[str, Any]:
    fd = os.open(device, os.O_RDONLY)
    try:
        parts: list[bytes] = []
        while True:
            block = os.read(fd, chunk)
            if not block:
                break
            parts.append(block)
        return validate_state(b"".join(parts))
    finally:
        os.close(fd)


def write_command(device: str, command: str, expected_errno: int | None = None) -> None:
    payload = command.encode("utf-8")
    fd = os.open(device, os.O_WRONLY)
    try:
        try:
            written = os.write(fd, payload)
        except OSError as exc:
            if expected_errno is None:
                raise Failure(f"{command!r} failed: {exc}") from exc
            check(exc.errno == expected_errno,
                  f"{command!r}: expected errno {expected_errno}, got {exc.errno}")
            return
        if expected_errno is not None:
            raise Failure(f"{command!r}: expected errno {expected_errno}, write succeeded")
        check(written == len(payload), f"{command!r}: short write {written}/{len(payload)}")
    finally:
        os.close(fd)


def expect_change(device: str, command: str, field: str, value: Any) -> dict[str, Any]:
    before = read_state(device)
    write_command(device, command)
    after = read_state(device)
    check(after[field] == value, f"{command!r}: {field} did not become {value!r}")
    expected = before["version"] + (before[field] != value)
    check(after["version"] == expected,
          f"{command!r}: version {after['version']} != expected {expected}")
    write_command(device, command)
    repeated = read_state(device)
    check(repeated == after, f"{command!r}: repeated value changed state/version")
    return after


def expect_rollback(device: str, command: str, expected_errno: int) -> None:
    before = read_state(device)
    write_command(device, command, expected_errno)
    after = read_state(device)
    check(after == before, f"{command!r}: failed write changed shared state")


def test_cli(cli: Path, device: str) -> None:
    good = subprocess.run([str(cli), "read", device], capture_output=True, check=False)
    check(good.returncode == 0, f"CLI read failed: {good.stderr.decode(errors='replace')}")
    validate_state(good.stdout)
    bad_cases = ([str(cli)], [str(cli), "read", device, "extra"],
                 [str(cli), "write"], [str(cli), "loop", "0", device],
                 [str(cli), "unknown"])
    for command in bad_cases:
        result = subprocess.run(command, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, check=False)
        check(result.returncode != 0, f"CLI accepted invalid argv: {command[1:]}")


def test_commands(device: str) -> None:
    expect_change(device, "TEXT", "text", "")
    expect_change(device, "TEXT ASCII", "text", "ASCII")
    expect_change(device, 'TEXT 中文 "quote" \\slash', "text", '中文 "quote" \\slash')
    for command, value in (("COLOR 0 0 0", [0, 0, 0]),
                           ("COLOR 255 255 255", [255, 255, 255]),
                           ("BRIGHTNESS 0", 0), ("BRIGHTNESS 100", 100),
                           ("MODE scroll", "scroll"), ("MODE static", "static")):
        field = "color" if command.startswith("COLOR") else (
            "brightness" if command.startswith("BRIGHTNESS") else "mode")
        expect_change(device, command, field, value)

    for command in ("COLOR -1 0 0", "COLOR 0 0 256", "COLOR 1 2", "COLOR 1 2 3 4",
                    "COLOR red 0 0", "BRIGHTNESS -1", "BRIGHTNESS 101",
                    "BRIGHTNESS bright", "BRIGHTNESS 1 2", "MODE blink", "MODE",
                    "MODE static extra", "", "UNKNOWN", "mode static"):
        expect_rollback(device, command, errno.EINVAL)
    expect_rollback(device, "PIXEL 0 0 1", errno.EOPNOTSUPP)

    expect_change(device, "TEXT clear-me", "text", "clear-me")
    before_clear = read_state(device)
    write_command(device, "CLEAR")
    after_clear = read_state(device)
    check(after_clear["text"] == "", "CLEAR did not empty text")
    check(after_clear["version"] == before_clear["version"] + 1, "CLEAR version mismatch")
    for field in REQUIRED_FIELDS - {"text", "version"}:
        check(after_clear[field] == before_clear[field], f"CLEAR changed {field}")
    write_command(device, "CLEAR")
    check(read_state(device) == after_clear, "repeated CLEAR changed state/version")
    write_command(device, "STATUS")
    check(read_state(device) == after_clear, "STATUS changed state/version")


@dataclass
class StressResult:
    failures: list[str]
    lock: threading.Lock

    def record(self, message: str) -> None:
        with self.lock:
            self.failures.append(message)


def test_concurrency(device: str, iterations: int) -> None:
    result = StressResult([], threading.Lock())
    start = threading.Barrier(8)

    def writer(index: int) -> None:
        try:
            start.wait()
            for turn in range(iterations):
                choices = (f"TEXT writer-{index}-{turn}",
                           f"COLOR {(index * 41 + turn) % 256} {(turn * 7) % 256} {(turn * 13) % 256}",
                           f"BRIGHTNESS {(index + turn) % 101}",
                           "MODE scroll" if turn % 2 else "MODE static")
                write_command(device, choices[turn % len(choices)])
        except Exception as exc:  # preserve all worker failures for the main thread
            result.record(f"writer {index}: {exc}")

    def reader(index: int) -> None:
        try:
            start.wait()
            last_version = -1
            for _ in range(iterations):
                state = read_state(device, chunk=7 + index)
                check(state["version"] >= last_version, "version moved backwards")
                last_version = state["version"]
        except Exception as exc:
            result.record(f"reader {index}: {exc}")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    threads += [threading.Thread(target=reader, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    check(all(not thread.is_alive() for thread in threads), "concurrency test timed out")
    check(not result.failures, "; ".join(result.failures))
    validate_state(json.dumps(read_state(device), ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/vled")
    parser.add_argument("--cli", default=str(Path(__file__).with_name("vled_cli")))
    parser.add_argument("--iterations", type=int, default=200)
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 10000:
        parser.error("--iterations must be in 1..10000")

    tests = (("T-CLI", lambda: test_cli(Path(args.cli), args.device)),
             ("T-CMD", lambda: test_commands(args.device)),
             ("T-CON", lambda: test_concurrency(args.device, args.iterations)))
    print(f"VLED P3 verify: device={args.device} page_size={PAGE_SIZE}")
    for test_id, test in tests:
        try:
            test()
        except Exception as exc:
            print(f"FAIL {test_id}: {exc}", file=sys.stderr)
            return 1
        print(f"PASS {test_id}")
    print("VLED P3 verify: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
