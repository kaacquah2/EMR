#!/usr/bin/env python
"""Monorepo root shim: forwards to medsync-backend/manage.py for Django/Railpack detection."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "medsync-backend")


def main() -> None:
    os.chdir(BACKEND)
    rc = subprocess.call([sys.executable, "manage.py", *sys.argv[1:]])
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
