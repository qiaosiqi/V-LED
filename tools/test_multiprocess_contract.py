#!/usr/bin/env python3
"""Static preflight for the VLED multi-process and lock-order contract."""

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


def main() -> int:
    driver = (ROOT / "driver" / "vled.c").read_text(encoding="utf-8")
    cli = (ROOT / "tools" / "vled_cli.c").read_text(encoding="utf-8")
    probe = (ROOT / "tools" / "vled_multiprocess_probe.py").read_text(
        encoding="utf-8"
    )
    verify = (ROOT / "tools" / "vled_verify.sh").read_text(encoding="utf-8")

    require(driver, r"vled_file_context\.lock\s*->\s*vled_device\.lock",
            "driver does not document its only nested-lock order")
    require(driver, r"lockdep_assert_held\(&ctx->lock\)",
            "device-lock helper does not enforce context-first ordering")
    require(driver, r"ctx->write_offset\s*=\s*old_offset\s*\+\s*count",
            "successful writes do not advance a per-open write offset")
    require(driver, r"should_wake_waiters\s*=\s*true\s*;",
            "successful no-op writes do not wake a shared-FD reader")
    reject(driver, r"should_wake_waiters\s*=\s*changed\s*;",
           "shared-FD wakeup is still incorrectly gated by version changes")
    require(
        driver,
        r"trace_command,\s*count,\s*ret,\s*old_offset\);",
        "failed-write trace does not print result and offset in the right order",
    )
    require(
        cli,
        r"write_errno\s*==\s*EMSGSIZE\s*\|\|\s*write_errno\s*==\s*ENOSPC",
        "CLI does not distinguish both write-buffer overflow errors",
    )
    require(
        cli,
        re.escape("out of buffer, please try again"),
        "CLI does not provide the required buffer overflow message",
    )
    for test_id in ("T-MP-01", "T-MP-02", "T-MP-03", "T-MP-04"):
        require(probe, re.escape(test_id), f"missing {test_id}")
    require(probe, r"get_context\(\"fork\"\)",
            "probe does not force real Linux fork semantics")
    require(probe, r"possible deadlock or lost wakeup",
            "probe has no timeout diagnosis for stuck processes")
    require(verify, r"vled_multiprocess_probe\.py",
            "unified verification does not run the multiprocess probe")

    print("PASS multiprocess static contract: per-open offsets, lock order and fork tests")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL multiprocess static contract: {exc}", file=sys.stderr)
        raise SystemExit(1)
