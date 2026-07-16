"""ai-sim-company backend package.

Shared by Company Hub (the core) and Agent Runtime (inside the container).
See README / architecture design doc §十三 for subpackage layout.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Auto-load the .env at the repo root on startup (effective when running `uvicorn` locally).
# docker compose reads .env natively; this fills in the non-container scenario.
# Existing env vars take precedence (override=False), so shell/env can still override .env.
try:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # silently skip if python-dotenv is not installed, keep the package importable
