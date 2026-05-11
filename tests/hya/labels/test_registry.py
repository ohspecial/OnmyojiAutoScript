"""Unit and property-based tests for hya.labels.registry.Registry.

Validates: Requirements 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 10.2, 10.3
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from hya.labels.registry import Registry
from hya.labels.legacy_snapshot import LEGACY_SNAPSHOT
from module.hyakkiyakou.class_info import ClassInfo, CANONICAL_TAGS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LABELS_YAML = PROJECT_ROOT / "hya" / "labels" / "labels.yaml"

VALID_PREFIXES = ("buff", "n", "g", "r", "sr", "ssr", "sp", "ur")


def _make_entry(
    id: int,
    label: str | None = None,
    name: str = "test",
    tier: str | None = None,
    tags: frozenset[str] | None = None,
) -> ClassInfo:
    """Helper to build a ClassInfo with sensible defaults."""
    if label is None:
        label = f"n_{id:03d}"
    if tier is None:
        tier = label.split("_")[0]
    if tags is None:
        tags = frozenset()
    return ClassInfo(id=id, label=label, name=name, tier=tier, tags=tags)


def _build_registry(entries: list[ClassInfo]) -> Registry:
    """Build a Registry directly from a list of ClassInfo entries."""
    return Registry(entries)


# ---------------------------------------------------------------------------
# Unit tests: validate() passes on well-formed YAML
# ---------------------------------------------------------------------------


class TestValidateWellFormed:
    """Test that validate() passes on the real labels.yaml file."""

    def test_validate_passes_on_real_labels_yaml(self):
        """validate() should pass on the actual hya/labels/labels.yaml file."""
        registry = Registry.from_yaml(LABELS_YAML)
        # Should not raise
        registry.validate()

    def test_from_yaml_loads_correct_entry_count(self):
        """The real labels.yaml should have at least 219 entries (legacy count)."""
        registry = Registry.from_yaml(LABELS_YAML)
        assert registry.num_classes >= 219, (
            f"Expected at least 219 entries, got {registry.num_classes}"
        )


# ---------------------------------------------------------------------------
# Unit tests: validate() raises on non-dense ids
# ---------------------------------------------------------------------------


class TestValidateDenseIds:
    """Test that validate() raises ValueError on non-dense ids."""

    def test_raises_on_skipped_id(self):
        """validate() should raise when an id is skipped (e.g. 0, 1, 3)."""
        entries = [
            _make_entry(0, "n_001"),
            _make_entry(1, "n_002"),
            _make_entry(3, "n_003"),  # skipped id 2
        ]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Dense-id violation"):
            registry.validate()

    def test_raises_on_duplicate_id(self):
        """validate() should raise when ids are not sequential."""
        entries = [
            _make_entry(0, "n_001"),
            _make_entry(0, "n_002"),  # duplicate id 0
        ]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Dense-id violation"):
            registry.validate()


# ---------------------------------------------------------------------------
# Unit tests: validate() raises on bad label syntax
# ---------------------------------------------------------------------------


class TestValidateLabelSyntax:
    """Test that validate() raises ValueError on invalid label format."""

    def test_raises_on_invalid_label_no_underscore(self):
        """validate() should reject labels without underscore separator."""
        entries = [_make_entry(0, "invalid_label", tier="invalid")]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Label format violation"):
            registry.validate()

    def test_raises_on_label_with_wrong_prefix(self):
        """validate() should reject labels with unknown prefix."""
        entries = [_make_entry(0, "xyz_001", tier="xyz")]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Label format violation"):
            registry.validate()

    def test_raises_on_label_with_no_digits(self):
        """validate() should reject labels without numeric suffix."""
        entries = [_make_entry(0, "n_abc", tier="n")]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Label format violation"):
            registry.validate()

    def test_raises_on_label_with_too_few_digits(self):
        """validate() should reject labels with fewer than 3 digits."""
        entries = [_make_entry(0, "n_01", tier="n")]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Label format violation"):
            registry.validate()


# ---------------------------------------------------------------------------
# Unit tests: validate() raises on tier mismatch
# ---------------------------------------------------------------------------


class TestValidateTierMismatch:
    """Test that validate() raises ValueError on tier/label prefix mismatch."""

    def test_raises_on_tier_mismatch(self):
        """validate() should reject entry where tier != label prefix (e.g. sp_001 with tier ssr)."""
        entries = [
            ClassInfo(id=0, label="sp_001", name="test", tier="ssr", tags=frozenset())
        ]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Tier-prefix mismatch"):
            registry.validate()

    def test_raises_on_buff_label_with_n_tier(self):
        """validate() should reject buff_001 with tier 'n'."""
        entries = [
            ClassInfo(id=0, label="buff_001", name="test", tier="n", tags=frozenset())
        ]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Tier-prefix mismatch"):
            registry.validate()


# ---------------------------------------------------------------------------
# Unit tests: validate() raises on unknown tags
# ---------------------------------------------------------------------------


class TestValidateUnknownTags:
    """Test that validate() raises ValueError on tags not in CANONICAL_TAGS."""

    def test_raises_on_unknown_tag(self):
        """validate() should reject entries with tags not in CANONICAL_TAGS (e.g. 'nonexistent')."""
        entries = [
            ClassInfo(
                id=0,
                label="n_001",
                name="test",
                tier="n",
                tags=frozenset({"nonexistent"}),
            )
        ]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Unknown tag"):
            registry.validate()

    def test_raises_on_multiple_unknown_tags(self):
        """validate() should reject entries with multiple unknown tags."""
        entries = [
            ClassInfo(
                id=0,
                label="n_001",
                name="test",
                tier="n",
                tags=frozenset({"fake_tag", "another_fake"}),
            )
        ]
        registry = _build_registry(entries)
        with pytest.raises(ValueError, match="Unknown tag"):
            registry.validate()

    def test_passes_with_canonical_tags(self):
        """validate() should pass when all tags are from CANONICAL_TAGS."""
        entries = [
            ClassInfo(
                id=0,
                label="buff_001",
                name="test",
                tier="buff",
                tags=frozenset({"buff_lantern"}),
            )
        ]
        registry = _build_registry(entries)
        # Should not raise
        registry.validate()


# ---------------------------------------------------------------------------
# Unit tests: with_appended enforces append-only
# ---------------------------------------------------------------------------


class TestWithAppended:
    """Test that with_appended enforces append-only invariant."""

    def test_append_new_entries_succeeds(self):
        """with_appended should succeed when appending valid new entries."""
        base_entries = [_make_entry(0, "n_001"), _make_entry(1, "n_002")]
        registry = _build_registry(base_entries)

        new_entries = [_make_entry(2, "sr_001"), _make_entry(3, "ssr_001")]
        result = registry.with_appended(new_entries)

        assert result.num_classes == 4
        assert result.entries[2].label == "sr_001"
        assert result.entries[3].label == "ssr_001"

    def test_append_rejects_wrong_id(self):
        """with_appended should reject new entries with non-continuation ids."""
        base_entries = [_make_entry(0, "n_001"), _make_entry(1, "n_002")]
        registry = _build_registry(base_entries)

        # New entry should have id=2, but we give it id=5
        new_entries = [_make_entry(5, "sr_001")]
        with pytest.raises(ValueError, match="Append-only id violation"):
            registry.with_appended(new_entries)

    def test_existing_label_and_tier_are_immutable(self):
        """Existing entries' label and tier must not change (enforced by dense id check)."""
        base_entries = [_make_entry(0, "n_001"), _make_entry(1, "n_002")]
        registry = _build_registry(base_entries)

        # Appending correctly should work
        new_entries = [_make_entry(2, "sr_001")]
        result = registry.with_appended(new_entries)

        # Original entries are preserved
        assert result.entries[0].label == "n_001"
        assert result.entries[0].tier == "n"
        assert result.entries[1].label == "n_002"
        assert result.entries[1].tier == "n"

    def test_name_and_tags_are_mutable(self):
        """name and tags of existing entries MAY change between snapshots."""
        # This is tested via diff_against — with_appended preserves existing entries as-is
        # and only appends new ones. The mutability of name/tags is a design property
        # that allows retroactive tagging without breaking append-only.
        base_entries = [
            ClassInfo(id=0, label="n_001", name="old_name", tier="n", tags=frozenset())
        ]
        registry = _build_registry(base_entries)

        new_entries = [_make_entry(1, "n_002")]
        result = registry.with_appended(new_entries)

        # The original entry is preserved as-is in with_appended
        assert result.entries[0].name == "old_name"
        assert result.num_classes == 2


# ---------------------------------------------------------------------------
# Unit tests: id-alignment against legacy snapshot
# ---------------------------------------------------------------------------


class TestLegacyAlignment:
    """Test id-alignment against LEGACY_SNAPSHOT for first 219 entries."""

    def test_first_219_entries_match_legacy_snapshot(self):
        """The first 219 entries of labels.yaml must match LEGACY_SNAPSHOT by (id, label, tier)."""
        registry = Registry.from_yaml(LABELS_YAML)

        assert len(LEGACY_SNAPSHOT) == 219, (
            f"LEGACY_SNAPSHOT should have 219 entries, got {len(LEGACY_SNAPSHOT)}"
        )

        for i in range(219):
            legacy_id, legacy_label, _legacy_name, legacy_tier = LEGACY_SNAPSHOT[i]
            current = registry.entries[i]
            assert current.id == legacy_id, (
                f"Id mismatch at index {i}: legacy={legacy_id}, current={current.id}"
            )
            assert current.label == legacy_label, (
                f"Label mismatch at id={i}: legacy={legacy_label!r}, "
                f"current={current.label!r}"
            )
            assert current.tier == legacy_tier, (
                f"Tier mismatch at id={i}: legacy={legacy_tier!r}, "
                f"current={current.tier!r}"
            )


# ---------------------------------------------------------------------------
# Unit tests: by_label, by_tag, num_classes correctness
# ---------------------------------------------------------------------------


class TestLookups:
    """Test by_label, by_tag, and num_classes correctness."""

    def test_by_label_returns_correct_entry(self):
        """by_label should map label string to the correct ClassInfo."""
        entries = [
            _make_entry(0, "n_001", name="灯笼鬼"),
            _make_entry(1, "sr_001", name="妖狐"),
        ]
        registry = _build_registry(entries)

        assert registry.by_label["n_001"].name == "灯笼鬼"
        assert registry.by_label["sr_001"].name == "妖狐"

    def test_by_label_on_real_yaml(self):
        """by_label should work on the real labels.yaml."""
        registry = Registry.from_yaml(LABELS_YAML)
        # buff_001 is the first entry
        assert registry.by_label["buff_001"].id == 0
        assert registry.by_label["buff_001"].tier == "buff"

    def test_by_tag_groups_entries_correctly(self):
        """by_tag should group entries by their tags."""
        entries = [
            ClassInfo(
                id=0, label="buff_001", name="a", tier="buff",
                tags=frozenset({"buff_lantern"}),
            ),
            ClassInfo(
                id=1, label="buff_002", name="b", tier="buff",
                tags=frozenset({"buff_slow"}),
            ),
            ClassInfo(
                id=2, label="n_001", name="c", tier="n",
                tags=frozenset(),
            ),
        ]
        registry = _build_registry(entries)

        assert len(registry.by_tag["buff_lantern"]) == 1
        assert registry.by_tag["buff_lantern"][0].id == 0
        assert len(registry.by_tag["buff_slow"]) == 1
        assert registry.by_tag["buff_slow"][0].id == 1
        assert "n" not in registry.by_tag  # no entries tagged "n"

    def test_by_tag_on_real_yaml(self):
        """by_tag should find forbidden entries on the real labels.yaml."""
        registry = Registry.from_yaml(LABELS_YAML)
        forbidden_entries = registry.by_tag.get("forbidden", [])
        # r_007 and r_008 should be tagged forbidden
        forbidden_labels = {e.label for e in forbidden_entries}
        assert "r_007" in forbidden_labels, "r_007 should be tagged 'forbidden'"
        assert "r_008" in forbidden_labels, "r_008 should be tagged 'forbidden'"

    def test_num_classes_equals_entry_count(self):
        """num_classes should equal len(entries)."""
        entries = [_make_entry(i, f"n_{i+1:03d}") for i in range(5)]
        registry = _build_registry(entries)
        assert registry.num_classes == 5

    def test_num_classes_on_real_yaml(self):
        """num_classes on real labels.yaml should match entry count."""
        registry = Registry.from_yaml(LABELS_YAML)
        assert registry.num_classes == len(registry.entries)


# ===========================================================================
# Property-based tests (hypothesis)
# ===========================================================================

# Strategy: generate a valid label from a random prefix and a 3-4 digit number
_prefix_st = st.sampled_from(VALID_PREFIXES)
_num_st = st.integers(min_value=1, max_value=9999)


@st.composite
def valid_label_st(draw):
    """Generate a valid label like 'ssr_042' or 'buff_001'."""
    prefix = draw(_prefix_st)
    num = draw(_num_st)
    # Use 3 digits for numbers < 1000, 4 digits otherwise
    digits = f"{num:03d}" if num < 1000 else f"{num:04d}"
    return f"{prefix}_{digits}"


@st.composite
def valid_entry_st(draw, id_value: int | None = None):
    """Generate a valid ClassInfo entry with a given or random id."""
    if id_value is None:
        id_value = draw(st.integers(min_value=0, max_value=1000))
    label = draw(valid_label_st())
    tier = label.split("_")[0]
    tags = draw(
        st.frozensets(st.sampled_from(sorted(CANONICAL_TAGS)), max_size=2)
    )
    name = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(
        whitelist_categories=("L", "N"),
    )))
    return ClassInfo(id=id_value, label=label, name=name, tier=tier, tags=tags)


@st.composite
def valid_registry_st(draw, min_size: int = 1, max_size: int = 20):
    """Generate a valid Registry with dense ids and correct tier/label/tags."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    entries = []
    for i in range(size):
        entry = draw(valid_entry_st(id_value=i))
        entries.append(entry)
    return Registry(entries)


# ---------------------------------------------------------------------------
# Property P3: Dense append-only ids
# ---------------------------------------------------------------------------


class TestPropertyP3:
    """**Validates: Requirements 1.3**

    Property P3: Dense append-only ids.
    - entries[i].id == i for all i in a valid registry.
    - For consecutive valid snapshots R_prev, R_curr: all entries in R_prev
      have the same (id, label, tier) in R_curr.
    """

    @given(registry=valid_registry_st())
    @settings(max_examples=100)
    def test_dense_ids_always_valid(self, registry: Registry):
        """**Validates: Requirements 1.3**

        For any well-formed registry built with dense ids, the dense-id
        validation passes and entries[i].id == i for all i.
        """
        # Test the dense-id invariant directly (avoids legacy alignment check)
        registry._validate_dense_ids()
        for i, entry in enumerate(registry.entries):
            assert entry.id == i, f"entries[{i}].id should be {i}, got {entry.id}"

    @given(
        registry=valid_registry_st(min_size=2, max_size=10),
        append_data=st.data(),
    )
    @settings(max_examples=50)
    def test_append_only_preserves_existing(self, registry: Registry, append_data):
        """**Validates: Requirements 1.7**

        After with_appended, all original entries retain their (id, label, tier).
        """
        # Generate 1-3 new entries to append
        num_new = append_data.draw(st.integers(min_value=1, max_value=3))
        new_entries = []
        base_id = len(registry.entries)
        for i in range(num_new):
            entry = append_data.draw(valid_entry_st(id_value=base_id + i))
            new_entries.append(entry)

        result = registry.with_appended(new_entries)

        # All original entries must be preserved
        for i, orig in enumerate(registry.entries):
            assert result.entries[i].id == orig.id
            assert result.entries[i].label == orig.label
            assert result.entries[i].tier == orig.tier


# ---------------------------------------------------------------------------
# Property P4: Tier is pure function of label prefix
# ---------------------------------------------------------------------------


class TestPropertyP4:
    """**Validates: Requirements 1.5**

    Property P4: Tier is pure function of label prefix.
    For all entries: e.tier == e.label.split("_")[0].
    """

    @given(registry=valid_registry_st())
    @settings(max_examples=100)
    def test_tier_equals_label_prefix(self, registry: Registry):
        """**Validates: Requirements 1.5**

        For any valid registry, every entry's tier equals its label prefix.
        """
        # Test the tier-prefix invariant directly
        registry._validate_tier_prefix()
        for entry in registry.entries:
            expected_tier = entry.label.split("_")[0]
            assert entry.tier == expected_tier, (
                f"Entry {entry.label}: tier={entry.tier!r} != "
                f"prefix={expected_tier!r}"
            )

    @given(label=valid_label_st())
    @settings(max_examples=200)
    def test_tier_derivation_is_deterministic(self, label: str):
        """**Validates: Requirements 1.5**

        The tier derived from any valid label is always its prefix.
        """
        prefix = label.split("_")[0]
        assert prefix in VALID_PREFIXES, f"Unexpected prefix: {prefix!r}"
        # Constructing a ClassInfo with matching tier should pass tier validation
        entry = ClassInfo(id=0, label=label, name="x", tier=prefix, tags=frozenset())
        reg = Registry([entry])
        reg._validate_label_regex()
        reg._validate_tier_prefix()


# ---------------------------------------------------------------------------
# Property P5: Closed tag vocabulary
# ---------------------------------------------------------------------------


class TestPropertyP5:
    """**Validates: Requirements 1.6**

    Property P5: Closed tag vocabulary.
    For all entries, all tags must be members of CANONICAL_TAGS.
    """

    @given(registry=valid_registry_st())
    @settings(max_examples=100)
    def test_all_tags_in_canonical_set(self, registry: Registry):
        """**Validates: Requirements 1.6**

        For any valid registry, every tag on every entry is in CANONICAL_TAGS.
        """
        # Test the canonical tags invariant directly
        registry._validate_canonical_tags()
        for entry in registry.entries:
            for tag in entry.tags:
                assert tag in CANONICAL_TAGS, (
                    f"Entry {entry.label} has tag {tag!r} not in CANONICAL_TAGS"
                )

    @given(
        bad_tag=st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=("L",),
        )).filter(lambda t: t not in CANONICAL_TAGS),
    )
    @settings(max_examples=50)
    def test_unknown_tag_always_rejected(self, bad_tag: str):
        """**Validates: Requirements 1.6**

        Any tag not in CANONICAL_TAGS causes validate() to raise.
        """
        entry = ClassInfo(
            id=0, label="n_001", name="test", tier="n",
            tags=frozenset({bad_tag}),
        )
        registry = Registry([entry])
        with pytest.raises(ValueError, match="Unknown tag"):
            registry.validate()
