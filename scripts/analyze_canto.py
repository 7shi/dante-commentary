"""Analyze sections, quotes, and line ranges for commentary files.

Inspects <canticle>/<NN>.md files, maps Italian quotes to line numbers in
dante_corpus, and prints section breakdown to help verify line alignment.
"""

import argparse
import re
import sys
from pathlib import Path
from dante_corpus import ref
from dante_corpus.api import CANTO_SPEC_HELP, check_canto_spec, select_cantos

CANTICLE_NAMES = {
    "inferno": "地獄篇",
    "purgatorio": "煉獄篇",
    "paradiso": "天国篇",
}

CANTICLES = list(CANTICLE_NAMES)


def analyze_canto(canticle: str, canto: int, path: Path) -> None:
    corpus_lines = ref(f"{canticle} {canto}")
    total_lines = len(corpus_lines)

    # Map normalized line to line number
    norm_to_no = {}
    for l in corpus_lines:
        norm = re.sub(r"[^\w\s]", "", l.text.lower())
        norm = re.sub(r"\s+", " ", norm).strip()
        norm_to_no[norm] = l.no

    text = path.read_text(encoding="utf-8")

    # Split into sections
    sections = re.split(r"\n(?=## )", text)

    canticle_ja = CANTICLE_NAMES.get(canticle, canticle)
    print(f"=== {canticle_ja}第{canto}歌 ({canticle} {canto}) (Total lines: {total_lines}) ===")

    sec_info = []
    for s in sections:
        lines = s.strip().split("\n")
        heading = lines[0]
        if heading.startswith("## 結び"):
            continue

        # Find Italian quotes: block starting with > containing Italian
        quoted_nos = []
        for line in lines:
            if line.startswith("> "):
                q_text = line[2:].strip()
                norm = re.sub(r"[^\w\s]", "", q_text.lower())
                norm = re.sub(r"\s+", " ", norm).strip()
                if norm in norm_to_no:
                    quoted_nos.append(norm_to_no[norm])
                else:
                    # substring match
                    for k, v in norm_to_no.items():
                        if len(norm) > 10 and (norm in k or k in norm):
                            quoted_nos.append(v)
                            break

        # summary of section
        first_few_lines = [l for l in lines[1:10] if l and not l.startswith(">")]
        sec_info.append({
            "heading": heading,
            "quotes": sorted(list(set(quoted_nos))),
            "sample": first_few_lines[:2] if first_few_lines else [],
        })

    for i, s in enumerate(sec_info):
        q_str = f"{min(s['quotes'])}～{max(s['quotes'])}" if s['quotes'] else "None"
        all_q = f"[{','.join(str(x) for x in s['quotes'])}]" if s['quotes'] else "[]"
        print(f"Sec {i+1}: {s['heading']}")
        print(f"   Quotes: {q_str} {all_q}")
        if s['sample']:
            print(f"   Sample: {s['sample'][0][:80]}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("canticles", nargs="+", choices=CANTICLES, metavar="canticle",
                        help="Canticle(s) to process: inferno, purgatorio, or paradiso")
    parser.add_argument("-d", "--dir", type=Path, required=True,
                        help="Directory holding <canticle>/<NN>.md files (e.g. astra)")
    parser.add_argument("-c", "--canto", help=CANTO_SPEC_HELP)
    args = parser.parse_args()

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

    for canticle, canto, path in targets:
        analyze_canto(canticle, canto, path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
