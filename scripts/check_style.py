"""
Judge whether a commentary's prose is written in です・ます調 (polite) or
だ・である調 (plain), based on the share of sentences ("。" terminated) that
end in a polite form such as です。 or ます。

Markdown block-quote lines (starting with ">") are excluded before counting:
a commentary like astra/inferno/01.md quotes the Italian original and its
translation inside "> ..." lines, and those follow the source/translation's
own phrasing, not the commentary author's prose style.
"""

import argparse
import re
import sys
from pathlib import Path
from dante_corpus.api import CANTO_SPEC_HELP, check_canto_spec, select_cantos

CANTICLES = ["inferno", "purgatorio", "paradiso"]

POLITE_RE = re.compile(r"(です|ます|ました|でした|ましょう|ませんでした|ません|でしょう)。")
SENTENCE_END_RE = re.compile(r"。")


def strip_quotes(text: str) -> str:
    """Drop Markdown block-quote lines, which are not the author's own prose."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))


def judge_style(text: str) -> tuple[int, int, float]:
    """Return (polite sentence count, total sentence count, ratio)."""
    body = strip_quotes(text)
    total = len(SENTENCE_END_RE.findall(body))
    polite = len(POLITE_RE.findall(body))
    ratio = polite / total if total else 0.0
    return polite, total, ratio


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("canticles", nargs="+", choices=CANTICLES, metavar="canticle",
                        help="Canticle(s) to process: inferno, purgatorio, or paradiso")
    parser.add_argument("-d", "--dir", type=Path, required=True,
                        help="Directory holding <canticle>/<NN>.md files (e.g. astra)")
    parser.add_argument("-c", "--canto", help=CANTO_SPEC_HELP)
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Ratio at or above which a file is judged です・ます調 (default: 0.5)")
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
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"{path}: {e}", file=sys.stderr)
            status = 1
            continue

        polite, total, ratio = judge_style(text)
        if total == 0:
            style = "判定不可（文末なし）"
        elif ratio >= args.threshold:
            style = "です・ます調"
        else:
            style = "だ・である調"
        print(f"{path}: {style} (です・ます比率 {polite}/{total} = {ratio:.1%})")

    return status


if __name__ == "__main__":
    sys.exit(main())
