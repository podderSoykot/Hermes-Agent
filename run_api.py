"""Run the Hermes REST API server."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("hermes.api.main:app", host="0.0.0.0", port=8000, reload=True)
