"""Bootstrap module: inject hya.labels.shim into sys.modules as oashya.labels.

This module performs a one-time ``sys.modules`` replacement so that all existing
code importing from ``oashya.labels`` transparently receives the new
Registry-backed shim implementation.

Usage — call once at application startup, before any ``oashya.labels`` import::

    from module.hyakkiyakou.bootstrap import install_custom_stack
    install_custom_stack()

After ``install_custom_stack()`` returns (Phase 1 defaults):
- ``import oashya.labels`` → resolves to ``hya.labels.shim``
- ``from oashya.labels import CLASSINDEX, id2label, ...`` → works as before
- ``oashya.tracker`` is NOT touched — the legacy pyd remains the resolver.

Design notes:
- Idempotent: calling ``install_custom_stack()`` multiple times is safe.
- Thread-safe: uses a module-level flag; the GIL protects the check-and-set.
- Respects ``HYA_USE_OWN_STACK`` env var: set to ``"0"`` to disable all patching.
"""

from __future__ import annotations

import logging
import os
import sys
import types
from pathlib import Path

_logger = logging.getLogger(__name__)

_installed: bool = False


def install_custom_stack(
    use_custom_tracker: bool = False,
    use_custom_labels: bool = True,
) -> None:
    """Replace ``sys.modules`` entries for the oashya labels (and optionally tracker).

    Phase 1 default: ``use_custom_tracker=False, use_custom_labels=True``.
    Phase 2 flips ``use_custom_tracker=True``.

    Respects ``HYA_USE_OWN_STACK`` env var — when set to ``"0"``, this function
    is a no-op and the Legacy_Stack remains active (useful for A/B parity runs).

    Idempotent — subsequent calls are no-ops.
    """
    global _installed
    if _installed:
        return

    # Respect HYA_USE_OWN_STACK env var
    if os.environ.get("HYA_USE_OWN_STACK", "1") == "0":
        _logger.info("bootstrap: HYA_USE_OWN_STACK=0, legacy stack remains active")
        _installed = True
        return

    if use_custom_labels:
        # Import the shim module (triggers Registry load + validate).
        from hya.labels import shim as _shim_module

        # Ensure the 'oashya' parent namespace package exists in sys.modules.
        if "oashya" not in sys.modules:
            oashya_ns = types.ModuleType("oashya")
            oashya_ns.__path__ = []  # namespace package convention
            oashya_ns.__package__ = "oashya"
            sys.modules["oashya"] = oashya_ns

        # Inject the shim as oashya.labels
        sys.modules["oashya.labels"] = _shim_module
        sys.modules["oashya"].labels = _shim_module  # type: ignore[attr-defined]

    if use_custom_tracker:
        # Phase 2: patch oashya.tracker with custom tracker
        from module.hyakkiyakou import custom_tracker as _tracker_module
        sys.modules["oashya.tracker"] = _tracker_module
        if "oashya" in sys.modules:
            sys.modules["oashya"].tracker = _tracker_module  # type: ignore[attr-defined]

    # Log active mode
    if use_custom_tracker and use_custom_labels:
        _logger.info("bootstrap: phase2-full-custom (labels shim + custom tracker)")
    elif use_custom_labels:
        _logger.info("bootstrap: phase1-labels-shim-only")
    else:
        _logger.info("bootstrap: legacy")

    _installed = True


# Legacy aliases for backward compatibility with tests
def install() -> None:
    """Alias for ``install_custom_stack()`` with Phase 1 defaults."""
    install_custom_stack(use_custom_tracker=False, use_custom_labels=True)


def is_installed() -> bool:
    """Return whether the bootstrap has been applied."""
    return _installed


def uninstall() -> None:
    """Remove the shim from sys.modules (primarily for testing).

    After calling this, importing ``oashya.labels`` will resolve to the
    original package (if installed) or raise ImportError.
    """
    global _installed
    if not _installed:
        return

    sys.modules.pop("oashya.labels", None)
    sys.modules.pop("oashya.tracker", None)
    _installed = False
