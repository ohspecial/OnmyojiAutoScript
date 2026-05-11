"""Compatibility tests for hya.labels.shim against the legacy oashya.labels API.

Validates that the shim module exposes the exact same surface as the original
``oashya.labels`` package, ensuring zero-breakage for existing callers:
- Tier dicts (sp, ssr, sr, r, n, g, buff)
- CLASSIFY list
- id2label / id2name / label2id functions
- CLASSINDEX.MIN_X / MAX_X / BUFF_00X / R_007 / R_008
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from hya.labels import shim
from hya.labels.legacy_snapshot import LEGACY_SNAPSHOT
from hya.labels.registry import Registry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LABELS_YAML = Path(__file__).resolve().parents[3] / "hya" / "labels" / "labels.yaml"


@pytest.fixture(scope="module")
def registry() -> Registry:
    """Load the real registry for cross-validation."""
    reg = Registry.from_yaml(LABELS_YAML)
    reg.validate()
    return reg


# ===========================================================================
# 2.2.1 Tier dicts
# ===========================================================================


class TestTierDicts:
    """Verify tier dicts match legacy snapshot content."""

    def test_sp_dict_keys_match_legacy(self):
        """sp dict should contain exactly the SP labels from LEGACY_SNAPSHOT."""
        expected = {label for _, label, _, tier in LEGACY_SNAPSHOT if tier == "sp"}
        assert set(shim.sp.keys()) == expected

    def test_ssr_dict_keys_match_legacy(self):
        expected = {label for _, label, _, tier in LEGACY_SNAPSHOT if tier == "ssr"}
        assert set(shim.ssr.keys()) == expected

    def test_sr_dict_keys_match_legacy(self):
        expected = {label for _, label, _, tier in LEGACY_SNAPSHOT if tier == "sr"}
        assert set(shim.sr.keys()) == expected

    def test_r_dict_keys_match_legacy(self):
        expected = {label for _, label, _, tier in LEGACY_SNAPSHOT if tier == "r"}
        assert set(shim.r.keys()) == expected

    def test_n_dict_keys_match_legacy(self):
        expected = {label for _, label, _, tier in LEGACY_SNAPSHOT if tier == "n"}
        assert set(shim.n.keys()) == expected

    def test_g_dict_keys_match_legacy(self):
        expected = {label for _, label, _, tier in LEGACY_SNAPSHOT if tier == "g"}
        assert set(shim.g.keys()) == expected

    def test_buff_dict_keys_match_legacy(self):
        expected = {label for _, label, _, tier in LEGACY_SNAPSHOT if tier == "buff"}
        assert set(shim.buff.keys()) == expected

    def test_tier_dict_values_are_names(self):
        """Each tier dict value should be the human-readable name."""
        for id_, label, name, tier in LEGACY_SNAPSHOT:
            tier_dict = getattr(shim, tier)
            assert tier_dict[label] == name, (
                f"Tier dict '{tier}' has wrong name for {label}: "
                f"expected {name!r}, got {tier_dict[label]!r}"
            )

    def test_tier_dicts_are_disjoint(self):
        """No label should appear in more than one tier dict."""
        all_keys: list[str] = []
        for tier_name in ("sp", "ssr", "sr", "r", "n", "g", "buff"):
            all_keys.extend(getattr(shim, tier_name).keys())
        assert len(all_keys) == len(set(all_keys)), "Duplicate labels across tier dicts"

    def test_tier_dicts_cover_all_entries(self):
        """Union of all tier dicts should cover all 219 legacy entries."""
        all_labels = set()
        for tier_name in ("sp", "ssr", "sr", "r", "n", "g", "buff"):
            all_labels.update(getattr(shim, tier_name).keys())
        expected_labels = {label for _, label, _, _ in LEGACY_SNAPSHOT}
        assert all_labels == expected_labels


# ===========================================================================
# 2.2.2 CLASSIFY list
# ===========================================================================


class TestClassify:
    """Verify CLASSIFY list matches legacy format."""

    def test_classify_length(self):
        """CLASSIFY should have exactly 219 entries."""
        assert len(shim.CLASSIFY) == 219

    def test_classify_is_list_of_dicts(self):
        """Each CLASSIFY entry should be a dict with keys 'name', 'class', 'id'."""
        for entry in shim.CLASSIFY:
            assert isinstance(entry, dict)
            assert "name" in entry
            assert "class" in entry
            assert "id" in entry

    def test_classify_id_order(self):
        """CLASSIFY should be in id order (0, 1, 2, ...)."""
        for i, entry in enumerate(shim.CLASSIFY):
            assert entry["id"] == i, f"CLASSIFY[{i}] has id={entry['id']}"

    def test_classify_matches_legacy_snapshot(self):
        """Each CLASSIFY entry should match LEGACY_SNAPSHOT by id, label, name."""
        for i, (legacy_id, legacy_label, legacy_name, _) in enumerate(LEGACY_SNAPSHOT):
            entry = shim.CLASSIFY[i]
            assert entry["id"] == legacy_id
            assert entry["class"] == legacy_label
            assert entry["name"] == legacy_name


# ===========================================================================
# 2.2.3 Lookup functions
# ===========================================================================


class TestLookupFunctions:
    """Verify id2label, id2name, label2id match legacy data."""

    def test_id2label_all_entries(self):
        """id2label should return correct label for all 219 ids."""
        for id_, label, _, _ in LEGACY_SNAPSHOT:
            assert shim.id2label(id_) == label

    def test_id2name_all_entries(self):
        """id2name should return correct name for all 219 ids."""
        for id_, _, name, _ in LEGACY_SNAPSHOT:
            assert shim.id2name(id_) == name

    def test_label2id_all_entries(self):
        """label2id should return correct id for all 219 labels."""
        for id_, label, _, _ in LEGACY_SNAPSHOT:
            assert shim.label2id(label) == id_

    def test_id2label_roundtrip(self):
        """label2id(id2label(i)) == i for all valid ids."""
        for i in range(219):
            assert shim.label2id(shim.id2label(i)) == i

    def test_id2label_out_of_range_raises(self):
        """id2label with invalid id should raise KeyError."""
        with pytest.raises(KeyError):
            shim.id2label(999)

    def test_label2id_unknown_label_raises(self):
        """label2id with unknown label should raise KeyError."""
        with pytest.raises(KeyError):
            shim.label2id("nonexistent_999")


# ===========================================================================
# 2.2.4 CLASSINDEX deprecated attributes
# ===========================================================================


class TestClassIndex:
    """Verify CLASSINDEX.MIN_X/MAX_X, BUFF_00X, R_007/R_008."""

    # --- MIN/MAX tier boundaries ---

    def test_min_buff(self):
        buff_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "buff"]
        assert shim.CLASSINDEX.MIN_BUFF == min(buff_ids)

    def test_max_buff(self):
        buff_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "buff"]
        assert shim.CLASSINDEX.MAX_BUFF == max(buff_ids)

    def test_min_n(self):
        n_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "n"]
        assert shim.CLASSINDEX.MIN_N == min(n_ids)

    def test_max_n(self):
        n_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "n"]
        assert shim.CLASSINDEX.MAX_N == max(n_ids)

    def test_min_g(self):
        g_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "g"]
        assert shim.CLASSINDEX.MIN_G == min(g_ids)

    def test_max_g(self):
        g_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "g"]
        assert shim.CLASSINDEX.MAX_G == max(g_ids)

    def test_min_r(self):
        r_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "r"]
        assert shim.CLASSINDEX.MIN_R == min(r_ids)

    def test_max_r(self):
        r_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "r"]
        assert shim.CLASSINDEX.MAX_R == max(r_ids)

    def test_min_sr(self):
        sr_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "sr"]
        assert shim.CLASSINDEX.MIN_SR == min(sr_ids)

    def test_max_sr(self):
        sr_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "sr"]
        assert shim.CLASSINDEX.MAX_SR == max(sr_ids)

    def test_min_ssr(self):
        ssr_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "ssr"]
        assert shim.CLASSINDEX.MIN_SSR == min(ssr_ids)

    def test_max_ssr(self):
        ssr_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "ssr"]
        assert shim.CLASSINDEX.MAX_SSR == max(ssr_ids)

    def test_min_sp(self):
        sp_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "sp"]
        assert shim.CLASSINDEX.MIN_SP == min(sp_ids)

    def test_max_sp(self):
        sp_ids = [id_ for id_, _, _, tier in LEGACY_SNAPSHOT if tier == "sp"]
        assert shim.CLASSINDEX.MAX_SP == max(sp_ids)

    # --- BUFF constants ---

    def test_buff_001(self):
        assert shim.CLASSINDEX.BUFF_001 == 0  # buff_001 -> id 0

    def test_buff_002(self):
        assert shim.CLASSINDEX.BUFF_002 == 1

    def test_buff_003(self):
        assert shim.CLASSINDEX.BUFF_003 == 2

    def test_buff_004(self):
        assert shim.CLASSINDEX.BUFF_004 == 3

    def test_buff_005(self):
        assert shim.CLASSINDEX.BUFF_005 == 4

    def test_buff_006(self):
        assert shim.CLASSINDEX.BUFF_006 == 5

    def test_buff_007(self):
        assert shim.CLASSINDEX.BUFF_007 == 6

    # --- R_007 / R_008 (forbidden) ---

    def test_r_007(self):
        assert shim.CLASSINDEX.R_007 == 42  # r_007 -> id 42

    def test_r_008(self):
        assert shim.CLASSINDEX.R_008 == 43  # r_008 -> id 43

    # --- Deprecation warnings ---

    def test_min_max_emits_deprecation_warning(self):
        """Accessing MIN_X/MAX_X should emit DeprecationWarning."""
        # Reset the warned set to ensure we get a warning
        shim.CLASSINDEX._ClassIndexMeta__warned = set()
        shim._ClassIndexMeta._warned = set()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = shim.CLASSINDEX.MIN_SP
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1, "Expected DeprecationWarning for MIN_SP"

    # --- Invalid attribute ---

    def test_invalid_attribute_raises(self):
        """Accessing a non-existent attribute should raise AttributeError."""
        with pytest.raises(AttributeError):
            _ = shim.CLASSINDEX.NONEXISTENT

    def test_invalid_tier_raises(self):
        """Accessing MIN_INVALID should raise AttributeError."""
        with pytest.raises(AttributeError):
            _ = shim.CLASSINDEX.MIN_INVALID


# ===========================================================================
# 2.2.5 Module-level attribute completeness
# ===========================================================================


class TestModuleSurface:
    """Verify the shim module exposes all expected names."""

    EXPECTED_NAMES = [
        "sp", "ssr", "sr", "r", "n", "g", "buff",
        "CLASSIFY",
        "id2label", "id2name", "label2id",
        "CLASSINDEX",
    ]

    def test_all_expected_names_exist(self):
        """All expected public names should be accessible on the shim module."""
        for name in self.EXPECTED_NAMES:
            assert hasattr(shim, name), f"shim module missing attribute: {name}"

    def test_tier_dicts_are_plain_dicts(self):
        """Tier dicts should be plain dict instances."""
        for tier_name in ("sp", "ssr", "sr", "r", "n", "g", "buff"):
            obj = getattr(shim, tier_name)
            assert isinstance(obj, dict), f"shim.{tier_name} is not a dict"

    def test_classify_is_list(self):
        """CLASSIFY should be a list."""
        assert isinstance(shim.CLASSIFY, list)

    def test_lookup_functions_are_callable(self):
        """id2label, id2name, label2id should be callable."""
        assert callable(shim.id2label)
        assert callable(shim.id2name)
        assert callable(shim.label2id)
