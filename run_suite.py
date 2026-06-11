#!/usr/bin/env python3
"""Run a set of pytest cases defined in a JSON config file with unified params."""

import json
import re
import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_suite.py <config.json> [extra pytest args...]")
        print()
        print("Example:")
        print("  python run_suite.py testcases/ubsmem/ubsmem_suite.json -n auto")
        print("  python run_suite.py testcases/ubsmem/ubsmem_suite.json -k borrow -s")
        sys.exit(1)

    config_path = Path(sys.argv[1])

    with open(config_path) as f:
        config = json.load(f)

    tests = config["tests"]
    params = config.get("params", {})
    hook_path = config.get("hook")

    args = ["pytest"] + tests
    if hook_path:
        args += ["--test-hook", hook_path]
    if params:
        args += ["--test-params", json.dumps(params)]
    args += sys.argv[2:]

    hook_info = f", hook: {hook_path}" if hook_path else ""
    print(f"[run_suite] {len(tests)} test(s), params: {params}{hook_info}")
    print(f"[run_suite] {' '.join(args)}")
    print()

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, encoding="utf-8", errors="replace")
    captured = ""
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        captured += line
    proc.wait()

    passed = failed = 0
    m = re.search(r"(\d+)\s+passed", captured)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", captured)
    if m:
        failed = int(m.group(1))

    print()
    print("=" * 60)
    print(f"  [run_suite]  Passed: {passed}  |  Failed: {failed}  |  Total: {passed + failed}")
    print("=" * 60)

    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
