#!/usr/bin/env python
"""Run the EquityMind API server."""

import sys
from pathlib import Path

# Add src to path so we can import equitymind
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

if __name__ == "__main__":
    import uvicorn
    from equitymind.api import create_app

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
