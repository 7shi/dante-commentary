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

"結び" (conclusion) sections are the exception: they are not tied to a
specific quoted passage, so 0 quote blocks is expected there. They are
reported only when their quote-block count is 1 or more.
"""

import argparse
import re
import sys
from pathlib import Path
from dante_corpus.api import CANTO_SPEC_HELP, check_canto_spec, select_cantos

CANTICLES = ["inferno", "purgatorio", "paradiso"]

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
        is_conclusion = m.group(1).startswith("結び")
        if is_conclusion:
            if count != 0:
                offenders.append((m.group(1), count))
        elif count != 1:
            offenders.append((m.group(1), count))
    return offenders


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("canticles", nargs="+", choices=CANTICLES, metavar="canticle",
                        help="Canticle(s) to process: inferno, purgatorio, or paradiso")
    parser.add_argument("-d", "--dir", type=Path, required=True,
                        help="Directory holding <canticle>/<NN>.md files (e.g. astra)")
    parser.add_argument("-c", "--canto", help=CANTO_SPEC_HELP)
    args = parser.parse_args()

    if err := check_canto_spec(args.canticles, args.canto):
        parser.error(err)

    targets: list[Path] = []
    for canticle in args.canticles:
        for canto in select_cantos(canticle, args.canto):
            path = args.dir / canticle / f"{canto:02d}.md"
            if path.exists():
                targets.append(path)
    if not targets:
        parser.error("no <canticle>/<NN>.md files found under the given directory")

    status = 0
    for path in targets:
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
