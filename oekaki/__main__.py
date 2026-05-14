"""Entry point: ``python -m oekaki``."""

from __future__ import annotations

import sys

from oekaki.cli import main


if __name__ == "__main__":
    sys.exit(main())
