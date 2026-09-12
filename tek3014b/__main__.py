"""Allow ``python -m tek3014b`` to run the command-line interface.

Traces to: SWE1-FR-100, SWE3-DD-CLI.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
