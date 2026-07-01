#!/usr/bin/env python3
"""Convenience launcher so the CLI runs without installing the package.

Adds ``src/`` to the path, then delegates to :func:`equitymind.cli.main`.

    python scripts/run_analysis.py run AAPL MSFT --no-ai
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from equitymind.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
