"""Opt-in fleet logging bootstrap factory for standalone daemon applications."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_platform_log_dir(app_name: str) -> Path:
    """Returns canonical OS log directory according to Homelab Systems Lifecycle standards."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_app_data) / app_name / "logs"
    return Path.home() / ".local" / "state" / app_name / "logs"


def configure_fleet_logging(
    app_name: str,
    log_dir: Path | None = None,
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> Path:
    """Configures standardized rotating file logging for fleet daemon applications."""
    target_dir = log_dir or get_platform_log_dir(app_name)
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / f"{app_name}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s (%(process)d): %(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    return log_file
