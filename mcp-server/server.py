"""Prefect Horizon entrypoint that preserves package-relative imports."""

import os
from pathlib import Path
import sys
import tempfile

# Horizon loads this entrypoint as a standalone file, so expose its package root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Build-time inspection does not inject deployment secrets and may use a read-only cwd.
if "DATABASE_URL" not in os.environ and "DATABASE_PATH" not in os.environ:
    os.environ["DATABASE_PATH"] = str(Path(tempfile.gettempdir()) / "moodwave.db")

from moodwave_mcp.server import mcp

__all__ = ["mcp"]
