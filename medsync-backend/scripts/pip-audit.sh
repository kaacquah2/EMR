#!/usr/bin/env bash
# Run pip-audit to check dependencies for known vulnerabilities.
# Usage: from repo root, ./scripts/pip-audit.sh  or  bash scripts/pip-audit.sh
set -e
pip install -q pip-audit
pip-audit
