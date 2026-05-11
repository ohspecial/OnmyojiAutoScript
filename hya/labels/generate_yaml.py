"""One-time generation script: produce labels.yaml v2 from LEGACY_SNAPSHOT.

Usage:
    python hya/labels/generate_yaml.py

Reads the 219-entry LEGACY_SNAPSHOT tuple and writes hya/labels/labels.yaml
with proper tags assigned to buff entries and r_007/r_008.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so we can import hya.labels.legacy_snapshot
_project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_project_root))

from hya.labels.legacy_snapshot import LEGACY_SNAPSHOT

# Tag assignments per the canonical tag vocabulary
BUFF_TAGS: dict[str, list[str]] = {
    "buff_001": ["buff_lantern"],
    "buff_002": ["buff_slow"],
    "buff_003": ["buff_throw_speed"],
    "buff_004": ["buff_bean_gain"],
    "buff_005": ["buff_freeze"],
    "buff_006": ["buff_prob_up"],
    "buff_007": ["buff_friend_up"],
}

FORBIDDEN_LABELS: set[str] = {"r_007", "r_008"}


def format_tags(tags: list[str]) -> str:
    """Format tags list as YAML flow sequence."""
    if not tags:
        return "[]"
    return "[" + ", ".join(tags) + "]"


def format_entry(id_: int, label: str, name: str, tier: str, tags: list[str]) -> str:
    """Format a single entry as a YAML flow mapping."""
    return (
        f'  - {{id: {id_}, label: {label}, name: "{name}", '
        f"tier: {tier}, tags: {format_tags(tags)}, since_version: v0.0}}"
    )


def generate() -> str:
    """Generate the full labels.yaml content."""
    lines: list[str] = []
    lines.append("version: 2")
    lines.append("entries:")

    for id_, label, name, tier in LEGACY_SNAPSHOT:
        # Determine tags
        if label in BUFF_TAGS:
            tags = BUFF_TAGS[label]
        elif label in FORBIDDEN_LABELS:
            tags = ["forbidden"]
        else:
            tags = []

        lines.append(format_entry(id_, label, name, tier, tags))

    # Trailing newline
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    output_path = Path(__file__).resolve().parent / "labels.yaml"
    content = generate()
    output_path.write_text(content, encoding="utf-8")
    print(f"Generated {output_path} ({len(LEGACY_SNAPSHOT)} entries)")


if __name__ == "__main__":
    main()
