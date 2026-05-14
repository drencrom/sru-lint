"""Run all local quality checks (ruff, mypy, unit tests, functional tests).

Invoked via the `check-all` Poetry script. Runs every step even if an earlier
one fails, then exits non-zero if any step failed.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass
class Step:
    name: str
    cmd: list[str]


@dataclass
class Result:
    step: Step
    returncode: int
    duration: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


STEPS: list[Step] = [
    Step("ruff (lint)", ["ruff", "check", "."]),
    Step("ruff (format)", ["ruff", "format", "--check", "."]),
    Step("mypy", ["mypy", "sru_lint/"]),
    Step("unittest", ["python", "-m", "unittest", "discover", "-s", "tests"]),
]


def _run(step: Step) -> Result:
    print(f"\n\033[1;36m==> {step.name}\033[0m  ({' '.join(step.cmd)})", flush=True)
    start = time.monotonic()
    proc = subprocess.run(step.cmd)
    return Result(step=step, returncode=proc.returncode, duration=time.monotonic() - start)


def main() -> int:
    results = [_run(s) for s in STEPS]

    print("\n\033[1;36m==> summary\033[0m")
    width = max(len(r.step.name) for r in results)
    for r in results:
        marker = "\033[1;32mPASS\033[0m" if r.ok else "\033[1;31mFAIL\033[0m"
        print(f"  {marker}  {r.step.name:<{width}}  {r.duration:6.2f}s")

    failed = [r for r in results if not r.ok]
    if failed:
        names = ", ".join(r.step.name for r in failed)
        print(f"\n\033[1;31m{len(failed)} step(s) failed:\033[0m {names}")
        return 1
    print("\n\033[1;32mAll checks passed.\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
