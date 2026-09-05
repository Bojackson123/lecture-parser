"""Run the GUI server: loopback only, until Ctrl+C.

Split from ``app.py`` so tests drive ``create_app`` in-process and only the one
loopback smoke test ever binds a socket.
"""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

import uvicorn

from lecturenotes.web.app import create_app


def serve(*, port: int, workspace: Path, open_browser: bool) -> None:
    """Serve the GUI on ``127.0.0.1:port`` (hardcoded loopback — a scope decision:
    this is a single-user tool holding API credentials in its environment)."""
    app = create_app(workspace)
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        # After a beat, so the socket is listening by the time the browser asks.
        threading.Timer(0.8, webbrowser.open, [url]).start()
    print(f"lecturenotes serve: {url} (workspace: {workspace}); Ctrl+C to stop")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
