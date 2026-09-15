"""
Rebuild the block-quote pairs in a commentary (e.g. astra/inferno/01.md) from
the sources of truth, instead of trusting whatever text already sits in the
quote block:

    > 1 Nel mezzo del cammin di nostra vita
    > （私たちの人生の道の半ばで、）

The original comes from dante_corpus, the translation from the sibling
<canticle>/<NN>.txt file (same line numbering, one verse per physical line).
A file whose sibling .txt is missing is skipped entirely and reported once.

For each quote block (a maximal run of lines starting with ">") in a file
that has a sibling .txt:

1. Flatten the block to a string.
2. If it opens with `> <line-number> ...`, find the lowest and highest
   quoted line numbers.
3. Rebuild every numbered pair from dante_corpus and the .txt file, in the
   canonical layout (original line ends with a two-space hard break,
   translation follows with no trailing spaces). Anything else in the
   block — separators, gaps where lines are skipped, unnumbered lines — is
   left untouched.
4. Compare the rebuilt block against the original string; rewrite the file
   only if something differs.
5. Report, per file, whether it was rewritten.

A pair whose translation line is missing, or a line number out of range for
the source text, is left as-is and reported as a warning.

--format-only switches to the previous, source-independent behavior: it
only normalizes the layout of pairs already in the file (hard-break spaces,
paren style, separator lines) without consulting dante_corpus or any .txt
file. The two modes are never mixed automatically; pick one via the flag.
"""

import argparse
import re
import sys
from pathlib import Path

from dante_corpus.api import canto

CANTICLES = ["inferno", "purgatorio", "paradiso"]

ORIG_RE = re.compile(r"^>\s*(\d+)[.:)]?\s+(.*?)\s*$")
TRANS_RE = re.compile(r"^>\s*[（(](.*)[）)][」』]*\s*$")
BLANK_RE = re.compile(r"^\s*(>\s*)?$")
PATH_RE = re.compile(r"(?:^|/)(inferno|purgatorio|paradiso)/(\d+)\.md$")

SEPARATOR = ">"


def find_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """[start, end) index ranges of maximal runs of lines starting with '>'."""
    blocks = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith(">"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                j += 1
            blocks.append((i, j))
            i = j
        else:
            i += 1
    return blocks


# --- Reconstruct from dante_corpus + the sibling .txt (default mode) ---

def rebuild_block(path: Path, canticle: str, number: int,
                   translations: list[str], block: list[str]) -> list[str] | None:
    """Rebuild one quote block from dante_corpus + the sibling .txt.

    Returns None if the block doesn't open with a numbered original line."""
    if not ORIG_RE.match(block[0]):
        return None

    numbers = [int(mm.group(1)) for line in block if (mm := ORIG_RE.match(line))]
    start, end = min(numbers), max(numbers)
    try:
        originals = {line.no: line.text for line in canto(canticle, number).lines(start, end)}
    except ValueError as e:
        print(f"{path}: {e}, block left as-is", file=sys.stderr)
        return None

    out: list[str] = []
    i = 0
    while i < len(block):
        orig = ORIG_RE.match(block[i])
        if not orig:
            out.append(block[i])
            i += 1
            continue
        n = int(orig.group(1))
        trans = TRANS_RE.match(block[i + 1]) if i + 1 < len(block) else None
        if not trans:
            print(f"{path}: line {n} has no translation on the next line, "
                  f"left as-is", file=sys.stderr)
            out.append(block[i])
            i += 1
            continue
        if n not in originals or not (1 <= n <= len(translations)):
            print(f"{path}: line {n} out of range for the source text, "
                  f"left as-is", file=sys.stderr)
            out.append(block[i])
            out.append(block[i + 1])
            i += 2
            continue
        out.append(f"> {n} {originals[n]}  ")
        out.append(f"> （{translations[n - 1]}）")
        i += 2
    return out


def normalize_file_reconstruct(path: Path, dry_run: bool) -> bool:
    """Rewrite the quote blocks of one commentary from dante_corpus + its
    sibling .txt. True if changed; False (with a warning) if the file has no
    sibling .txt or its canticle/canto can't be resolved from its path."""
    m = PATH_RE.search(path.as_posix())
    if not m:
        print(f"{path}: can't resolve canticle/canto from path, file left as-is",
              file=sys.stderr)
        return False
    canticle, number = m.group(1), int(m.group(2))

    txt_path = path.with_suffix(".txt")
    if not txt_path.exists():
        print(f"{path}: no sibling {txt_path.name}, file left as-is "
              f"(use --format-only to normalize layout without it)", file=sys.stderr)
        return False
    translations = txt_path.read_text(encoding="utf-8").splitlines()

    lines = path.read_text().splitlines()
    out = list(lines)
    changed = False
    for start, end in find_blocks(lines):
        block = lines[start:end]
        rebuilt = rebuild_block(path, canticle, number, translations, block)
        if rebuilt is not None and rebuilt != block:
            out[start:end] = rebuilt
            changed = True

    if not changed:
        return False
    if not dry_run:
        path.write_text("\n".join(out) + "\n")
    return True


# --- Normalize the layout of pairs already in the file (--format-only) ---

def normalize_file_format_only(path: Path, dry_run: bool) -> bool:
    """Rewrite the quote pairs of one commentary in place, using only the
    text already in the file. True if changed."""
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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("-d", "--dir", dest="dirs", action="append", type=Path,
                        required=True, metavar="DIR",
                        help="Directory holding <canticle>/<NN>.md files (e.g. astra); "
                             "repeatable, e.g. -d astra -d fable")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Report the changes without writing them back")
    parser.add_argument("-f", "--format-only", action="store_true",
                        help="Only normalize the layout of pairs already in the file "
                             "(no dante_corpus/.txt lookup, no automatic fallback)")
    args = parser.parse_args()

    paths = [
        path
        for dir in args.dirs
        for canticle in CANTICLES
        for path in sorted((dir / canticle).glob("*.md"))
    ]
    if not paths:
        parser.error("no <canticle>/*.md files found under the given directories")

    normalize_file = normalize_file_format_only if args.format_only else normalize_file_reconstruct

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
