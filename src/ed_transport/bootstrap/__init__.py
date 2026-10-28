"""Composition root and dependency injection wiring."""

from .container import Container
from .logging import configure_fleet_logging, get_platform_log_dir

__all__ = ["Container", "configure_fleet_logging", "get_platform_log_dir"]
