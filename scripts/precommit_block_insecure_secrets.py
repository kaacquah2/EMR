#!/usr/bin/env python3
"""Pre-commit hook: reject known insecure secret literals in staged files."""

from __future__ import annotations

import sys

BLOCKED = (
    "django-insecure-dev-key",
    "django-insecure-ci-test-key",
    "FIELD_ENCRYPTION_KEY=ci-test-encryption-key-32-chars-long-at-least",
)

SKIP_SUFFIXES = (".md",)


def main() -> int:
    failed = []
    for path in sys.argv[1:]:
        if path.endswith(SKIP_SUFFIXES) and "Master_Prompt" in path:
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for pattern in BLOCKED:
            if pattern in text:
                failed.append((path, pattern))
    if failed:
        for path, pattern in failed:
            print(f"BLOCKED: {path} contains insecure pattern: {pattern}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
