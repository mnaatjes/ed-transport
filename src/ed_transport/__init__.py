"""Package root for ed-transport."""

import logging

__version__ = "0.1.0"

# PEP 2818: Absorb all library logging silently if host application has no handlers configured.
logging.getLogger("ed_transport").addHandler(logging.NullHandler())
