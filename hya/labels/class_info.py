"""Semantic data model for Hyakkiyakou shikigami classes.

Defines the immutable ``ClassInfo`` dataclass and the closed canonical tag
vocabulary used by the Registry, Agent, Focus, and Debugger layers.

This is the canonical location. ``module.hyakkiyakou.class_info`` re-exports
from here for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Canonical tier values — derived deterministically from the label prefix.
Tier = Literal["buff", "n", "g", "r", "sr", "ssr", "sp", "ur"]

# Canonical tag vocabulary — closed set, validated at registry load.
# Adding a new tag requires a deliberate reviewed code change here.
CANONICAL_TAGS: frozenset[str] = frozenset({
    "forbidden",          # Agent must never target (legacy R_007, R_008 childboy/childgirl)
    "buff_lantern",       # legacy BUFF_001
    "buff_slow",          # legacy BUFF_002
    "buff_throw_speed",   # legacy BUFF_003
    "buff_bean_gain",     # legacy BUFF_004
    "buff_freeze",        # legacy BUFF_005
    "buff_prob_up",       # legacy BUFF_006
    "buff_friend_up",     # legacy BUFF_007
})


@dataclass(frozen=True)
class ClassInfo:
    """Immutable record describing one detection class.

    Attributes:
        id: Dense integer index (``entries[i].id == i``).
        label: Machine-readable identifier, e.g. ``"ssr_012"``.
        name: Human-readable display name (may be localised).
        tier: One of the canonical tier values.
        tags: Subset of ``CANONICAL_TAGS`` attached to this class.
        since_version: The labels.yaml version that introduced this entry.
    """

    id: int
    label: str
    name: str
    tier: Tier
    tags: frozenset[str] = frozenset()
    since_version: str = "v0.0"

    def has_tag(self, tag: str) -> bool:
        """Return whether *tag* is present on this class."""
        return tag in self.tags
