"""Unit tests for opt-in fleet logging bootstrap factory."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from ed_transport.bootstrap.logging import (
    configure_fleet_logging,
    get_platform_log_dir,
)


def test_get_platform_log_dir_linux(monkeypatch) -> None:
    """Verifies standard Linux platform log directory resolution."""
    monkeypatch.setattr(sys, "platform", "linux")
    path = get_platform_log_dir("ed-capi")
    assert path == Path.home() / ".local" / "state" / "ed-capi" / "logs"


def test_get_platform_log_dir_windows(monkeypatch, tmp_path: Path) -> None:
    """Verifies Windows NT local app data directory resolution."""
    monkeypatch.setattr(sys, "platform", "win32")
    fake_local_appdata = str(tmp_path / "AppData" / "Local")
    monkeypatch.setenv("LOCALAPPDATA", fake_local_appdata)
    path = get_platform_log_dir("ed-eddn")
    assert path == Path(fake_local_appdata) / "ed-eddn" / "logs"


def test_configure_fleet_logging_creates_file_and_captures_logs(tmp_path: Path) -> None:
    """Asserts that configure_fleet_logging attaches a rotating handler and captures records."""
    log_file = configure_fleet_logging(
        app_name="test-app",
        log_dir=tmp_path,
        level=logging.DEBUG,
        max_bytes=1024,
        backup_count=2,
    )
    assert log_file.is_file()

    logger = logging.getLogger("test_component")
    logger.debug("Debug event message")
    logger.info("Info event message")

    content = log_file.read_text(encoding="utf-8")
    assert "Debug event message" in content
    assert "Info event message" in content
    assert "[DEBUG]" in content
    assert "[INFO]" in content

    # Clean up handlers attached to root logger
    root = logging.getLogger()
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
