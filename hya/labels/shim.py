"""Backward-compatibility shim re-exporting the legacy ``oashya.labels`` surface.

This module is loaded by ``module.hyakkiyakou.bootstrap`` and injected into
``sys.modules['oashya.labels']`` so that existing callers (``script_task.py``,
third-party code) continue to work without source changes.

The rewritten Agent, Focus, and Debugger MUST NOT import from this module.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from hya.labels.registry import Registry

# ---------------------------------------------------------------------------
# Load the Registry at module import time
# ---------------------------------------------------------------------------

_LABELS_YAML = Path(__file__).resolve().parent / "labels.yaml"
_registry = Registry.from_yaml(_LABELS_YAML)
_registry.validate()

# ---------------------------------------------------------------------------
# Tier dicts: dict[str, str] mapping {label: name} filtered by tier
# ---------------------------------------------------------------------------

ur: dict[str, str] = {
    e.label: e.name for e in _registry.entries if e.tier == "ur"
}
sp: dict[str, str] = {
    e.label: e.name for e in _registry.entries if e.tier == "sp"
}
ssr: dict[str, str] = {
    e.label: e.name for e in _registry.entries if e.tier == "ssr"
}
sr: dict[str, str] = {
    e.label: e.name for e in _registry.entries if e.tier == "sr"
}
r: dict[str, str] = {
    e.label: e.name for e in _registry.entries if e.tier == "r"
}
n: dict[str, str] = {
    e.label: e.name for e in _registry.entries if e.tier == "n"
}
g: dict[str, str] = {
    e.label: e.name for e in _registry.entries if e.tier == "g"
}
buff: dict[str, str] = {
    e.label: e.name for e in _registry.entries if e.tier == "buff"
}

# ---------------------------------------------------------------------------
# CLASSIFY: list[dict] in id order — each dict has keys "name", "class", "id"
# ---------------------------------------------------------------------------


def _gen_classify() -> list[dict]:
    """Generate CLASSIFY in id order matching legacy format."""
    return [
        {"name": e.name, "class": e.label, "id": e.id}
        for e in _registry.entries
    ]


CLASSIFY: list[dict] = _gen_classify()

# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------


def id2label(idd: int) -> str:
    """Return the label string for a given dense id."""
    return _registry.classes[idd].label


def id2name(idd: int) -> str:
    """Return the human-readable name for a given dense id."""
    return _registry.classes[idd].name


def label2id(label: str) -> int:
    """Return the dense id for a given label string."""
    return _registry.by_label[label].id


# ---------------------------------------------------------------------------
# CLASSINDEX — deprecated, emits DeprecationWarning on MIN_X/MAX_X access
# ---------------------------------------------------------------------------

# Tag-to-BUFF constant mapping
_BUFF_TAG_MAP: dict[str, str] = {
    "buff_lantern": "BUFF_001",
    "buff_slow": "BUFF_002",
    "buff_throw_speed": "BUFF_003",
    "buff_bean_gain": "BUFF_004",
    "buff_freeze": "BUFF_005",
    "buff_prob_up": "BUFF_006",
    "buff_friend_up": "BUFF_007",
}

# Reverse: constant name -> tag
_BUFF_CONST_TO_TAG: dict[str, str] = {v: k for k, v in _BUFF_TAG_MAP.items()}


class _ClassIndexMeta(type):
    """Metaclass for CLASSINDEX that intercepts attribute access.

    Emits DeprecationWarning on first access per MIN_X/MAX_X attribute per
    process, and resolves BUFF_001..BUFF_007 and R_007/R_008 via the Registry.
    """

    _warned: set[str] = set()

    def __getattr__(cls, name: str) -> Any:
        # Handle MIN_<TIER> / MAX_<TIER>
        if name.startswith("MIN_") or name.startswith("MAX_"):
            tier_upper = name[4:]  # e.g. "SP", "SSR", "BUFF", etc.
            tier = tier_upper.lower()
            # Validate it's a known tier
            valid_tiers = {"buff", "n", "g", "r", "sr", "ssr", "sp", "ur"}
            if tier not in valid_tiers:
                raise AttributeError(
                    f"'CLASSINDEX' has no attribute '{name}'"
                )

            # Emit deprecation warning on first access per attribute
            if name not in cls._warned:
                cls._warned.add(name)
                warnings.warn(
                    f"CLASSINDEX.{name} is deprecated; "
                    f"use registry.classes[id].tier == '{tier}'",
                    DeprecationWarning,
                    stacklevel=2,
                )

            # Compute min/max id for the tier
            ids = [e.id for e in _registry.entries if e.tier == tier]
            if not ids:
                raise AttributeError(
                    f"'CLASSINDEX' has no attribute '{name}' "
                    f"(no entries with tier '{tier}')"
                )
            if name.startswith("MIN_"):
                return min(ids)
            else:
                return max(ids)

        # Handle BUFF_001..BUFF_007
        if name in _BUFF_CONST_TO_TAG:
            tag = _BUFF_CONST_TO_TAG[name]
            return _registry.by_tag[tag][0].id

        # Handle R_007, R_008
        if name == "R_007":
            return _registry.by_label["r_007"].id
        if name == "R_008":
            return _registry.by_label["r_008"].id

        raise AttributeError(f"'CLASSINDEX' has no attribute '{name}'")


class CLASSINDEX(metaclass=_ClassIndexMeta):
    """Deprecated class-index constants.

    Access to ``MIN_<TIER>`` / ``MAX_<TIER>`` emits a ``DeprecationWarning``
    on first access per attribute per process. These values are no longer
    guaranteed to form contiguous ranges after migration.

    ``BUFF_001..BUFF_007`` and ``R_007``/``R_008`` are resolved via the
    Registry's tag and label lookups.
    """

    pass
