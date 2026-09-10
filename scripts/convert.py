"""
One-time migration: rewrite old-format .txt translation files (original and
translation on alternating lines, with line numbers) into the new format
(Japanese translation only, one per source line, blank where untranslated).

Idempotent: a file already in the new format has no line numbers on its odd
lines, so the sequential-numbering check fails and the file is skipped.
"""

import argparse
import sys
from pathlib import Path
from generate import FILLED_RE


def convert_file(path: Path) -> None:
    old_lines = path.read_text().splitlines()
    if len(old_lines) % 2 != 0:
        print(f"{path}: skip: odd number of lines", file=sys.stderr)
        return

    for i in range(0, len(old_lines), 2):
        match = FILLED_RE.match(old_lines[i])
        if not match or int(match.group(1)) != i // 2 + 1:
            print(f"{path}: skip: line {i + 1} lacks the expected sequential number {i // 2 + 1}", file=sys.stderr)
            return

    content = "\n".join(old_lines[i] for i in range(1, len(old_lines), 2)) + "\n"
    path.write_text(content)
    print(f"Converted {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Old-format .txt files to convert")
    args = parser.parse_args()

    for path in args.files:
        convert_file(path)


if __name__ == "__main__":
    main()
