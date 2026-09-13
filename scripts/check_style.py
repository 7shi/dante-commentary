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
    parser.add_argument("files", nargs="+", type=Path, help="Markdown files to check")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Ratio at or above which a file is judged です・ます調 (default: 0.5)")
    args = parser.parse_args()

    status = 0
    for path in args.files:
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
