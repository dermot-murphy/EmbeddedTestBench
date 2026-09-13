"""Allow ``python -m benchtools`` to run the command line.

Traces to: RUN-FR-050, SCOPE-FR-100.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
