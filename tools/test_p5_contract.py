#!/usr/bin/env python3
"""Static P5 preflight: prove the poll tests reject the P4 implementation."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(text: str, pattern: str, message: str) -> None:
    if re.search(pattern, text, re.MULTILINE) is None:
        raise AssertionError(message)


def reject(text: str, pattern: str, message: str) -> None:
    if re.search(pattern, text, re.MULTILINE) is not None:
        raise AssertionError(message)


def require_count(text: str, pattern: str, expected: int, message: str) -> None:
    if len(re.findall(pattern, text, re.MULTILINE)) != expected:
        raise AssertionError(message)


def main() -> int:
    driver = (ROOT / "driver" / "vled.c").read_text(encoding="utf-8")
    bridge = (ROOT / "tools" / "vled_bridge.c").read_text(encoding="utf-8")
    probe = (ROOT / "tools" / "vled_poll_probe.c").read_text(encoding="utf-8")
    bridge_probe = (ROOT / "tools" / "vled_bridge_probe.py").read_text(
        encoding="utf-8")
    fd_probe = (ROOT / "tools" / "vled_fd_probe.c").read_text(encoding="utf-8")

    for test_id in range(1, 8):
        require(probe, rf"T-POLL-0{test_id}", f"missing T-POLL-0{test_id}")
    require(bridge_probe, r"T-POLL-08", "missing T-POLL-08 bridge metrics")

    require(driver, r"wait_queue_head_t", "driver has no wait queue")
    require(driver, r"\.poll\s*=", "driver has no .poll callback")
    require(driver, r"poll_wait\s*\(", "driver does not register poll waiters")
    require(driver, r"wait_event_interruptible\s*\(",
            "blocking read does not wait interruptibly")
    require(driver, r"wake_up_interruptible\s*\(",
            "state changes do not wake waiters")
    require(driver, r"O_NONBLOCK", "nonblocking read has no EAGAIN path")

    require(bridge, r"#include\s+<poll\.h>", "bridge does not include poll API")
    require(bridge, r"\bpoll\s*\(", "bridge is not event driven")
    reject(bridge, r"\bread_vled_once\s*\(",
           "bridge still reopens the device for every sample")
    reject(bridge, r"\busleep\s*\(", "bridge still performs periodic polling")
    require_count(
        fd_probe,
        r'open_checked\("T-ROLLBACK", dev, O_RDWR \| O_NONBLOCK\)',
        2,
        "T-ROLLBACK must use nonblocking reads at both P5 EOF checks",
    )

    print("PASS P5 static contract: wait queue, poll, blocking read and bridge")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL P5 static contract: {exc}", file=sys.stderr)
        raise SystemExit(1)
