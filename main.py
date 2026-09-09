"""
Explain a canto of the Divina Commedia in Japanese (default: Inferno Canto 1).
The Italian source (fetched line-by-line from dante_corpus, with line numbers
so the model can cite them) is sent as its own message, followed by the
instructions in PROMPT.
"""

import argparse
from pathlib import Path
from dante_corpus import ref
from llm7shi import Client

DEFAULT_OUT_DIR = Path(__file__).parent / "test"

PROMPT = """
添付のダンテ『神曲』地獄篇第1歌のイタリア語原文を読み、寓意・背景を解説する記事をMarkdownで書いてください。

- 場面・主題ごとに見出しを付け、各見出しの下でその箇所の要点となる範囲を引用してください。
- 引用は行ごとに `> 行番号 原文` の次の行に `> （日本語訳）` を続ける形式にしてください。
- 引用に続けて、その行が示す寓意・背景の解説を地の文で書いてください。
""".strip()


def canto_text(canticle: str, number: int) -> str:
    lines = ref(f"{canticle} {number}")
    return "\n".join(f"{line.no} {line.text}" for line in lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "canticle",
        nargs="?",
        default="inferno",
        help="Canticle name: inferno, purgatorio, or paradiso (default: inferno)",
    )
    parser.add_argument(
        "-c", "--canto",
        type=int,
        default=1,
        help="Canto number (default: 1)",
    )
    parser.add_argument(
        "-m", "--model",
        default="ollama:gemma4:26b-a4b-it-qat",
        help="Model name with optional vendor prefix (e.g. openai:gpt-4.1-mini)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory for 01.md (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args()

    text = canto_text(args.canticle, args.canto)
    client = Client(model=args.model, show_params=False, keep_history=False)
    result = client([text, PROMPT])

    out_path = args.out_dir / args.canticle / f"{args.canto:02d}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.text)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
