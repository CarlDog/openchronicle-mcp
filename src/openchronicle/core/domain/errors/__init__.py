"""Error domain utilities and constants.

Deliberately does NOT re-export the codes from ``error_codes``. It used
to mirror all twelve plus their ``__all__``, and nothing ever consumed
them — every import in ``src/`` and ``tests/`` reaches the submodule
directly (``from ...domain.errors import error_codes``). A second copy of
the list is one more place to forget when a code is added.
"""

from __future__ import annotations
