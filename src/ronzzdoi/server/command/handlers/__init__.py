"""Command handlers — register all domain command modules.

Side-effect imports register handlers with the command registry.
"""

from __future__ import annotations

# Import all handler modules to trigger registration
from ronzzdoi.server.command.handlers import auth  # noqa: F401
