import argparse
import json
from copy import deepcopy
from pathlib import Path


def is_plain_object(value):
    return isinstance(value, dict)


def merge_by_template_shape(template_node, source_node):
    if isinstance(template_node, list):
        return deepcopy(source_node) if isinstance(source_node, list) else deepcopy(template_node)

    if is_plain_object(template_node):
        result = {}
        for key, template_value in template_node.items():
            if is_plain_object(source_node) and key in source_node:
                result[key] = merge_by_template_shape(template_value, source_node[key])
            else:
                result[key] = deepcopy(template_value)
        return result

    return deepcopy(source_node) if source_node is not None else deepcopy(template_node)


def generate_configs(config_dir: Path, template_name: str) -> list[Path]:
    template_path = config_dir / template_name
    template = json.loads(template_path.read_text(encoding="utf-8"))
    generated_files = []

    for json_path in sorted(config_dir.glob("*.json")):
        if json_path.name == template_name or json_path.name.endswith("-new.json"):
            continue

        source = json.loads(json_path.read_text(encoding="utf-8"))
        merged = merge_by_template_shape(template, source)
        output_path = json_path.with_name(f"{json_path.stem}-new.json")
        output_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        generated_files.append(output_path)

    return generated_files


def main():
    parser = argparse.ArgumentParser(
        description="Generate *-new.json files by applying source values onto template.json structure."
    )
    parser.add_argument(
        "--config-dir",
        default=Path(__file__).resolve().parents[1] / "config",
        type=Path,
        help="Config directory path.",
    )
    parser.add_argument(
        "--template",
        default="template.json",
        help="Template file name in config directory.",
    )
    args = parser.parse_args()

    generated_files = generate_configs(args.config_dir, args.template)
    for path in generated_files:
        print(path)


if __name__ == "__main__":
    main()
