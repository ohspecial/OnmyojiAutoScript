# This Python file uses the following encoding: utf-8

import os
from module.hyakkiyakou.bootstrap import install_custom_stack

# Phase 1: labels shim only — tracker remains the legacy pyd
if os.environ.get("HYA_USE_OWN_STACK", "1") != "0":
    install_custom_stack(use_custom_tracker=False, use_custom_labels=True)

# Lazy import: Debugger depends on oashya.utils which may not be available
# in test environments. Import is deferred to actual usage.
try:
    from module.hyakkiyakou.debugger import Debugger
except ImportError:
    Debugger = None  # type: ignore[assignment, misc]

__all__ = [
    "Debugger",
]
