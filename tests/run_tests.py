"""Point d'entrée de la suite de tests (pytest)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import pytest
except ImportError:
    sys.exit("pytest est requis : pip install -r requirements-dev.txt")

if __name__ == "__main__":
    raise SystemExit(pytest.main([str(ROOT / "tests"), "-v"]))
