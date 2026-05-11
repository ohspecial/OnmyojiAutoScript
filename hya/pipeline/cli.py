"""Pipeline CLI — subcommands for managing the Hyakkiyakou label registry.

Usage::

    python -m hya.pipeline add-class --label ssr_042 --name "新式神" --since-version v1.2 [--tags forbidden]

Subcommands:
    add-class   Append a new class entry to labels.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# Default labels.yaml path (relative to project root)
_DEFAULT_LABELS_YAML = Path(__file__).resolve().parents[2] / "hya" / "labels" / "labels.yaml"

# Label regex — must match the one in Registry
_LABEL_RE = re.compile(r"^(buff|n|g|r|sr|ssr|sp|ur)_\d{3,4}$")


def _add_class(args: argparse.Namespace) -> int:
    """Handle the ``add-class`` subcommand.

    Returns:
        0 on success, non-zero on failure.
    """
    # Lazy imports to avoid circular dependency through module.hyakkiyakou.__init__
    from hya.labels.class_info import CANONICAL_TAGS  # noqa: E402
    from hya.labels.registry import Registry  # noqa: E402

    labels_path = Path(args.labels) if args.labels else _DEFAULT_LABELS_YAML

    # Validate label format
    label: str = args.label
    if not _LABEL_RE.match(label):
        print(
            f"Error: label {label!r} does not match required format "
            f"'^(buff|n|g|r|sr|ssr|sp)_\\d{{3,4}}$'",
            file=sys.stderr,
        )
        return 1

    # Infer tier from label prefix
    tier = label.split("_")[0]

    # Validate tags
    tags: list[str] = args.tags or []
    for tag in tags:
        if tag not in CANONICAL_TAGS:
            print(
                f"Error: unknown tag {tag!r}. "
                f"Valid tags: {sorted(CANONICAL_TAGS)}",
                file=sys.stderr,
            )
            return 1

    # Load existing registry
    if not labels_path.exists():
        print(f"Error: labels file not found: {labels_path}", file=sys.stderr)
        return 1

    registry = Registry.from_yaml(labels_path)

    # Check for duplicate label
    if label in registry.by_label:
        print(
            f"Error: label {label!r} already exists (id={registry.by_label[label].id})",
            file=sys.stderr,
        )
        return 1

    # Assign next dense id
    new_id = registry.num_classes

    # Build the new entry dict for YAML
    new_entry = {
        "id": new_id,
        "label": label,
        "name": args.name,
        "tier": tier,
        "tags": tags if tags else [],
        "since_version": args.since_version,
    }

    # Read existing YAML and append
    with open(labels_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    data["entries"].append(new_entry)

    # Write back
    with open(labels_path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # Re-validate the updated file
    try:
        updated_registry = Registry.from_yaml(labels_path)
        updated_registry.validate()
    except ValueError as e:
        print(f"Error: validation failed after append: {e}", file=sys.stderr)
        # Rollback: remove the last entry
        data["entries"].pop()
        with open(labels_path, "w", encoding="utf-8") as fh:
            yaml.dump(data, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return 1

    print(f"Added class: id={new_id}, label={label!r}, name={args.name!r}, tier={tier!r}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the pipeline CLI."""
    parser = argparse.ArgumentParser(
        prog="hya.pipeline",
        description="Hyakkiyakou label registry management tools",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # add-class subcommand
    add_parser = subparsers.add_parser(
        "add-class",
        help="Append a new class entry to labels.yaml",
    )
    add_parser.add_argument(
        "--label", required=True, help="Machine-readable label (e.g. ssr_042)"
    )
    add_parser.add_argument(
        "--name", required=True, help="Human-readable display name"
    )
    add_parser.add_argument(
        "--since-version", required=True, help="Version that introduces this class (e.g. v1.2)"
    )
    add_parser.add_argument(
        "--tags", nargs="*", default=[], help="Optional tags from CANONICAL_TAGS"
    )
    add_parser.add_argument(
        "--labels", default=None, help="Path to labels.yaml (default: auto-detect)"
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "add-class":
        return _add_class(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
