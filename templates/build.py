"""Static site builder for dante-commentary.

Reads the Italian source from dante-corpus and, for each canto, the sibling
astra/{canticle}/NN.md commentary and astra/{canticle}/NN.txt translation,
and generates:

- dist/{canticle}/NN.html    per-canto page: the full Italian/Japanese text,
                             set side by side line by line, with the
                             commentary's sections embedded next to the line
                             range each one covers
- dist/{canticle}/index.html per-canticle index page (links to every canto)
- dist/index.html            landing page
- dist/assets/                static assets (style.css)

Every "## " section in a commentary file (other than the closing "## 結び"
section) ends its heading with the line range it covers, e.g.
"## 1. 人生の半ばの「暗い森」……（1～3行）". In every astra/*/*.md file these
ranges tile the canto's lines with no gaps and no overlap (verified across
all 100 cantos), so that's used directly as the section boundaries -- no
separate segmentation data is needed. A canto whose headings don't tile
cleanly falls back to a single unannotated block covering the whole text,
with a warning, rather than mis-attributing commentary to the wrong lines.

Within a section, the commentary quotes the original in one or more
"> N text" / "> （trans）" runs, each immediately followed by the prose that
discusses it. build_section_pieces() turns each such run + its prose into
one merged bilingual+commentary piece (spanning from the run's first to
last quoted line, so a small internal gap between two quotes in the same
run stays inside that piece), and any lines within the section's range
that no run touches at all become their own commentary-less piece, placed
where they actually fall between pieces.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import markdown as md
from jinja2 import Environment, FileSystemLoader, select_autoescape

from dante_corpus.api import canticles as corpus_canticles
from dante_corpus.api import canto, cantos

ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = TEMPLATES_DIR / "static"
DIST_DIR = ROOT / "dist"
SOURCE_DIR = ROOT / "astra"
MODEL_NAME = "GPT-6 Astra"
REPO_URL = "https://github.com/7shi/dante-commentary"
CORPUS_URL = "https://github.com/7shi/dante-corpus"

CANTICLES = [
    {"key": "inferno", "label": "地獄篇"},
    {"key": "purgatorio", "label": "煉獄篇"},
    {"key": "paradiso", "label": "天国篇"},
]

HEAD_RE = re.compile(
    r"^(?:\d+\.\s*)?(?P<title>.*?)"
    r"(?:（(?P<start>\d+)(?:[～\-](?P<end>\d+))?行）)?\s*$"
)

TITLE_PREFIX_RE = re.compile(r"^ダンテ『神曲』.+?篇第\d+歌――")

QUOTE_LINE_RE = re.compile(r"^>\s*(\d+)\s")


@dataclass
class Section:
    heading: str
    start: int
    end: int
    raw_body: str  # unstripped text following the heading, quote blocks intact


@dataclass
class Piece:
    start: int
    end: int
    lines: list[tuple[int, str, str, bool]]  # (lineno, it, ja, quoted)
    annotated: bool = False
    body_html: str = ""


@dataclass
class SectionBlock:
    start: int
    end: int
    heading: str  # "" for the whole-canto fallback block
    pieces: list[Piece] = field(default_factory=list)


@dataclass
class CantoPage:
    canticle: str
    number: int
    title: str
    intro_html: str
    blocks: list[SectionBlock] = field(default_factory=list)
    conclusion_heading: str = ""
    conclusion_html: str = ""
    total_lines: int = 0
    is_last: bool = False


def strip_quote_blocks(text: str) -> str:
    """Drop maximal runs of '>' block-quote lines (already shown in the
    bilingual table above), keeping the surrounding prose intact."""
    out = [line for line in text.splitlines() if not line.lstrip().startswith(">")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def parse_commentary(text: str) -> tuple[str, str, list[Section], tuple[str, str] | None]:
    """Return (title, intro_md, sections, conclusion) for one commentary file.

    `sections` is every "## " heading in file order except "## 結び...",
    each carrying the (start, end) line range parsed from its own heading
    text. `conclusion` is the "## 結び..." section, if present, as
    (heading, body_md) -- it has no line range of its own.
    """
    parts = re.split(r"\n(?=## )", text.strip())
    preamble_lines = parts[0].splitlines()
    title = preamble_lines[0].lstrip("#").strip() if preamble_lines and preamble_lines[0].startswith("#") else ""
    title = TITLE_PREFIX_RE.sub("", title)
    intro_md = "\n".join(preamble_lines[1:]).strip()

    sections: list[Section] = []
    conclusion: tuple[str, str] | None = None
    for part in parts[1:]:
        head_line, _, body = part.partition("\n")
        heading_text = head_line[3:].strip()  # strip "## "
        if heading_text.startswith("結び"):
            conclusion = (heading_text, strip_quote_blocks(body))
            continue
        m = HEAD_RE.match(heading_text)
        if not m or not m.group("start"):
            sections.append(Section(heading_text, 0, 0, body))
            continue
        start = int(m.group("start"))
        end = int(m.group("end")) if m.group("end") else start
        sections.append(Section(m.group("title").strip(), start, end, body))
    return title, intro_md, sections, conclusion


def split_runs(body: str) -> list[tuple[str, list[str]]]:
    """Split a section's raw body into ('quote' | 'prose', lines) chunks,
    in order, by whether each line starts a '>' block-quote line."""
    chunks: list[tuple[str, list[str]]] = []
    for line in body.split("\n"):
        kind = "quote" if line.startswith(">") else "prose"
        if chunks and chunks[-1][0] == kind:
            chunks[-1][1].append(line)
        else:
            chunks.append((kind, [line]))
    return chunks


def build_section_pieces(
    start: int, end: int, raw_body: str,
    line_tuple,
) -> list[Piece]:
    """Turn one section's raw body into pieces covering start..end.

    Each '>' quote run pairs with the prose immediately following it into
    one annotated piece, spanning from the run's first to last quoted
    line (so a small gap between two quotes in the same run stays inside
    that piece). Prose before the first run is folded into the first
    piece's commentary. A run whose quoted lines fall entirely outside
    start..end (a rare authoring slip) is dropped, its prose folded into
    the neighboring piece, so lines aren't duplicated across sections.
    Any lines in start..end that no run touches become their own
    commentary-less piece, positioned where they actually fall.
    """
    chunks = split_runs(raw_body)

    leading_prose = ""
    i = 0
    if chunks and chunks[0][0] == "prose":
        leading_prose = "\n".join(chunks[0][1]).strip()
        i = 1

    raw_groups: list[tuple[list[int], str]] = []
    while i < len(chunks):
        run_lines = chunks[i][1]
        nums = [int(m.group(1)) for m in (QUOTE_LINE_RE.match(l) for l in run_lines) if m]
        prose = ""
        i += 1
        if i < len(chunks) and chunks[i][0] == "prose":
            prose = "\n".join(chunks[i][1]).strip()
            i += 1
        raw_groups.append((nums, prose))

    if leading_prose and raw_groups:
        nums0, prose0 = raw_groups[0]
        raw_groups[0] = (nums0, f"{leading_prose}\n\n{prose0}".strip())

    def fold_into_previous(groups: list[tuple[int, int, set[int], str]], prose: str) -> None:
        if not prose:
            return
        if groups:
            gs, ge, gq, gb = groups[-1]
            groups[-1] = (gs, ge, gq, f"{gb}\n\n{prose}".strip() if gb else prose)

    groups: list[tuple[int, int, set[int], str]] = []
    for nums, prose in raw_groups:
        if not nums:
            fold_into_previous(groups, prose)
            continue
        cmin, cmax = max(min(nums), start), min(max(nums), end)
        if cmin > cmax:
            fold_into_previous(groups, prose)
            continue
        groups.append((cmin, cmax, {n for n in nums if cmin <= n <= cmax}, prose))

    # A section's commentary sometimes quotes out of order (e.g. the
    # conclusion first, then the earlier line it draws on as an example),
    # so place groups by where their lines actually fall, not file order.
    # Overlapping ranges (not seen in practice, but possible) are merged
    # rather than rendering the same line twice.
    groups.sort(key=lambda g: g[0])
    merged: list[tuple[int, int, set[int], str]] = []
    for gmin, gmax, quoted, prose in groups:
        if merged and gmin <= merged[-1][1]:
            pmin, pmax, pquoted, pprose = merged[-1]
            merged[-1] = (pmin, max(pmax, gmax), pquoted | quoted,
                          f"{pprose}\n\n{prose}".strip() if pprose else prose)
        else:
            merged.append((gmin, gmax, quoted, prose))
    groups = merged

    pieces: list[Piece] = []
    cursor = start
    for gmin, gmax, quoted, prose in groups:
        if cursor < gmin:
            pieces.append(Piece(
                start=cursor, end=gmin - 1,
                lines=[line_tuple(i) + (False,) for i in range(cursor, gmin)],
            ))
        pieces.append(Piece(
            start=gmin, end=gmax,
            lines=[line_tuple(i) + (i in quoted,) for i in range(gmin, gmax + 1)],
            annotated=True,
            body_html=md.markdown(prose) if prose else "",
        ))
        cursor = gmax + 1
    if cursor <= end:
        pieces.append(Piece(
            start=cursor, end=end,
            lines=[line_tuple(i) + (False,) for i in range(cursor, end + 1)],
        ))
    return pieces


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").rstrip("\n").split("\n")


def build_canto(canticle: str, number: int) -> CantoPage:
    md_path = SOURCE_DIR / canticle / f"{number:02d}.md"
    txt_path = SOURCE_DIR / canticle / f"{number:02d}.txt"

    it_lines = [line.text for line in canto(canticle, number).lines()]
    n = len(it_lines)
    ja_lines = read_lines(txt_path)
    if len(ja_lines) != n:
        print(f"Warning: {canticle} {number:02d} line count mismatch "
              f"(it={n}, ja={len(ja_lines)})")
        ja_lines = (ja_lines + [""] * n)[:n]

    title, intro_md, sections, conclusion = parse_commentary(md_path.read_text(encoding="utf-8"))

    def line_tuple(i: int) -> tuple[int, str, str]:
        return (i, it_lines[i - 1], ja_lines[i - 1])

    tiles = bool(sections)
    expected = 1
    for s in sections:
        if s.start == 0 or s.start != expected:
            tiles = False
            break
        expected = s.end + 1
    if tiles and expected - 1 != n:
        tiles = False

    blocks: list[SectionBlock] = []
    if tiles:
        for s in sections:
            blocks.append(SectionBlock(
                start=s.start,
                end=s.end,
                heading=s.heading,
                pieces=build_section_pieces(s.start, s.end, s.raw_body, line_tuple),
            ))
    else:
        print(f"Warning: {canticle} {number:02d} commentary headings don't tile "
              f"1..{n} without gaps; showing the canto unannotated")
        blocks.append(SectionBlock(start=1, end=n, heading="", pieces=[
            Piece(start=1, end=n, lines=[line_tuple(i) + (False,) for i in range(1, n + 1)]),
        ]))

    conclusion_heading, conclusion_html = "", ""
    if conclusion:
        conclusion_heading, body_md = conclusion
        conclusion_html = md.markdown(body_md) if body_md else ""

    return CantoPage(
        canticle=canticle,
        number=number,
        title=title,
        intro_html=md.markdown(intro_md) if intro_md else "",
        blocks=blocks,
        conclusion_heading=conclusion_heading,
        conclusion_html=conclusion_html,
        total_lines=n,
    )


def canto_href(canticle: str, number: int) -> str:
    return f"{canticle}/{number:02d}.html"


def part_href(canticle: str) -> str:
    return f"{canticle}/index.html"


def load_part_cantos(canticle: str) -> list[CantoPage]:
    numbers = sorted(cantos(canticle))
    total = len(numbers)
    pages = []
    for i, number in enumerate(numbers):
        page = build_canto(canticle, number)
        page.is_last = (i == total - 1)
        pages.append(page)
    return pages


def build_sidebar_parts(all_cantos: dict[str, list[CantoPage]]) -> list[dict]:
    sidebar_parts = []
    for part_cfg in CANTICLES:
        key = part_cfg["key"]
        sidebar_parts.append({
            "key": key,
            "label": part_cfg["label"],
            "href": part_href(key),
            "cantos": [
                {"number": c.number, "href": canto_href(key, c.number)}
                for c in all_cantos[key]
            ],
        })
    return sidebar_parts


def build_canto_pages(env: Environment, all_cantos: dict[str, list[CantoPage]], sidebar_parts: list[dict]) -> None:
    template = env.get_template("canto.html")
    count = 0
    for part_index, part_cfg in enumerate(CANTICLES):
        key = part_cfg["key"]
        cantos_list = all_cantos[key]
        for i, canto_page in enumerate(cantos_list):
            if i > 0:
                prev_href = canto_href(key, cantos_list[i - 1].number)
                prev_label = f"第{cantos_list[i - 1].number}歌"
            elif part_index > 0:
                prev_part = CANTICLES[part_index - 1]
                prev_cantos = all_cantos[prev_part["key"]]
                prev_href = canto_href(prev_part["key"], prev_cantos[-1].number)
                prev_label = f"{prev_part['label']} 第{prev_cantos[-1].number}歌"
            else:
                prev_href = None
                prev_label = None

            if i < len(cantos_list) - 1:
                next_href = canto_href(key, cantos_list[i + 1].number)
                next_label = f"第{cantos_list[i + 1].number}歌"
            elif part_index < len(CANTICLES) - 1:
                next_part = CANTICLES[part_index + 1]
                next_href = canto_href(next_part["key"], all_cantos[next_part["key"]][0].number)
                next_label = f"{next_part['label']} 第{all_cantos[next_part['key']][0].number}歌"
            else:
                next_href = None
                next_label = None

            html_out = template.render(
                canticle_key=key,
                canticle_label=part_cfg["label"],
                canto=canto_page,
                prev_href=prev_href,
                prev_label=prev_label,
                next_href=next_href,
                next_label=next_label,
                part_href=part_href(key),
                base="../",
                sidebar_parts=sidebar_parts,
                current_part=key,
                current_canto=canto_page.number,
                model_name=MODEL_NAME,
                repo_url=REPO_URL,
                corpus_url=CORPUS_URL,
            )
            out = DIST_DIR / canto_href(key, canto_page.number)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html_out, encoding="utf-8")
            count += 1
    print(f"  wrote {count} canto pages")


def build_part_index_pages(env: Environment, all_cantos: dict[str, list[CantoPage]], sidebar_parts: list[dict]) -> None:
    template = env.get_template("part_index.html")
    for part_cfg in CANTICLES:
        key = part_cfg["key"]
        cantos_summary = [
            {"number": c.number, "href": canto_href(key, c.number), "title": c.title}
            for c in all_cantos[key]
        ]
        html_out = template.render(
            canticle_key=key,
            canticle_label=part_cfg["label"],
            cantos=cantos_summary,
            base="../",
            sidebar_parts=sidebar_parts,
            current_part=key,
        )
        out = DIST_DIR / part_href(key)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_out, encoding="utf-8")
    print(f"  wrote {len(CANTICLES)} canticle index pages")


def build_index(env: Environment, sidebar_parts: list[dict]) -> None:
    template = env.get_template("index.html")
    html_out = template.render(
        base="",
        sidebar_parts=sidebar_parts,
        parts=CANTICLES,
        model_name=MODEL_NAME,
        repo_url=REPO_URL,
        corpus_url=CORPUS_URL,
    )
    out = DIST_DIR / "index.html"
    out.write_text(html_out, encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}")


def copy_static() -> None:
    assets = DIST_DIR / "assets"
    if assets.exists():
        shutil.rmtree(assets)
    shutil.copytree(STATIC_DIR, assets)
    print(f"  copied static -> {assets.relative_to(ROOT)}")


def main() -> None:
    missing = [c for c in ("inferno", "purgatorio", "paradiso") if c not in corpus_canticles()]
    if missing:
        raise SystemExit(f"dante-corpus has no source for: {', '.join(missing)}. "
                          f"Run 'make' in ../dante-corpus first.")

    DIST_DIR.mkdir(exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )

    print("Loading cantos...")
    all_cantos = {part_cfg["key"]: load_part_cantos(part_cfg["key"]) for part_cfg in CANTICLES}
    sidebar_parts = build_sidebar_parts(all_cantos)

    print("Building canto pages...")
    build_canto_pages(env, all_cantos, sidebar_parts)

    print("Building canticle index pages...")
    build_part_index_pages(env, all_cantos, sidebar_parts)

    print("Building index...")
    build_index(env, sidebar_parts)

    print("Copying static assets...")
    copy_static()

    print("Done.")


if __name__ == "__main__":
    main()
