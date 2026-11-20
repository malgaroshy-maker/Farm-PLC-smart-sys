"""Reset demo history — preserves programs and configuration, clears operating history."""

import os
import sys

# Ensure apps/api is in sys.path so app modules load properly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_DIR = os.path.join(ROOT, "apps", "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.reset_demo import main, reset_history  # noqa: E402

__all__ = ["main", "reset_history"]

if __name__ == "__main__":
    main()
