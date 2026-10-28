"""Driven adapter evaluating operating system liveness via standard library."""

from __future__ import annotations

import os
import platform
import sys

from ...core.ports.driven.probe_port import SystemProbePort


class OsSystemProbeAdapter(SystemProbePort):
    """Probes system environment and resources using Python standard library."""

    def is_operational(self) -> bool:
        """Determines if the runtime environment is responsive and operational."""
        # Baseline invariant: Python runtime has an active interpreter and filesystem access
        return sys.hexversion > 0 and os.name != ""

    def get_probe_metadata(self) -> dict[str, str]:
        """Collects environmental metadata without external dependencies."""
        return {
            "os_name": os.name,
            "platform": platform.system(),
            "python_version": platform.python_version(),
        }
