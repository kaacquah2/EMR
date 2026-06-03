"""Model subpackage shim that re-exports the legacy flat module."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_legacy_path = Path(__file__).resolve().parent.parent / "models.py"
_spec = spec_from_file_location("api.models_legacy", _legacy_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load legacy model module at {_legacy_path}")

_legacy_module = module_from_spec(_spec)
sys.modules.setdefault("api.models_legacy", _legacy_module)
_spec.loader.exec_module(_legacy_module)

for _name in dir(_legacy_module):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_legacy_module, _name)

__all__ = [name for name in dir(_legacy_module) if not name.startswith("_")]
