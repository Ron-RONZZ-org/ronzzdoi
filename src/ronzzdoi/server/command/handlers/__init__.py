"""Command handlers — import domain modules to register commands.

Side-effect imports register handlers with the command registry.
v0.1.0: no server-side command handlers yet (all !xxx commands are
either frontend-local or map directly to REST endpoints).
"""
