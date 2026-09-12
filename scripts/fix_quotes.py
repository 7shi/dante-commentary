"""Restore the quotation marks of a line-by-line translation, segment by segment.

generate.py asks for one translation line per source line, so nothing carries
the state of a speech across a line break: a speech running over a dozen lines
gets closed early and reopened, or never closed at all. The Italian source
marks every speech with « », “ ” and ‘ ’, so the structure is already there -
but it cannot be transposed mechanically, because Japanese word order decides
where in a line 「 belongs, and a translation may legitimately merge or shift a
boundary that the source draws inside a line.

This script does not re-translate: it hands the model one segment of the source
alongside its existing translation and asks for the same translation back with
its quotation marks corrected. The record is rewritten in place in the
translation file chosen by -d/--dir and the canticle/canto arguments (e.g.
astra/inferno/01.txt), which holds one Japanese line per source line, blank
where untranslated, with no line numbers of its own - those come from the
source via dante_corpus.

Segments come from segments/<canticle>.jsonl. A segment can begin or end in
the middle of a speech - the source's quotes balance within a canto, not
within every segment - so the prompt says to leave a speech the source does
not open or close alone.

A segment that already matches the source's structure is skipped without
calling the model - sending it in would only risk the model introducing a
mark that breaks the match. --check runs that same structural test on its
own, without calling the model or writing anything.

A segment whose translation still holds one of the source's own literal
marks (« » “ ” ‘ ’) usually was never actually translated - the Italian
leaked through verbatim - rather than suffering a quote-style slip. Such a
segment is skipped rather than "corrected", since fixing only its quote
marks would leave the untranslated text in place while erasing the one
signal that it needs to be redone by hand; --check keeps flagging it.
"""

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from dante_corpus import QuoteSpan, canto as get_canto, ref
from llm7shi import Client

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CANTICLES = ["inferno", "purgatorio", "paradiso"]

SEGMENT_DIR = os.path.join(PROJECT_DIR, "segments")

INSTRUCTIONS = """The text above is an existing Japanese translation of the numbered source lines, one line per source line. Its quotation marks are unreliable: the translation was made one line at a time, so a speech spanning several lines may be closed early, reopened in the middle, or never closed.

Your task is to correct the quotation marks and output every line again, prefixed with its source line number, one output line per source line, in order.

The source's « », “ ” and ‘ ’ are the authority for where a speech begins and ends. Map them by nesting level, outermost first:

- « » -> 「」
- “ ” inside it -> 『』
- ‘ ’ inside that -> 「」 again

Every speech the source opens must be opened in the translation, and every speech it closes must be closed.

A speech the source keeps open across several lines must run unbroken in the translation too. Where the translation closes it partway and opens it again, both marks go - the early closing one and the one that restarts the speech - so that it reads as one speech. Removing only one of the two leaves the rest of the segment unbalanced.

The translation also sets a phrase in 「」 of its own accord now and then - for emphasis, or around a name or a title that the source leaves unmarked. Those marks open and close within one line and answer to nothing in the source: take them out. Never take out a mark that belongs to a speech the source does mark.

Where the source opens or closes in the middle of a line, put the Japanese mark where the translation's own word order calls for it, which is not always the same place.

Constraints:
- A segment may begin or end in the middle of a speech, which the source shows by closing a speech it never opened, or opening one it never closes. Leave it that way: never add an opening or a closing mark the source does not have.
- Change nothing but the quotation marks. Reproduce every other character exactly - wording, punctuation, spelling and names - including anything you judge to be a mistranslation or an awkward phrase. Correcting it is out of scope here.
- Keep one output line per source line. Never merge, split or drop a line.
- Output the numbered lines only. No commentary, no headings, no blank lines."""

LINE_RE = re.compile(r"^\s*(\d+)[.:)]?\s+(.*)$")

# Everything the model is allowed to touch, in the source and in the translation
QUOTE_CHARS = "«»“”‘’「」『』\"'"

QUOTES = str.maketrans({c: None for c in QUOTE_CHARS})

# The source's own literal marks - never legitimate in Japanese text, so a
# leftover one almost always means the segment was never actually
# translated (the Italian leaked through verbatim), not a quote-style slip
FOREIGN_CHARS = "«»“”‘’"


def normalize(text: str) -> str:
    """The text with everything the model is allowed to change taken out."""
    return re.sub(r"\s+", "", text).translate(QUOTES)


def has_quotes(text: str) -> bool:
    return any(c in QUOTE_CHARS for c in text)


def foreign_marks(lines: List[str]) -> str:
    """The lines' quote marks still in the source's own literal style."""
    return "".join(sorted({c for line in lines for c in line if c in FOREIGN_CHARS}))


def flatten(spans: Tuple[QuoteSpan, ...]) -> List[QuoteSpan]:
    out = []
    for span in spans:
        out.append(span)
        out.extend(flatten(span.children))
    return out


def crossing(spans: List[QuoteSpan], start: int, end: int) -> Tuple[int, int]:
    """Speeches the segment closes but does not open, and opens but does not close."""
    closes = sum(1 for s in spans if s.start_line < start <= s.end_line <= end)
    opens = sum(1 for s in spans if start <= s.start_line <= end < s.end_line)
    return closes, opens


def unmatched(lines: List[str]) -> Tuple[int, int]:
    """Marks the lines close without opening, and open without closing."""
    opens = closes = 0
    for line in lines:
        for c in line:
            if c in "「『":
                opens += 1
            elif c in "」』":
                if opens:
                    opens -= 1
                else:
                    closes += 1
    return closes, opens


def number_lines(numbers: List[int], texts: List[str]) -> str:
    return "\n".join(f"{no} {text}" for no, text in zip(numbers, texts))


def parse_numbered(text: str) -> Tuple[List[int], List[str]]:
    numbers, texts = [], []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        if m := LINE_RE.match(line):
            numbers.append(int(m.group(1)))
            texts.append(m.group(2).strip())
        else:
            numbers.append(0)
            texts.append(line.strip())
    return numbers, texts


def fix_segment(
    client: Client,
    numbers: List[int],
    source_lines: List[str],
    translation_lines: List[str],
) -> str:
    messages = [
        f"[Source text in Italian, one numbered line per line]\n"
        f"{number_lines(numbers, source_lines)}",
        f"[Existing Japanese translation of the text above]\n"
        f"{number_lines(numbers, translation_lines)}",
        INSTRUCTIONS,
    ]
    return client(messages).text.strip()


def check(numbers: List[int], translation_lines: List[str], response: str,
          want: Tuple[int, int]) -> Tuple[List[str], float]:
    got_numbers, texts = parse_numbered(response)
    problems = []

    if got_numbers != numbers:
        if len(got_numbers) != len(numbers):
            problems.append(f"line count {len(got_numbers)} != {len(numbers)}")
        else:
            problems.append("line numbers do not match the source")

    # The source says how many speeches the segment leaves open or closes on
    # its own; anything else means a speech was left unopened or unclosed
    got = unmatched(texts)
    if got != want:
        problems.append(f"unmatched marks {got} != {want} (closes, opens)")

    # A mark left in the source's own literal style, e.g. a leftover «»
    if foreign := foreign_marks(texts):
        problems.append(f"leftover {foreign} not converted to Japanese's quotation marks")

    before, after = normalize("\n".join(translation_lines)), normalize("\n".join(texts))
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    drift = 0.0 if before == after else 1.0 - matcher.ratio()
    if drift:
        problems.append("text changed apart from the quotation marks")

    return problems, drift


def load_segments(canticle: str) -> Dict[int, List[Dict]]:
    path = os.path.join(SEGMENT_DIR, f"{canticle}.jsonl")
    with open(path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    return {r["canto"]: r["boundaries"] for r in records}


def load_translations(path: str) -> List[str]:
    """One Japanese line per source line, blank where untranslated."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def save_translations(path: str, translation_lines: List[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(translation_lines) + "\n")


def parse_segment_arg(value: str) -> List[int]:
    try:
        return [int(item) for item in value.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected a segment number or a comma-separated list, e.g. 3 or 1,3"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore the quotation marks of an existing translation"
    )
    parser.add_argument("canticles", nargs="+", choices=CANTICLES, metavar="canticle",
                        help="Canticle(s) to process: inferno, purgatorio, or paradiso")
    parser.add_argument("-d", "--dir", type=Path, required=True,
                        help="Directory holding <canticle>/<NN>.txt files (e.g. astra)")
    parser.add_argument("-m", "--model",
                        help="LLM model to use (e.g. openai:gpt-6-astra). Required unless --check")
    parser.add_argument("-c", "--canto", type=int,
                        help="Canto number to process (default: every canto under the directory)")
    parser.add_argument("-s", "--segment", type=parse_segment_arg,
                        help="Process only these segments of each canto, comma separated "
                             "(e.g. 3 or 1,3). Without it, every segment is processed")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Report the changes without writing them back")
    parser.add_argument("--check", action="store_true",
                        help="Report which segments' quotation marks already mismatch what "
                             "the source's structure calls for, without calling the model or "
                             "writing anything - use it to locate a problem left over from a "
                             "previous run whose output has scrolled away")

    args = parser.parse_args()
    if not args.check and not args.model:
        parser.error("-m/--model is required unless --check is given")

    # Segments are independent, so no turn is carried over into the next
    client = None if args.check else Client(model=args.model, show_params=False, keep_history=False)

    targets: List[Tuple[str, int, Path]] = []
    for canticle in args.canticles:
        pattern = f"{args.canto:02d}.txt" if args.canto is not None else "*.txt"
        for path in sorted((args.dir / canticle).glob(pattern)):
            targets.append((canticle, int(path.stem), path))
    if not targets:
        parser.error("no <canticle>/<NN>.txt files found under the given directories")

    violations: List[Tuple[str, List[str], float]] = []
    changed = processed = 0

    for canticle, canto, path in targets:
        try:
            boundaries = load_segments(canticle)[canto]
            source = {line.no: line.text for line in ref(f"{canticle} {canto}")}
            spans = flatten(get_canto(canticle, canto).quotes())
            translations = load_translations(path)
        except (OSError, ValueError, KeyError) as e:
            print(f"{path}: {e}", file=sys.stderr)
            return 1

        numbers = sorted(source)
        if len(translations) != len(numbers):
            print(f"{path}: line count does not match {canticle} {canto} "
                  f"({len(translations)} lines, source has {len(numbers)})", file=sys.stderr)
            return 1

        source_lines = [source[no] for no in numbers]
        index = {no: i for i, no in enumerate(numbers)}

        for segment, b in enumerate(boundaries, 1):
            if args.segment and segment not in args.segment:
                continue

            first, last = index[b["start_line"]], index[b["end_line"]]
            part = slice(first, last + 1)

            # A segment without a quotation mark on either side has nothing to fix
            if not has_quotes("".join(source_lines[part] + translations[part])):
                continue
            label = f"{canticle} {canto:2d}:{segment}"
            want = crossing(spans, b["start_line"], b["end_line"])

            # Same structural checks fix_segment's response is held to below,
            # run directly on the translation as it stands on disk
            got = unmatched(translations[part])
            foreign = foreign_marks(translations[part])
            already_ok = got == want and not foreign

            if args.check:
                if not already_ok:
                    problems = []
                    if got != want:
                        problems.append(f"unmatched marks {got} != {want} (closes, opens)")
                    if foreign:
                        problems.append(f"leftover {foreign} not converted to Japanese's quotation marks")
                    violations.append((label, problems, 0.0))
                    print(f"{label} (lines {b['start_line']}-{b['end_line']}): {', '.join(problems)}")
                continue

            # Already matches the source's structure - sending it to the model
            # would only risk it introducing a mark that breaks that match
            if already_ok:
                continue

            # A leftover literal source mark usually means the segment was
            # never actually translated, not a quote-style slip - skip it
            # entirely rather than have fix_segment "correct" the quotes on
            # text that is still Italian. --check keeps flagging it until it
            # is redone by hand
            if foreign:
                print(f"{label} (lines {b['start_line']}-{b['end_line']}): leftover {foreign} - "
                      f"likely untranslated, skipping")
                continue

            print(f"\n{label} -> fixing quotation marks "
                  f"(lines {b['start_line']}-{b['end_line']})")

            response = fix_segment(
                client, numbers[part], source_lines[part], translations[part],
            )

            problems, drift = check(numbers[part], translations[part], response, want)
            if problems:
                violations.append((label, problems, drift))
                print(f"  violation: {', '.join(problems)}")
                print("  left unchanged")
                continue
            print(f"  drift: {drift * 100:.1f}%")

            _, texts = parse_numbered(response)
            changed += sum(a != b for a, b in zip(translations[part], texts))
            translations[part] = texts
            processed += 1

            if not args.dry_run:
                save_translations(path, translations)

    if args.check:
        print(f"\n{len(violations)} segment(s) already mismatch the source's structure")
    else:
        print(f"\nProcessed {processed} segments, {changed} lines changed"
              + (" (dry run, nothing written)" if args.dry_run else ""))
        print(f"Violations: {len(violations)}/{processed + len(violations)}")
        for label, problems, drift in violations:
            print(f"  {label} {', '.join(problems)} (drift {drift * 100:.1f}%)")

    return 0


if __name__ == "__main__":
    exit(main())
