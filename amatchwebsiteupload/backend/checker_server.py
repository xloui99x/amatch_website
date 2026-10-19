#!/usr/bin/env python3
"""Entry point for the A Match job-ad check backend.

Production (Render):   gunicorn checker_server:app
Local development:     python3 checker_server.py   → http://localhost:8913

The application itself lives in the ``amatch_checker`` package.
"""

import logging
import os

from amatch_checker import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = create_app()

if __name__ == "__main__":
    # 0.0.0.0 so the process is reachable inside containers (Render, Docker).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8913")), debug=False)  # noqa: S104
