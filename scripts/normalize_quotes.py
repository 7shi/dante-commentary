"""
Normalize the block-quote pairs in a commentary (e.g. astra/inferno/01.md) to
the canonical layout:

    > 1 Nel mezzo del cammin di nostra vita
    > （私たちの人生の道の半ばで、）
    >
    > 2 mi ritrovai per una selva oscura,
    > （私は、ある暗い森の中にいる自分に気づいた。）

i.e. the original line ends with a two-space hard break, the translation
follows on the next line with no trailing spaces, and pairs are separated by
a single blank quote line.

Lines are classified mechanically: a quote line starting with a number is an
original, one starting with （ ( or ) is a translation, everything else is
left untouched. An original line with no translation on the next line is
reported as a warning and left as-is, since pairing it would be a guess.
"""

import argparse
import re
import sys
from pathlib import Path

CANTICLES = ["inferno", "purgatorio", "paradiso"]

ORIG_RE = re.compile(r"^>\s*(\d+)[.:)]?\s+(.*?)\s*$")
TRANS_RE = re.compile(r"^>\s*[（(](.*)[）)][」』]*\s*$")
BLANK_RE = re.compile(r"^\s*(>\s*)?$")

SEPARATOR = ">"


def normalize_file(path: Path, dry_run: bool) -> bool:
    """Rewrite the quote pairs of one commentary in place. True if changed."""
    lines = path.read_text().splitlines()
    out: list[str] = []
    changed = 0
    i = 0
    while i < len(lines):
        if orig := ORIG_RE.match(lines[i]):
            trans = TRANS_RE.match(lines[i + 1]) if i + 1 < len(lines) else None
            if not trans:
                print(f"{path}:{i + 1}: original line without a translation "
                      f"on the next line, left as-is", file=sys.stderr)
                out.append(lines[i])
                i += 1
                continue
            out.append(f"> {orig.group(1)} {orig.group(2).strip()}  ")
            out.append(f"> （{trans.group(1).strip()}）")
            changed += out[-2] != lines[i] or out[-1] != lines[i + 1]
            i += 2
            # Exactly one blank quote line between this pair and the next one;
            # a gap that runs into prose or ends the file is not ours to touch
            if i < len(lines):
                j = i
                while j < len(lines) and BLANK_RE.match(lines[j]):
                    j += 1
                if j < len(lines) and ORIG_RE.match(lines[j]):
                    out.append(SEPARATOR)
                    changed += lines[i:j] != [SEPARATOR]
                    i = j
            continue
        if TRANS_RE.match(lines[i]) and not (i and ORIG_RE.match(lines[i - 1])):
            print(f"{path}:{i + 1}: translation line without a preceding "
                  f"original line, left as-is", file=sys.stderr)
        out.append(lines[i])
        i += 1

    content = "\n".join(out) + "\n"
    if not changed and content == path.read_text():
        return False
    if not dry_run:
        path.write_text(content)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-d", "--dir", dest="dirs", action="append", type=Path,
                        required=True, metavar="DIR",
                        help="Directory holding <canticle>/<NN>.md files (e.g. astra); "
                             "repeatable, e.g. -d astra -d fable")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Report the changes without writing them back")
    args = parser.parse_args()

    paths = [
        path
        for dir in args.dirs
        for canticle in CANTICLES
        for path in sorted((dir / canticle).glob("*.md"))
    ]
    if not paths:
        parser.error("no <canticle>/*.md files found under the given directories")

    rewritten = 0
    for path in paths:
        if normalize_file(path, args.dry_run):
            print(f"{'Would rewrite' if args.dry_run else 'Rewrote'} {path}")
            rewritten += 1
    print(f"\n{rewritten} file(s) "
          + ("would change" if args.dry_run else "rewritten")
          + f" out of {len(paths)}")


if __name__ == "__main__":
    main()
