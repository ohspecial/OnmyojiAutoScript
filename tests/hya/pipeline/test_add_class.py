"""Unit tests for the ``hya.pipeline add-class`` CLI subcommand.

Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from hya.pipeline.cli import main


@pytest.fixture(autouse=True)
def _isolate_bootstrap():
    """Prevent bootstrap side effects from polluting test state."""
    import sys
    # Ensure module.hyakkiyakou doesn't auto-bootstrap during test collection
    sys.modules.pop("module.hyakkiyakou", None)
    yield


def _load_registry(path):
    """Helper to load registry without triggering circular imports."""
    from hya.labels.registry import Registry
    return Registry.from_yaml(path)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LABELS_YAML_SRC = Path(__file__).resolve().parents[3] / "hya" / "labels" / "labels.yaml"


@pytest.fixture()
def tmp_labels(tmp_path: Path) -> Path:
    """Copy the real labels.yaml to a temp dir for isolated testing."""
    dest = tmp_path / "labels.yaml"
    shutil.copy2(LABELS_YAML_SRC, dest)
    return dest


# ===========================================================================
# Test successful append
# ===========================================================================


class TestAddClassSuccess:
    """Test successful class addition."""

    def test_append_assigns_correct_id(self, tmp_labels: Path):
        """New class should get id == len(existing entries)."""
        reg_before = _load_registry(tmp_labels)
        expected_id = reg_before.num_classes

        rc = main([
            "add-class",
            "--label", "ssr_900",
            "--name", "新式神",
            "--since-version", "v1.0",
            "--labels", str(tmp_labels),
        ])
        assert rc == 0

        reg_after = _load_registry(tmp_labels)
        assert reg_after.num_classes == expected_id + 1
        new_entry = reg_after.entries[-1]
        assert new_entry.id == expected_id
        assert new_entry.label == "ssr_900"
        assert new_entry.name == "新式神"
        assert new_entry.tier == "ssr"

    def test_append_with_tags(self, tmp_labels: Path):
        """New class with valid tags should be accepted."""
        rc = main([
            "add-class",
            "--label", "r_042",
            "--name", "测试式神",
            "--since-version", "v2.0",
            "--tags", "forbidden",
            "--labels", str(tmp_labels),
        ])
        assert rc == 0

        reg = _load_registry(tmp_labels)
        new_entry = reg.entries[-1]
        assert "forbidden" in new_entry.tags

    def test_append_validates_after_write(self, tmp_labels: Path):
        """After append, the registry should pass validate()."""
        main([
            "add-class",
            "--label", "sp_042",
            "--name", "SP式神",
            "--since-version", "v3.0",
            "--labels", str(tmp_labels),
        ])

        reg = _load_registry(tmp_labels)
        # Should not raise
        reg.validate()

    def test_tier_inferred_from_label_prefix(self, tmp_labels: Path):
        """Tier should be automatically inferred from label prefix."""
        test_cases = [
            ("n_220", "n"),
            ("g_100", "g"),
            ("r_100", "r"),
            ("sr_100", "sr"),
            ("ssr_100", "ssr"),
            ("sp_100", "sp"),
            ("buff_100", "buff"),
        ]
        for label, expected_tier in test_cases:
            # Reload fresh copy each time
            shutil.copy2(LABELS_YAML_SRC, tmp_labels)
            rc = main([
                "add-class",
                "--label", label,
                "--name", f"test_{label}",
                "--since-version", "v1.0",
                "--labels", str(tmp_labels),
            ])
            assert rc == 0, f"Failed for label={label}"
            reg = _load_registry(tmp_labels)
            assert reg.entries[-1].tier == expected_tier, (
                f"Expected tier={expected_tier} for label={label}"
            )


# ===========================================================================
# Test rejection on invalid label format
# ===========================================================================


class TestAddClassInvalidLabel:
    """Test rejection of invalid label formats."""

    def test_rejects_invalid_prefix(self, tmp_labels: Path):
        """Labels with unknown prefix should be rejected."""
        rc = main([
            "add-class",
            "--label", "xyz_001",
            "--name", "bad",
            "--since-version", "v1.0",
            "--labels", str(tmp_labels),
        ])
        assert rc != 0

    def test_rejects_no_underscore(self, tmp_labels: Path):
        """Labels without underscore should be rejected."""
        rc = main([
            "add-class",
            "--label", "ssr001",
            "--name", "bad",
            "--since-version", "v1.0",
            "--labels", str(tmp_labels),
        ])
        assert rc != 0

    def test_rejects_too_few_digits(self, tmp_labels: Path):
        """Labels with fewer than 3 digits should be rejected."""
        rc = main([
            "add-class",
            "--label", "ssr_01",
            "--name", "bad",
            "--since-version", "v1.0",
            "--labels", str(tmp_labels),
        ])
        assert rc != 0

    def test_rejects_non_numeric_suffix(self, tmp_labels: Path):
        """Labels with non-numeric suffix should be rejected."""
        rc = main([
            "add-class",
            "--label", "ssr_abc",
            "--name", "bad",
            "--since-version", "v1.0",
            "--labels", str(tmp_labels),
        ])
        assert rc != 0


# ===========================================================================
# Test rejection on duplicate label
# ===========================================================================


class TestAddClassDuplicate:
    """Test rejection of duplicate labels."""

    def test_rejects_existing_label(self, tmp_labels: Path):
        """Adding a label that already exists should fail."""
        # buff_001 is the first entry in labels.yaml
        rc = main([
            "add-class",
            "--label", "buff_001",
            "--name", "duplicate",
            "--since-version", "v1.0",
            "--labels", str(tmp_labels),
        ])
        assert rc != 0

    def test_rejects_second_add_of_same_label(self, tmp_labels: Path):
        """Adding the same label twice should fail on the second attempt."""
        rc1 = main([
            "add-class",
            "--label", "ssr_099",
            "--name", "first",
            "--since-version", "v1.0",
            "--labels", str(tmp_labels),
        ])
        assert rc1 == 0

        rc2 = main([
            "add-class",
            "--label", "ssr_099",
            "--name", "second",
            "--since-version", "v1.0",
            "--labels", str(tmp_labels),
        ])
        assert rc2 != 0


# ===========================================================================
# Test rejection on unknown tag
# ===========================================================================


class TestAddClassUnknownTag:
    """Test rejection of unknown tags."""

    def test_rejects_unknown_tag(self, tmp_labels: Path):
        """Tags not in CANONICAL_TAGS should be rejected."""
        rc = main([
            "add-class",
            "--label", "ssr_099",
            "--name", "test",
            "--since-version", "v1.0",
            "--tags", "nonexistent_tag",
            "--labels", str(tmp_labels),
        ])
        assert rc != 0

    def test_rejects_if_any_tag_unknown(self, tmp_labels: Path):
        """If any tag is unknown, the whole operation should fail."""
        rc = main([
            "add-class",
            "--label", "ssr_099",
            "--name", "test",
            "--since-version", "v1.0",
            "--tags", "forbidden", "bad_tag",
            "--labels", str(tmp_labels),
        ])
        assert rc != 0

    def test_file_unchanged_on_rejection(self, tmp_labels: Path):
        """On rejection, labels.yaml should not be modified."""
        content_before = tmp_labels.read_text(encoding="utf-8")

        main([
            "add-class",
            "--label", "ssr_099",
            "--name", "test",
            "--since-version", "v1.0",
            "--tags", "bad_tag",
            "--labels", str(tmp_labels),
        ])

        content_after = tmp_labels.read_text(encoding="utf-8")
        assert content_before == content_after
