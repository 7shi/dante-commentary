"""
Explain a canto of the Divina Commedia in Japanese.
The Italian source (fetched line-by-line from dante_corpus, with line numbers
so the model can cite them) is sent as its own message, followed by the
instructions in PROMPT.
"""

import argparse
import re
import sys
from pathlib import Path
from dante_corpus import ref
from dante_corpus.api import CANTO_SPEC_HELP, check_canto_spec, select_cantos
from llm7shi import Client

CANTICLE_NAMES = {
    "inferno": "地獄篇",
    "purgatorio": "煉獄篇",
    "paradiso": "天国篇",
}

PROMPT = """
添付のダンテ『神曲』{canticle_name}第{number}歌のイタリア語原文を読み、寓意・背景を解説する記事をMarkdownで書いてください。

- 場面・主題ごとに見出しを付け、各見出しの下でその箇所の要点となる範囲を引用してください。
- 引用は行ごとに `> 行番号 原文` の次の行に `> （日本語訳）` を続ける形式にしてください。
- 引用に続けて、その行が示す寓意・背景の解説を地の文で書いてください。
""".strip()

TRANSLATE_PROMPT = """
添付はダンテ『神曲』{canticle_name}第{number}歌の原文と日本語訳を1行ずつ交互に並べたものです。訳が {placeholder} となっている行の日本語訳を補ってください。

- 訳が {placeholder} となっている行だけを対象とし、`行番号 日本語訳` の形式で1行に1つずつ出力してください。
- 既存の訳の文体に合わせ、前後の文脈がつながるように訳してください。
- 出力は補った訳の行だけとしてください。
- 各行には訳文そのものを書いてください。{placeholder} は出力に含めないでください。
""".strip()


PLACEHOLDER = "**NEED TRANSLATE**"

QUOTE_RE = re.compile(r"^>\s*(\d+)\s+(.*?)\s*$")
TRANS_RE = re.compile(r"^>\s*[（(](.*)[）)][」』]*\s*$")
FILLED_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")
MARKER_RE = re.compile(rf"^\**\s*{re.escape(PLACEHOLDER.strip('*'))}\s*\**\s*")
JAPANESE_RE = re.compile(r"[ぁ-んァ-ヶ一-龥]")


def clean_translation(text: str) -> str:
    """Drop the placeholder, which the model sometimes echoes ahead of the
    translation instead of replacing it, with or without its emphasis marks."""
    return MARKER_RE.sub("", text.strip())


def is_translated(trans: str, original: str) -> bool:
    """The model sometimes copies the Italian line instead of translating it."""
    return bool(trans) and trans != original and bool(JAPANESE_RE.search(trans))


def canto_text(lines) -> str:
    return "\n".join(f"{line.no} {line.text}" for line in lines)


def extract_translations(commentary: str, lines) -> dict[int, str]:
    """Collect `> 行番号 原文` / `> （日本語訳）` pairs from a commentary.

    Pairs whose quoted original does not match the corpus line are dropped, so
    that a partial or misquoted line is left untranslated instead of wrong.
    """
    originals = {line.no: line.text for line in lines}
    md_lines = commentary.splitlines()
    translations: dict[int, str] = {}
    for i, md_line in enumerate(md_lines[:-1]):
        if not (quote := QUOTE_RE.match(md_line)):
            continue
        if not (trans := TRANS_RE.match(md_lines[i + 1])):
            continue
        no = int(quote.group(1))
        if originals.get(no) != quote.group(2):
            print(f"skip line {no}: quoted text does not match", file=sys.stderr)
            continue
        translations[no] = trans.group(1)
    return translations


def interleaved_text(lines, translations: dict[int, str], placeholder: str) -> str:
    """Original and translation on alternating lines, sent to the model.

    Untranslated lines carry a placeholder, since the model overlooks blank lines easily.
    """
    return "\n".join(
        f"{line.no} {line.text}\n{translations.get(line.no, placeholder)}"
        for line in lines
    )


def translations_only_text(lines, translations: dict[int, str]) -> str:
    """Japanese translations only, one per source line, blank where untranslated."""
    return "\n".join(translations.get(line.no, "") for line in lines)


def parse_translations_only(saved: str, lines) -> dict[int, str]:
    """Read back a saved translations-only file, keeping the lines already translated."""
    translations: dict[int, str] = {}
    for line, text_line in zip(lines, saved.splitlines()):
        trans = clean_translation(text_line)
        if is_translated(trans, line.text):
            translations[line.no] = trans
    return translations


def parse_filled(filled: str, missing: set[int], lines) -> dict[int, str]:
    """Collect `行番号 日本語訳` lines, keeping only the requested line numbers."""
    originals = {line.no: line.text for line in lines}
    translations: dict[int, str] = {}
    for text_line in filled.splitlines():
        if match := FILLED_RE.match(text_line):
            no, trans = int(match.group(1)), clean_translation(match.group(2))
            if no in missing and is_translated(trans, originals.get(no, "")):
                translations[no] = trans
    return translations


def generate(canticle: str, canto: int, args: argparse.Namespace) -> None:
    lines = ref(f"{canticle} {canto}")
    text = canto_text(lines)
    canticle_name = CANTICLE_NAMES.get(canticle, canticle)

    out_dir = args.dir / canticle
    out_path = out_dir / f"{canto:02d}.md"
    trans_path = out_dir / f"{canto:02d}.txt"
    client = Client(
        model=args.model,
        include_thoughts=not args.no_think,
        show_params=False,
        keep_history=False,
    )

    if trans_path.exists():
        # Resume: the saved file already holds every translation extracted so far.
        print(f"Resuming from {trans_path}")
        translations = parse_translations_only(trans_path.read_text(), lines)
    else:
        if out_path.exists():
            print(f"Skipped (already exists): {out_path}")
            commentary = out_path.read_text()
        else:
            prompt = PROMPT.format(canticle_name=canticle_name, number=canto)
            commentary = client([text, prompt]).text
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(commentary)
            print(f"\nSaved to {out_path}")
        translations = extract_translations(commentary, lines)

    saved = trans_path.read_text() if trans_path.exists() else ""

    def save():
        # Saved every round, so an interrupted run can resume where it left off.
        nonlocal saved
        content = translations_only_text(lines, translations) + "\n"
        if content != saved:
            out_dir.mkdir(parents=True, exist_ok=True)
            trans_path.write_text(content)
            saved = content
            print(f"\nSaved to {trans_path}")

    prompt = TRANSLATE_PROMPT.format(
        canticle_name=canticle_name, number=canto, placeholder=PLACEHOLDER
    )
    for round_no in range(1, args.rounds + 1):
        missing = {line.no for line in lines if line.no not in translations}
        if not missing:
            break
        print(f"\n--- round {round_no}: {len(missing)} lines left ---")
        filled = client(
            [interleaved_text(lines, translations, PLACEHOLDER), prompt]
        ).text
        if not (added := parse_filled(filled, missing, lines)):
            print("\nno progress, giving up", file=sys.stderr)
            break
        translations |= added
        save()
    save()  # in case the loop ended before any round wrote the file
    if remaining := sorted(line.no for line in lines if line.no not in translations):
        print(f"\nstill untranslated: {remaining}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "canticle",
        help="Canticle name: inferno, purgatorio, or paradiso",
    )
    parser.add_argument(
        "-c", "--canto",
        metavar="SPEC",
        help=CANTO_SPEC_HELP,
    )
    parser.add_argument(
        "-m", "--model",
        default="ollama:gemma4:26b-a4b-it-qat",
        help="Model name with optional vendor prefix (e.g. openai:gpt-4.1-mini)",
    )
    parser.add_argument(
        "-r", "--rounds",
        type=int,
        default=5,
        help="Max translation passes to fill remaining lines (default: 5)",
    )
    parser.add_argument(
        "--no-think",
        action="store_true",
        help="Disable thinking output (include_thoughts=False)",
    )
    parser.add_argument(
        "-d", "--dir",
        type=Path,
        required=True,
        help="Output directory holding <canticle>/<NN>.md",
    )
    args = parser.parse_args()

    if err := check_canto_spec([args.canticle], args.canto):
        parser.error(err)

    for canto in select_cantos(args.canticle, args.canto):
        generate(args.canticle, canto, args)


if __name__ == "__main__":
    main()
