"""Backward-compatibility re-export of class_info from hya.labels.class_info.

The canonical location is ``hya.labels.class_info``. This module re-exports
all public names so that existing imports from ``module.hyakkiyakou.class_info``
continue to work.
"""

from hya.labels.class_info import ClassInfo, CANONICAL_TAGS, Tier  # noqa: F401

__all__ = ["ClassInfo", "CANONICAL_TAGS", "Tier"]
