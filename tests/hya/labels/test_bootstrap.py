"""Tests for module.hyakkiyakou.bootstrap — sys.modules injection.

Validates:
- install() makes ``import oashya.labels`` resolve to the shim
- install() is idempotent
- uninstall() reverses the injection
- After install(), all legacy API surface is accessible via oashya.labels
"""

from __future__ import annotations

import importlib
import sys

import pytest

from module.hyakkiyakou.bootstrap import install, uninstall, is_installed


@pytest.fixture(autouse=True)
def _clean_bootstrap():
    """Ensure bootstrap state is clean before and after each test."""
    uninstall()
    # Remove cached oashya.labels from sys.modules if present
    sys.modules.pop("oashya.labels", None)
    yield
    uninstall()
    sys.modules.pop("oashya.labels", None)


class TestInstall:
    """Test install() behavior."""

    def test_install_injects_shim(self):
        """After install(), sys.modules['oashya.labels'] should be the shim."""
        install()
        assert "oashya.labels" in sys.modules
        from hya.labels import shim
        assert sys.modules["oashya.labels"] is shim

    def test_install_creates_oashya_namespace(self):
        """install() should create 'oashya' in sys.modules if not present."""
        sys.modules.pop("oashya", None)
        install()
        assert "oashya" in sys.modules

    def test_install_is_idempotent(self):
        """Calling install() twice should not raise or change behavior."""
        install()
        first_module = sys.modules["oashya.labels"]
        install()
        assert sys.modules["oashya.labels"] is first_module

    def test_is_installed_reflects_state(self):
        """is_installed() should return True after install(), False after uninstall()."""
        assert not is_installed()
        install()
        assert is_installed()
        uninstall()
        assert not is_installed()


class TestUninstall:
    """Test uninstall() behavior."""

    def test_uninstall_removes_shim(self):
        """After uninstall(), 'oashya.labels' should not be in sys.modules."""
        install()
        assert "oashya.labels" in sys.modules
        uninstall()
        assert "oashya.labels" not in sys.modules

    def test_uninstall_is_idempotent(self):
        """Calling uninstall() when not installed should not raise."""
        uninstall()  # should be a no-op
        assert not is_installed()


class TestLegacyImportAfterBootstrap:
    """Test that legacy import patterns work after bootstrap."""

    def test_from_oashya_labels_import_classindex(self):
        """from oashya.labels import CLASSINDEX should work after install()."""
        install()
        # Use importlib to simulate a fresh import
        oashya_labels = sys.modules["oashya.labels"]
        assert hasattr(oashya_labels, "CLASSINDEX")

    def test_from_oashya_labels_import_id2label(self):
        """from oashya.labels import id2label should work after install()."""
        install()
        oashya_labels = sys.modules["oashya.labels"]
        assert callable(oashya_labels.id2label)
        # Verify it returns correct value
        assert oashya_labels.id2label(0) == "buff_001"

    def test_from_oashya_labels_import_id2name(self):
        """from oashya.labels import id2name should work after install()."""
        install()
        oashya_labels = sys.modules["oashya.labels"]
        assert callable(oashya_labels.id2name)
        assert oashya_labels.id2name(0) == "式神灯笼"

    def test_from_oashya_labels_import_label2id(self):
        """from oashya.labels import label2id should work after install()."""
        install()
        oashya_labels = sys.modules["oashya.labels"]
        assert callable(oashya_labels.label2id)
        assert oashya_labels.label2id("buff_001") == 0

    def test_from_oashya_labels_import_classify(self):
        """from oashya.labels import CLASSIFY should work after install()."""
        install()
        oashya_labels = sys.modules["oashya.labels"]
        assert hasattr(oashya_labels, "CLASSIFY")
        assert len(oashya_labels.CLASSIFY) == 219

    def test_from_oashya_labels_import_tier_dicts(self):
        """Tier dicts (sp, ssr, sr, r, n, g, buff) should be accessible."""
        install()
        oashya_labels = sys.modules["oashya.labels"]
        for tier_name in ("sp", "ssr", "sr", "r", "n", "g", "buff"):
            assert hasattr(oashya_labels, tier_name)
            assert isinstance(getattr(oashya_labels, tier_name), dict)

    def test_classindex_min_max_via_bootstrap(self):
        """CLASSINDEX.MIN_SP / MAX_SP should work via bootstrapped module."""
        install()
        oashya_labels = sys.modules["oashya.labels"]
        CI = oashya_labels.CLASSINDEX
        # SP range: ids 184-218
        assert CI.MIN_SP == 184
        assert CI.MAX_SP == 218

    def test_attribute_access_on_oashya_namespace(self):
        """oashya.labels should be accessible as attribute on oashya module."""
        install()
        oashya = sys.modules["oashya"]
        assert hasattr(oashya, "labels")
        assert oashya.labels is sys.modules["oashya.labels"]
