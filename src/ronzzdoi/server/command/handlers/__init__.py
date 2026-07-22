"""Command handlers — import domain modules to register commands.

Side-effect imports register handlers with the command registry
via the ``@command()`` decorator.  Each module is auto-discovered
by the ``command/__init__.py`` import chain.
"""

from __future__ import annotations

# Side-effect imports: each module registers its handlers as a
# side effect of module-level ``@command()`` decorator evaluation.
from ronzzdoi.server.command.handlers import auth  # noqa: F401
from ronzzdoi.server.command.handlers import citation  # noqa: F401
from ronzzdoi.server.command.handlers import doi  # noqa: F401
