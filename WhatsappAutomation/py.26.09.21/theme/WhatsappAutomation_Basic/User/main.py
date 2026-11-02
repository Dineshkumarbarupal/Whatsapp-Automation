from __future__ import annotations

import logging
import sys
from pathlib import Path

import eel

from core.config import APP_DIR, AppConfig, ensure_directories
from core.logging_config import configure_logging
from py.api import ApplicationServices


def run() -> int:
    ensure_directories()
    logger = configure_logging(logging.DEBUG if AppConfig.debug else logging.INFO)
    try:
        services = ApplicationServices(logger)
        services.register(eel)
        eel.init(str(APP_DIR), allowed_extensions=[".js", ".html", ".css", ".json", ".svg"])
        logger.info("Starting %s v%s", AppConfig.app_name, AppConfig.version)
        eel.start("web/index.html", size=(1440, 920), position=(80, 50),
                  port=0, mode="chrome", shutdown_delay=2.0, close_callback=lambda route, websockets: None)
        return 0
    except EnvironmentError as exc:
        logger.exception("Desktop browser runtime could not start: %s", exc)
        print("Unable to start the desktop window. Install Google Chrome or Chromium and retry.", file=sys.stderr)
        return 1
    except Exception:
        logger.exception("Application startup failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
