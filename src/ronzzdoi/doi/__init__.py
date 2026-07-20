"""DOI core module — assign, resolve, redirect, and manage ronzzDOIs.

Handles the core DOI lifecycle:
- Generation and assignment of persistent identifiers
- URL resolution and HTTP redirect
- Soft redirect on metadata/URL changes
- Deletion and tombstoning
"""

from __future__ import annotations
