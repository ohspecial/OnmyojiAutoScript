"""Registry — single source of truth for class metadata at runtime.

Loads from ``hya/labels/labels.yaml`` (version 2), validates structural
invariants, and provides O(1) lookups by id, label, and tag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import yaml

from hya.labels.class_info import CANONICAL_TAGS, ClassInfo, Tier
from hya.labels.legacy_snapshot import LEGACY_SNAPSHOT

# Regex that every label must satisfy.
_LABEL_RE = re.compile(r"^(buff|n|g|r|sr|ssr|sp|ur)_\d{3,4}$")


@dataclass
class RegistryDiff:
    """Result of comparing two Registry snapshots.

    Attributes:
        added: Entries present in *self* but not in *prev*.
        removed: Entries present in *prev* but not in *self*.
        label_changed: Entries whose label differs between snapshots.
        tier_changed: Entries whose tier differs between snapshots.
        tags_changed: Entries whose tags differ between snapshots.
        name_changed: Entries whose name differs between snapshots.
    """

    added: list[ClassInfo] = field(default_factory=list)
    removed: list[ClassInfo] = field(default_factory=list)
    label_changed: list[tuple[ClassInfo, ClassInfo]] = field(default_factory=list)
    tier_changed: list[tuple[ClassInfo, ClassInfo]] = field(default_factory=list)
    tags_changed: list[tuple[ClassInfo, ClassInfo]] = field(default_factory=list)
    name_changed: list[tuple[ClassInfo, ClassInfo]] = field(default_factory=list)


class Registry:
    """Immutable registry of detection classes loaded from ``labels.yaml``.

    Use :meth:`from_yaml` to construct, then call :meth:`validate` to enforce
    all structural invariants before using the registry at runtime.
    """

    __slots__ = ("entries", "classes", "by_label", "by_tag")

    entries: list[ClassInfo]
    classes: dict[int, ClassInfo]
    by_label: dict[str, ClassInfo]
    by_tag: dict[str, list[ClassInfo]]

    def __init__(self, entries: list[ClassInfo]) -> None:
        self.entries = entries
        self.classes = {e.id: e for e in entries}
        self.by_label = {e.label: e for e in entries}
        self.by_tag = {}
        for e in entries:
            for tag in e.tags:
                self.by_tag.setdefault(tag, []).append(e)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Registry":
        """Parse a ``version: 2`` labels YAML file into a Registry.

        Parameters:
            path: Filesystem path to the YAML file.

        Returns:
            A new :class:`Registry` instance (not yet validated).

        Raises:
            ValueError: If the YAML does not declare ``version: 2``.
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if data.get("version") != 2:
            raise ValueError(
                f"labels.yaml at {path} must declare 'version: 2', "
                f"got version={data.get('version')!r}"
            )

        entries: list[ClassInfo] = []
        for raw in data.get("entries", []):
            tags_raw = raw.get("tags") or []
            info = ClassInfo(
                id=int(raw["id"]),
                label=str(raw["label"]),
                name=str(raw["name"]),
                tier=str(raw["tier"]),  # type: ignore[arg-type]
                tags=frozenset(tags_raw),
                since_version=str(raw.get("since_version", "v0.0")),
            )
            entries.append(info)

        return cls(entries)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Enforce all structural invariants on this registry.

        Raises:
            ValueError: With a precise message naming the offending entry
                for each invariant violation detected.
        """
        self._validate_dense_ids()
        self._validate_label_regex()
        self._validate_tier_prefix()
        self._validate_canonical_tags()
        self._validate_legacy_alignment()

    def _validate_dense_ids(self) -> None:
        """entries[i].id == i for all i."""
        for i, entry in enumerate(self.entries):
            if entry.id != i:
                raise ValueError(
                    f"Dense-id violation: entries[{i}].id == {entry.id}, "
                    f"expected {i} (entry: {entry.label!r})"
                )

    def _validate_label_regex(self) -> None:
        """Every label must match ^(buff|n|g|r|sr|ssr|sp|ur)_\\d{{3,4}}$."""
        for entry in self.entries:
            if not _LABEL_RE.match(entry.label):
                raise ValueError(
                    f"Label format violation: entry id={entry.id} has "
                    f"label={entry.label!r} which does not match "
                    f"'^(buff|n|g|r|sr|ssr|sp|ur)_\\d{{3,4}}$'"
                )

    def _validate_tier_prefix(self) -> None:
        """e.tier must equal e.label.split('_')[0]."""
        for entry in self.entries:
            expected_tier = entry.label.split("_")[0]
            if entry.tier != expected_tier:
                raise ValueError(
                    f"Tier-prefix mismatch: entry id={entry.id} "
                    f"label={entry.label!r} has tier={entry.tier!r}, "
                    f"expected {expected_tier!r}"
                )

    def _validate_canonical_tags(self) -> None:
        """All tags must be members of CANONICAL_TAGS."""
        for entry in self.entries:
            unknown = entry.tags - CANONICAL_TAGS
            if unknown:
                raise ValueError(
                    f"Unknown tag(s) on entry id={entry.id} "
                    f"label={entry.label!r}: {sorted(unknown)}. "
                    f"Valid tags: {sorted(CANONICAL_TAGS)}"
                )

    def _validate_legacy_alignment(self) -> None:
        """First 219 entries must match LEGACY_SNAPSHOT by (id, label, tier)."""
        check_count = min(len(self.entries), len(LEGACY_SNAPSHOT))
        for i in range(check_count):
            legacy_id, legacy_label, _legacy_name, legacy_tier = LEGACY_SNAPSHOT[i]
            current = self.entries[i]
            if current.label != legacy_label or current.tier != legacy_tier:
                raise ValueError(
                    f"Id-alignment violation at id={i}: legacy has "
                    f"(label={legacy_label!r}, tier={legacy_tier!r}), "
                    f"current has (label={current.label!r}, tier={current.tier!r})"
                )

    # ------------------------------------------------------------------
    # Append-only evolution
    # ------------------------------------------------------------------

    def with_appended(self, new: list[ClassInfo]) -> "Registry":
        """Return a new Registry with *new* entries appended.

        Enforces the append-only invariant: existing entries' ``label`` and
        ``tier`` must not change. ``name`` and ``tags`` MAY change.

        Parameters:
            new: New entries to append. Each entry's ``id`` must equal
                ``len(self.entries) + index_in_new``.

        Returns:
            A new :class:`Registry` containing all existing entries plus *new*.

        Raises:
            ValueError: If any existing entry's label or tier would change,
                or if new entry ids are not dense continuations.
        """
        # Build the candidate entry list — existing entries are preserved as-is.
        candidate_entries = list(self.entries) + new

        # Validate that new entries have correct dense ids.
        base_id = len(self.entries)
        for idx, entry in enumerate(new):
            expected_id = base_id + idx
            if entry.id != expected_id:
                raise ValueError(
                    f"Append-only id violation: new entry at position {idx} "
                    f"has id={entry.id}, expected {expected_id}"
                )

        return Registry(candidate_entries)

    # ------------------------------------------------------------------
    # Diffing
    # ------------------------------------------------------------------

    def diff_against(self, prev: "Registry") -> RegistryDiff:
        """Compute the difference between this registry and a previous one.

        Parameters:
            prev: The previous registry snapshot to compare against.

        Returns:
            A :class:`RegistryDiff` describing all changes.
        """
        diff = RegistryDiff()

        prev_ids = set(prev.classes.keys())
        curr_ids = set(self.classes.keys())

        # Added entries (in current but not in prev).
        for cid in sorted(curr_ids - prev_ids):
            diff.added.append(self.classes[cid])

        # Removed entries (in prev but not in current).
        for cid in sorted(prev_ids - curr_ids):
            diff.removed.append(prev.classes[cid])

        # Changed entries (present in both).
        for cid in sorted(prev_ids & curr_ids):
            old = prev.classes[cid]
            new = self.classes[cid]
            if old.label != new.label:
                diff.label_changed.append((old, new))
            if old.tier != new.tier:
                diff.tier_changed.append((old, new))
            if old.tags != new.tags:
                diff.tags_changed.append((old, new))
            if old.name != new.name:
                diff.name_changed.append((old, new))

        return diff

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def num_classes(self) -> int:
        """Total number of registered classes."""
        return len(self.entries)
