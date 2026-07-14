#!/usr/bin/env python3
"""Real fork-based acceptance for VLED multi-process file semantics.

This probe deliberately uses Linux ``fork`` processes rather than threads. It
checks independent opens, per-open write capacity, shared-state visibility,
concurrent progress, and the distinct POSIX case where fork inherits one open
file description. Every phase has a parent-side timeout so a lock cycle or lost
wakeup is reported instead of hanging the acceptance run forever.
"""

from __future__ import annotations

import argparse
import errno
import json
import multiprocessing as mp
import os
import queue
import sys
import time
from typing import Any


# Keep --help and static preflight usable on Windows; the real acceptance path
# below rejects platforms without Linux fork before touching /dev/vled.
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
REQUIRED_FIELDS = {
    "type", "width", "height", "text", "color", "brightness", "mode",
    "version",
}
VERBOSE = os.environ.get("VLED_VERBOSE", "") not in {"", "0"}


class Failure(RuntimeError):
    pass


def detail(message: str) -> None:
    if VERBOSE:
        print(f"  [DETAIL] {message}")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def validate_state(raw: bytes) -> dict[str, Any]:
    check(0 < len(raw) < PAGE_SIZE, "state does not fit in one page")
    try:
        state = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Failure(f"invalid UTF-8 state JSON: {exc}") from exc
    check(type(state) is dict, "state root is not an object")
    check(set(state) == REQUIRED_FIELDS, "state fields do not match contract")
    check(state["type"] == "state", "state type is not 'state'")
    check(type(state["width"]) is int and 1 <= state["width"] <= 128,
          "invalid width")
    check(type(state["height"]) is int and 1 <= state["height"] <= 128,
          "invalid height")
    check(state["width"] * state["height"] <= 4096, "invalid dimensions")
    check(type(state["text"]) is str, "text is not a string")
    color = state["color"]
    check(type(color) is list and len(color) == 3, "invalid color shape")
    check(all(type(value) is int and 0 <= value <= 255 for value in color),
          "invalid color")
    check(type(state["brightness"]) is int and
          0 <= state["brightness"] <= 100, "invalid brightness")
    check(state["mode"] in {"static", "scroll"}, "invalid mode")
    check(type(state["version"]) is int and state["version"] >= 0,
          "invalid version")
    return state


def read_fd(fd: int) -> dict[str, Any]:
    return validate_state(os.read(fd, PAGE_SIZE))


def read_current(device: str) -> dict[str, Any]:
    fd = os.open(device, os.O_RDONLY)
    try:
        return read_fd(fd)
    finally:
        os.close(fd)


def write_fd(fd: int, command: str) -> None:
    payload = command.encode("utf-8")
    written = os.write(fd, payload)
    check(written == len(payload), f"short write {written}/{len(payload)}")


def write_command(device: str, command: str) -> None:
    fd = os.open(device, os.O_WRONLY)
    try:
        write_fd(fd, command)
    finally:
        os.close(fd)


def join_or_terminate(processes: list[Any], timeout: float, label: str) -> None:
    deadline = time.monotonic() + timeout
    for process in processes:
        process.join(max(0.0, deadline - time.monotonic()))
    stuck = [process for process in processes if process.is_alive()]
    if stuck:
        for process in stuck:
            process.terminate()
        for process in stuck:
            process.join(1.0)
        raise Failure(f"{label} timed out; possible deadlock or lost wakeup")
    bad = [process.exitcode for process in processes if process.exitcode != 0]
    check(not bad, f"{label} child exit codes: {bad}")


def collect(results: Any, count: int, label: str) -> dict[str, tuple[Any, ...]]:
    items: dict[str, tuple[Any, ...]] = {}
    for _ in range(count):
        try:
            item = results.get(timeout=2.0)
        except queue.Empty as exc:
            raise Failure(f"{label} did not report every process result") from exc
        items[item[0]] = item
    failures = [item for item in items.values() if not item[1]]
    check(not failures, f"{label} failures: {failures}")
    return items


def visibility_reader(device: str, ready: Any, results: Any) -> None:
    try:
        fd = os.open(device, os.O_RDONLY)
        try:
            initial = read_fd(fd)
            ready.set()
            updated = read_fd(fd)
            results.put(("reader", True, initial, updated))
        finally:
            os.close(fd)
    except Exception as exc:
        results.put(("reader", False, repr(exc)))


def visibility_writer(device: str, ready: Any, text: str, results: Any) -> None:
    try:
        check(ready.wait(3.0), "reader did not consume initial state")
        write_command(device, f"TEXT {text}")
        results.put(("writer", True))
    except Exception as exc:
        results.put(("writer", False, repr(exc)))


def test_separate_open_visibility(ctx: Any, device: str) -> None:
    initial_text = f"mp-initial-{os.getpid()}"
    updated_text = f"mp-visible-{os.getpid()}"
    write_command(device, f"TEXT {initial_text}")
    ready = ctx.Event()
    results = ctx.Queue()
    reader = ctx.Process(target=visibility_reader,
                         args=(device, ready, results))
    writer = ctx.Process(target=visibility_writer,
                         args=(device, ready, updated_text, results))
    reader.start()
    writer.start()
    detail(
        f"T-MP-01 reader PID={reader.pid} and writer PID={writer.pid} "
        "each call open() on the same device"
    )
    join_or_terminate([reader, writer], 7.0, "T-MP-01")
    items = collect(results, 2, "T-MP-01")
    check(items["reader"][2]["text"] == initial_text,
          "reader initial state mismatch")
    check(items["reader"][3]["text"] == updated_text,
          "independent reader did not observe writer state")
    detail(
        f"T-MP-01 reader observed text {initial_text!r}, blocked, then "
        f"observed writer state {updated_text!r}"
    )
    print("PASS T-MP-01 separate processes open and share state without deadlock")


def capacity_owner(device: str, page_full: Any, peer_done: Any,
                   results: Any) -> None:
    try:
        fd = os.open(device, os.O_WRONLY)
        try:
            payload = b"STATUS" + b" " * (PAGE_SIZE - 1 - len("STATUS"))
            written = os.write(fd, payload)
            check(written == PAGE_SIZE - 1, "could not fill owner write page")
            page_full.set()
            check(peer_done.wait(3.0), "independent writer did not finish")
            try:
                os.write(fd, b"X")
            except OSError as exc:
                check(exc.errno == errno.ENOSPC,
                      f"full owner page returned errno {exc.errno}, not ENOSPC")
            else:
                raise Failure("full owner page accepted another byte")
            results.put(("owner", True))
        finally:
            os.close(fd)
    except Exception as exc:
        results.put(("owner", False, repr(exc)))
        page_full.set()


def independent_writer(device: str, page_full: Any, peer_done: Any,
                       text: str, results: Any) -> None:
    try:
        check(page_full.wait(3.0), "owner did not fill its write page")
        write_command(device, f"TEXT {text}")
        state = read_current(device)
        check(state["text"] == text, "independent writer state was not published")
        results.put(("peer", True, state["version"]))
    except Exception as exc:
        results.put(("peer", False, repr(exc)))
    finally:
        peer_done.set()


def test_independent_write_offsets(ctx: Any, device: str) -> None:
    page_full = ctx.Event()
    peer_done = ctx.Event()
    results = ctx.Queue()
    text = f"mp-independent-offset-{os.getpid()}"
    owner = ctx.Process(target=capacity_owner,
                        args=(device, page_full, peer_done, results))
    peer = ctx.Process(target=independent_writer,
                       args=(device, page_full, peer_done, text, results))
    owner.start()
    peer.start()
    detail(
        f"T-MP-02 owner PID={owner.pid} fills its PAGE_SIZE write context; "
        f"peer PID={peer.pid} opens an independent context"
    )
    join_or_terminate([owner, peer], 7.0, "T-MP-02")
    collect(results, 2, "T-MP-02")
    detail(
        f"T-MP-02 owner accepted {PAGE_SIZE - 1} bytes then returned ENOSPC; "
        "peer still wrote successfully from its own offset 0"
    )
    print("PASS T-MP-02 independent processes have independent write offsets")


def stress_writer(device: str, index: int, iterations: int,
                  start: Any, results: Any) -> None:
    try:
        start.wait()
        for turn in range(iterations):
            commands = (
                f"TEXT mp-{index}-{turn}",
                f"COLOR {(index * 37 + turn) % 256} {(turn * 11) % 256} {(turn * 17) % 256}",
                f"BRIGHTNESS {(index + turn) % 101}",
                "MODE scroll" if turn % 2 else "MODE static",
            )
            write_command(device, commands[turn % len(commands)])
        results.put((f"writer-{index}", True))
    except Exception as exc:
        results.put((f"writer-{index}", False, repr(exc)))


def stress_reader(device: str, index: int, iterations: int,
                  start: Any, results: Any) -> None:
    try:
        start.wait()
        last_version = -1
        for _ in range(iterations):
            state = read_current(device)
            check(state["version"] >= last_version, "version moved backwards")
            last_version = state["version"]
        results.put((f"reader-{index}", True))
    except Exception as exc:
        results.put((f"reader-{index}", False, repr(exc)))


def test_process_stress(ctx: Any, device: str, iterations: int) -> None:
    worker_count = 8
    start = ctx.Barrier(worker_count)
    results = ctx.Queue()
    processes = [
        ctx.Process(target=stress_writer,
                    args=(device, index, iterations, start, results))
        for index in range(4)
    ] + [
        ctx.Process(target=stress_reader,
                    args=(device, index, iterations, start, results))
        for index in range(4)
    ]
    for process in processes:
        process.start()
    detail(
        "T-MP-03 started writer PIDs="
        f"{[process.pid for process in processes[:4]]} and reader PIDs="
        f"{[process.pid for process in processes[4:]]}"
    )
    join_or_terminate(processes, 30.0, "T-MP-03")
    collect(results, worker_count, "T-MP-03")
    read_current(device)
    print(f"PASS T-MP-03 4 writers + 4 readers x {iterations} complete without deadlock")


def inherited_reader(fd: int, ready: Any, results: Any) -> None:
    try:
        ready.set()
        results.put(("shared-reader", True, read_fd(fd)))
    except Exception as exc:
        results.put(("shared-reader", False, repr(exc)))


def test_fork_shared_fd_wakeup(ctx: Any, device: str) -> None:
    fd = os.open(device, os.O_RDWR)
    reader = None
    try:
        before = read_fd(fd)
        ready = ctx.Event()
        results = ctx.Queue()
        reader = ctx.Process(target=inherited_reader, args=(fd, ready, results))
        reader.start()
        detail(
            f"T-MP-04 parent PID={os.getpid()} opened fd={fd}; child "
            f"PID={reader.pid} inherited that same open-file context"
        )
        check(ready.wait(2.0), "shared reader did not start")
        time.sleep(0.2)
        check(reader.is_alive(), "shared reader did not block after current version")
        write_fd(fd, "STATUS")
        join_or_terminate([reader], 3.0, "T-MP-04")
        items = collect(results, 1, "T-MP-04")
        check(items["shared-reader"][2] == before,
              "STATUS changed state while refreshing shared FD")
        detail(
            "T-MP-04 child blocked after consuming the version and STATUS "
            "woke it without changing JSON/version"
        )
    finally:
        if reader is not None and reader.is_alive():
            reader.terminate()
            reader.join(1.0)
        os.close(fd)
    print("PASS T-MP-04 fork-shared FD no-op write wakes blocked reader")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/vled")
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 10000:
        parser.error("--iterations must be in 1..10000")
    if "fork" not in mp.get_all_start_methods():
        parser.error("this target-Linux probe requires multiprocessing method 'fork'")
    if not os.path.exists(args.device):
        parser.error(f"device does not exist: {args.device}")

    ctx = mp.get_context("fork")
    try:
        print(f"VLED multiprocess probe: device={args.device} page_size={PAGE_SIZE}")
        test_separate_open_visibility(ctx, args.device)
        test_independent_write_offsets(ctx, args.device)
        test_process_stress(ctx, args.device, args.iterations)
        test_fork_shared_fd_wakeup(ctx, args.device)
    except Exception as exc:
        print(f"FAIL VLED multiprocess probe: {exc}", file=sys.stderr)
        return 1
    print("VLED multiprocess probe: T-MP-01..04 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
