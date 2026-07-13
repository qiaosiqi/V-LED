#!/usr/bin/env python3
"""Static guardrails for the VLED multiprocess and lock-order contract."""

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
    probe = (ROOT / "tools" / "vled_multiprocess_probe.py").read_text(
        encoding="utf-8"
    )
    verify = (ROOT / "tools" / "vled_verify.sh").read_text(encoding="utf-8")

    require(
        driver,
        r"vled_file_context\.lock\s*->\s*vled_device\.lock",
        "driver does not document its single nested-lock order",
    )
    require(
        driver,
        r"should_wake_waiters\s*=\s*true\s*;",
        "successful STATUS/no-op writes do not wake a shared-FD reader",
    )
    reject(
        driver,
        r"should_wake_waiters\s*=\s*changed\s*;",
        "shared-FD wakeup is still incorrectly gated by version changes",
    )
    for test_id in ("T-MP-01", "T-MP-02", "T-MP-03", "T-MP-04",
                    "T-DEADLOCK-01", "T-DEADLOCK-02"):
        require(probe, re.escape(test_id), f"missing {test_id}")
    require(
        probe,
        r"get_context\(\"fork\"\)",
        "multiprocess probe does not force real Linux fork semantics",
    )
    require(
        verify,
        r"vled_multiprocess_probe\.py[\s\S]*?--mode all",
        "unified verification does not run the multiprocess/deadlock probe",
    )

    print("PASS multiprocess static contract: lock order, shared-FD wake and tests")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL multiprocess static contract: {exc}", file=sys.stderr)
        raise SystemExit(1)
