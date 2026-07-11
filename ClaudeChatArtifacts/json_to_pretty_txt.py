#!/usr/bin/env python3
"""
json_to_pretty_txt.py

Convert a JSON file (including Visual-Meta export JSON files, which often
contain nested JSON encoded as strings) into a pretty-printed, human-readable
.txt file.

Usage:
    python3 json_to_pretty_txt.py input.json
    python3 json_to_pretty_txt.py input.json output.txt
    python3 json_to_pretty_txt.py input.json --indent 4

If no output path is given, the script writes a .txt file next to the input,
using the same base name.
"""

import argparse
import json
import sys
from pathlib import Path


def try_parse_nested_json(value):
    """
    Recursively walk the parsed JSON structure. Any string value that itself
    looks like valid JSON (common in Visual-Meta exports, e.g. "CustomJSON")
    gets parsed and expanded, so the final output doesn't contain unreadable
    escaped JSON-within-a-string.
    """
    if isinstance(value, dict):
        return {k: try_parse_nested_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [try_parse_nested_json(v) for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")) and len(stripped) > 1:
            try:
                nested = json.loads(stripped)
                return try_parse_nested_json(nested)
            except json.JSONDecodeError:
                return value
        return value
    return value


def convert(input_path: Path, output_path: Path, indent: int = 2, expand_nested: bool = True):
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if expand_nested:
        data = try_parse_nested_json(data)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Pretty-print a JSON file into a readable .txt file.")
    parser.add_argument("input", type=Path, help="Path to the input .json file")
    parser.add_argument("output", type=Path, nargs="?", default=None,
                         help="Path to the output .txt file (default: same name as input, .txt extension)")
    parser.add_argument("--indent", type=int, default=2, help="Indent width (default: 2)")
    parser.add_argument("--no-expand-nested", action="store_true",
                         help="Don't try to expand JSON strings nested inside string values")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or args.input.with_suffix(".txt")

    try:
        convert(args.input, output_path, indent=args.indent, expand_nested=not args.no_expand_nested)
    except json.JSONDecodeError as e:
        print(f"Error: input file is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote pretty-printed JSON to: {output_path}")


if __name__ == "__main__":
    main()
