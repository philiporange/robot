#!/usr/bin/env python3
"""Start the Robot web server."""

import uvicorn

from robot.server import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9999)
