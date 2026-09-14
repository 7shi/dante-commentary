"""Append a closing 結び section to an existing commentary that lacks one.

generate.py's PROMPT now asks for a closing "## 結び――..." section, but
commentaries written before that change have none. This script fills the gap
for those older files: the whole existing commentary is sent to the model as
context, and the response - a single 結び section - is appended to the file.

A file whose commentary already has a "## 結び" or "## おわりに" heading is
left untouched, so the script can be re-run safely over a whole canticle.
"""

import argparse
import re
import sys
from pathlib import Path
from dante_corpus.api import CANTO_SPEC_HELP, check_canto_spec, select_cantos
from llm7shi import Client

CANTICLE_NAMES = {
    "inferno": "地獄篇",
    "purgatorio": "煉獄篇",
    "paradiso": "天国篇",
}

CANTICLES = list(CANTICLE_NAMES)

CLOSING_RE = re.compile(r"^## (結び|おわりに)", re.MULTILINE)

PROMPT = """
添付はダンテ『神曲』{canticle_name}第{number}歌の寓意・背景を解説した記事です。この記事の末尾に置く結びのセクションを書いてください。

- 「## 結び――〈内容を要約した見出し〉」という見出しで始めてください。
- 記事全体を踏まえて、この歌が示す意味を短くまとめてください。
- 「です・ます調」で統一してください。
- 出力は見出しと本文のみとし、他の説明は含めないでください。
""".strip()


def generate_conclusion(client: Client, canticle: str, canto: int, commentary: str) -> str:
    prompt = PROMPT.format(canticle_name=CANTICLE_NAMES[canticle], number=canto)
    return client([commentary, prompt]).text.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("canticles", nargs="+", choices=CANTICLES, metavar="canticle",
                        help="Canticle(s) to process: inferno, purgatorio, or paradiso")
    parser.add_argument("-d", "--dir", type=Path, required=True,
                        help="Directory holding <canticle>/<NN>.md files (e.g. astra)")
    parser.add_argument("-m", "--model",
                        help="Model name with optional vendor prefix (e.g. openai:gpt-4.1-mini). "
                             "Required unless --dry-run")
    parser.add_argument("-c", "--canto", help=CANTO_SPEC_HELP)
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Report which files would be changed, without calling the model "
                             "or writing anything")
    args = parser.parse_args()

    if not args.dry_run and not args.model:
        parser.error("-m/--model is required unless --dry-run is given")
    if err := check_canto_spec(args.canticles, args.canto):
        parser.error(err)

    targets: list[tuple[str, int, Path]] = []
    for canticle in args.canticles:
        for canto in select_cantos(canticle, args.canto):
            path = args.dir / canticle / f"{canto:02d}.md"
            if path.exists():
                targets.append((canticle, canto, path))
    if not targets:
        parser.error("no <canticle>/<NN>.md files found under the given directory")

    client = None if args.dry_run else Client(model=args.model, show_params=False, keep_history=False)

    added = skipped = 0
    for canticle, canto, path in targets:
        commentary = path.read_text()
        if CLOSING_RE.search(commentary):
            skipped += 1
            continue

        if args.dry_run:
            print(f"{path}: would generate 結び")
            added += 1
            continue

        print(f"{path}: generating 結び")
        conclusion = generate_conclusion(client, canticle, canto, commentary)
        if not conclusion.startswith("## "):
            print(f"  unexpected response, skipping:\n{conclusion}", file=sys.stderr)
            continue

        path.write_text(commentary.rstrip("\n") + "\n\n" + conclusion + "\n")
        added += 1

    print(f"\nAdded {added} 結び section(s), skipped {skipped} already-closed file(s)"
          + (" (dry run, nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    exit(main())
