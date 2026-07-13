#!/usr/bin/env python3
"""VLED real multiprocess acceptance and controlled deadlock demonstration.

The driver checks operate on /dev/vled.  The deadlock demonstration is kept in
user space: two disposable child processes intentionally acquire two locks in
opposite order, the parent detects the lack of progress, terminates them, and
then proves that a single global lock order completes normally.  Deliberately
deadlocking a kernel module would make the target VM unsafe to continue using.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import queue
import sys
import time
from typing import Any


PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
READ_FLAGS = os.O_RDONLY | os.O_NONBLOCK
REQUIRED_FIELDS = {
    "type", "width", "height", "text", "color", "brightness", "mode",
    "version",
}


class Failure(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def validate_state(raw: bytes) -> dict[str, Any]:
    check(0 < len(raw) < PAGE_SIZE, "state length is outside one page")
    try:
        state = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Failure(f"invalid UTF-8 state JSON: {exc}") from exc
    check(type(state) is dict, "state root is not an object")
    check(set(state) == REQUIRED_FIELDS, "state fields do not match the contract")
    check(state["type"] == "state", "state type is not 'state'")
    check(type(state["width"]) is int and 1 <= state["width"] <= 128,
          "invalid width")
    check(type(state["height"]) is int and 1 <= state["height"] <= 128,
          "invalid height")
    check(state["width"] * state["height"] <= 4096, "invalid LED cell count")
    check(type(state["text"]) is str, "text is not a string")
    color = state["color"]
    check(type(color) is list and len(color) == 3, "invalid color shape")
    check(all(type(value) is int and 0 <= value <= 255 for value in color),
          "invalid color")
    check(type(state["brightness"]) is int and 0 <= state["brightness"] <= 100,
          "invalid brightness")
    check(state["mode"] in {"static", "scroll"}, "invalid mode")
    check(type(state["version"]) is int and state["version"] >= 0,
          "invalid version")
    return state


def read_snapshot_fd(fd: int, first: bytes = b"", chunk: int = PAGE_SIZE) -> dict[str, Any]:
    data = bytearray(first)
    while True:
        try:
            block = os.read(fd, chunk)
        except BlockingIOError as exc:
            raise Failure("snapshot ended before a complete JSON object") from exc
        if not block:
            raise Failure("device returned EOF before a complete JSON object")
        data.extend(block)
        try:
            return validate_state(bytes(data))
        except Failure:
            if len(data) >= PAGE_SIZE:
                raise


def read_current(device: str) -> dict[str, Any]:
    fd = os.open(device, READ_FLAGS)
    try:
        return read_snapshot_fd(fd)
    finally:
        os.close(fd)


def write_command(device: str, command: str, fd: int | None = None) -> None:
    payload = command.encode("utf-8")
    owned_fd = fd is None
    target = os.open(device, os.O_WRONLY) if owned_fd else fd
    assert target is not None
    try:
        written = os.write(target, payload)
        check(written == len(payload), f"short write {written}/{len(payload)}")
    finally:
        if owned_fd:
            os.close(target)


def child_long_lived_reader(device: str, ready: Any, results: Any) -> None:
    try:
        fd = os.open(device, os.O_RDONLY)
        try:
            initial = validate_state(os.read(fd, PAGE_SIZE))
            ready.set()
            updated = validate_state(os.read(fd, PAGE_SIZE))
            results.put(("reader", True, initial, updated))
        finally:
            os.close(fd)
    except Exception as exc:
        results.put(("reader", False, repr(exc)))


def child_visible_writer(device: str, ready: Any, text: str, results: Any) -> None:
    try:
        check(ready.wait(3.0), "reader did not consume its initial version")
        write_command(device, f"TEXT {text}")
        results.put(("writer", True))
    except Exception as exc:
        results.put(("writer", False, repr(exc)))


def child_partial_reader(
    device: str, prefix_ready: Any, update_done: Any, results: Any
) -> None:
    try:
        fd = os.open(device, READ_FLAGS)
        try:
            prefix = os.read(fd, 23)
            check(prefix, "failed to read old snapshot prefix")
            prefix_ready.set()
            check(update_done.wait(3.0), "writer did not publish the new state")
            old_state = read_snapshot_fd(fd, first=prefix, chunk=19)
            results.put(("old-reader", True, old_state))
        finally:
            os.close(fd)
    except Exception as exc:
        results.put(("old-reader", False, repr(exc)))


def child_snapshot_writer(
    device: str, prefix_ready: Any, update_done: Any, new_text: str, results: Any
) -> None:
    try:
        check(prefix_ready.wait(3.0), "reader did not capture the old prefix")
        write_command(device, f"TEXT {new_text}")
        new_state = read_current(device)
        results.put(("new-writer", True, new_state))
    except Exception as exc:
        results.put(("new-writer", False, repr(exc)))
    finally:
        update_done.set()


def stress_writer(device: str, index: int, iterations: int, start: Any, results: Any) -> None:
    try:
        start.wait()
        for turn in range(iterations):
            commands = (
                f"TEXT mp-writer-{index}-{turn}",
                f"COLOR {(index * 37 + turn) % 256} {(turn * 11) % 256} {(turn * 17) % 256}",
                f"BRIGHTNESS {(index + turn) % 101}",
                "MODE scroll" if turn % 2 else "MODE static",
            )
            write_command(device, commands[turn % len(commands)])
        results.put((f"writer-{index}", True))
    except Exception as exc:
        results.put((f"writer-{index}", False, repr(exc)))


def stress_reader(device: str, index: int, iterations: int, start: Any, results: Any) -> None:
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


def child_shared_fd_reader(fd: int, ready: Any, results: Any) -> None:
    try:
        ready.set()
        state = validate_state(os.read(fd, PAGE_SIZE))
        results.put(("shared-reader", True, state))
    except Exception as exc:
        results.put(("shared-reader", False, repr(exc)))


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
        raise Failure(f"{label} timed out; possible driver deadlock")
    bad = [process.exitcode for process in processes if process.exitcode != 0]
    check(not bad, f"{label} child exit codes: {bad}")


def collect_results(results: Any, count: int, label: str) -> dict[str, tuple[Any, ...]]:
    collected: dict[str, tuple[Any, ...]] = {}
    for _ in range(count):
        try:
            item = results.get(timeout=2.0)
        except queue.Empty as exc:
            raise Failure(f"{label} did not report every child result") from exc
        collected[item[0]] = item
    failures = [item for item in collected.values() if not item[1]]
    check(not failures, f"{label} failures: {failures}")
    return collected


def test_cross_process_visibility(ctx: Any, device: str) -> None:
    write_command(device, "TEXT mp-initial")
    text = f"mp-visible-{os.getpid()}"
    ready = ctx.Event()
    results = ctx.Queue()
    reader = ctx.Process(target=child_long_lived_reader,
                         args=(device, ready, results))
    writer = ctx.Process(target=child_visible_writer,
                         args=(device, ready, text, results))
    reader.start()
    writer.start()
    join_or_terminate([reader, writer], 6.0, "T-MP-01")
    collected = collect_results(results, 2, "T-MP-01")
    check(collected["reader"][2]["text"] == "mp-initial",
          "reader initial state mismatch")
    check(collected["reader"][3]["text"] == text,
          "reader did not observe the writer's shared-state update")
    print("PASS T-MP-01 independent processes share state and wait without deadlock")


def test_process_offsets_and_snapshot(ctx: Any, device: str) -> None:
    old_text = f"mp-old-{os.getpid()}"
    new_text = f"mp-new-{os.getpid()}"
    write_command(device, f"TEXT {old_text}")
    prefix_ready = ctx.Event()
    update_done = ctx.Event()
    results = ctx.Queue()
    reader = ctx.Process(target=child_partial_reader,
                         args=(device, prefix_ready, update_done, results))
    writer = ctx.Process(target=child_snapshot_writer,
                         args=(device, prefix_ready, update_done, new_text, results))
    reader.start()
    writer.start()
    join_or_terminate([reader, writer], 6.0, "T-MP-02")
    collected = collect_results(results, 2, "T-MP-02")
    check(collected["old-reader"][2]["text"] == old_text,
          "partial reader mixed old and new snapshots")
    check(collected["new-writer"][2]["text"] == new_text,
          "new independent open did not start from the latest state")
    print("PASS T-MP-02 per-open offsets and stable snapshots are process-independent")


def test_multiprocess_stress(ctx: Any, device: str, iterations: int) -> None:
    worker_count = 8
    start = ctx.Barrier(worker_count)
    results = ctx.Queue()
    processes = [
        ctx.Process(target=stress_writer,
                    args=(device, index, iterations, start, results))
        for index in range(4)
    ]
    processes += [
        ctx.Process(target=stress_reader,
                    args=(device, index, iterations, start, results))
        for index in range(4)
    ]
    for process in processes:
        process.start()
    join_or_terminate(processes, 30.0, "T-MP-03")
    collect_results(results, worker_count, "T-MP-03")
    validate_state(json.dumps(read_current(device), ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8"))
    print(f"PASS T-MP-03 4 writers + 4 readers x {iterations} completed safely")


def test_shared_fd_status_wakeup(ctx: Any, device: str) -> None:
    fd = os.open(device, os.O_RDWR)
    reader = None
    try:
        before = validate_state(os.read(fd, PAGE_SIZE))
        ready = ctx.Event()
        results = ctx.Queue()
        reader = ctx.Process(target=child_shared_fd_reader, args=(fd, ready, results))
        reader.start()
        check(ready.wait(2.0), "shared reader did not start")
        time.sleep(0.2)
        check(reader.is_alive(), "shared reader did not block after consuming the version")
        write_command(device, "STATUS", fd=fd)
        join_or_terminate([reader], 3.0, "T-MP-04")
        collected = collect_results(results, 1, "T-MP-04")
        after = collected["shared-reader"][2]
        check(after == before, "STATUS changed state/version while refreshing the shared FD")
    finally:
        if reader is not None and reader.is_alive():
            reader.terminate()
            reader.join(1.0)
        os.close(fd)
    print("PASS T-MP-04 fork-shared FD STATUS wakes its blocked reader")


def abba_worker(first: Any, second: Any, first_locked: Any, go: Any) -> None:
    first.acquire()
    first_locked.set()
    go.wait()
    second.acquire()


def ordered_worker(first: Any, second: Any, results: Any, name: str) -> None:
    try:
        with first:
            time.sleep(0.05)
            with second:
                time.sleep(0.02)
        results.put((name, True))
    except Exception as exc:
        results.put((name, False, repr(exc)))


def demonstrate_deadlock_and_ordered_fix(ctx: Any) -> None:
    lock_a = ctx.Lock()
    lock_b = ctx.Lock()
    a_locked = ctx.Event()
    b_locked = ctx.Event()
    go = ctx.Event()
    first = ctx.Process(target=abba_worker, args=(lock_a, lock_b, a_locked, go))
    second = ctx.Process(target=abba_worker, args=(lock_b, lock_a, b_locked, go))
    first.start()
    second.start()
    check(a_locked.wait(2.0) and b_locked.wait(2.0),
          "could not establish the controlled ABBA setup")
    go.set()
    time.sleep(0.3)
    detected = first.is_alive() and second.is_alive()
    for process in (first, second):
        if process.is_alive():
            process.terminate()
        process.join(1.0)
    check(detected, "controlled ABBA case unexpectedly made progress")
    print("OBSERVE T-DEADLOCK-01 controlled ABBA deadlock detected; children stopped")

    safe_a = ctx.Lock()
    safe_b = ctx.Lock()
    results = ctx.Queue()
    workers = [
        ctx.Process(target=ordered_worker,
                    args=(safe_a, safe_b, results, f"ordered-{index}"))
        for index in range(2)
    ]
    for process in workers:
        process.start()
    join_or_terminate(workers, 4.0, "T-DEADLOCK-02")
    collect_results(results, 2, "T-DEADLOCK-02")
    print("PASS T-DEADLOCK-02 both workers use A->B order and finish normally")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/vled")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--mode", choices=("driver", "deadlock", "all"), default="all")
    args = parser.parse_args()
    if not 1 <= args.iterations <= 10000:
        parser.error("--iterations must be in 1..10000")
    if "fork" not in mp.get_all_start_methods():
        parser.error("this Linux driver probe requires multiprocessing start method 'fork'")
    ctx = mp.get_context("fork")

    try:
        if args.mode in {"driver", "all"}:
            check(os.path.exists(args.device), f"device does not exist: {args.device}")
            print(f"VLED multiprocess probe: device={args.device}")
            test_cross_process_visibility(ctx, args.device)
            test_process_offsets_and_snapshot(ctx, args.device)
            test_multiprocess_stress(ctx, args.device, args.iterations)
            test_shared_fd_status_wakeup(ctx, args.device)
        if args.mode in {"deadlock", "all"}:
            print("VLED controlled deadlock demonstration (user space only)")
            demonstrate_deadlock_and_ordered_fix(ctx)
    except Exception as exc:
        print(f"FAIL VLED multiprocess/deadlock probe: {exc}", file=sys.stderr)
        return 1

    print("VLED multiprocess/deadlock probe: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
