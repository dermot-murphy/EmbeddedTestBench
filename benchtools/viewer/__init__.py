"""The test run viewer: watch and control bench test runs in a browser (#130, #137).

``benchtools view`` serves a page on 127.0.0.1 that follows a run's event log
and drives the runner's control channel. Standard library only; the page is
plain HTML, JavaScript and CSS shipped beside the code.

The viewer sits above the runner: it may import from every other layer, and
nothing imports from it.

Traces to: VIEW-ARC-001.
"""

from .server import Catalogue, Hub, Launcher, ViewerServer, main
from .state import RunState, describe_step

__all__ = ["Catalogue", "Hub", "Launcher", "RunState", "ViewerServer", "describe_step", "main"]
