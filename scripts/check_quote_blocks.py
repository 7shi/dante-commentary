"""
Check that every "##" section in a commentary file contains exactly one
Markdown block-quote block.

A commentary file is structured as:

    # <title>

    <intro paragraph(s)>

    ## <section title>

    > <quote line>
    > ...

    <commentary paragraph(s)>

A "quote block" is a maximal run of consecutive lines starting with ">".
Two such runs separated by a non-quote line (even a blank one) count as two
blocks. Sections whose quote-block count is not exactly 1 (i.e. 0 or 2+)
are reported, since the intended structure is one quote block per section.
"""

import argparse
import re
import sys
from pathlib import Path

SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def count_quote_blocks(section_body: str) -> int:
    """Count maximal runs of consecutive lines starting with '>'."""
    blocks = 0
    in_block = False
    for line in section_body.splitlines():
        if line.lstrip().startswith(">"):
            if not in_block:
                blocks += 1
                in_block = True
        else:
            in_block = False
    return blocks


def check_file(path: Path) -> list[tuple[str, int]]:
    """Return [(section title, quote block count), ...] for offending sections."""
    text = path.read_text(encoding="utf-8")
    headers = list(SECTION_RE.finditer(text))
    offenders = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end]
        count = count_quote_blocks(body)
        if count != 1:
            offenders.append((m.group(1), count))
    return offenders


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("files", nargs="+", type=Path, help="Markdown files to check")
    args = parser.parse_args()

    status = 0
    for path in args.files:
        try:
            offenders = check_file(path)
        except OSError as e:
            print(f"{path}: {e}", file=sys.stderr)
            status = 1
            continue

        if offenders:
            status = 1
            for title, count in offenders:
                print(f"{path}: 引用ブロック数 {count} - ## {title}")
        else:
            print(f"{path}: OK")

    return status


if __name__ == "__main__":
    sys.exit(main())
