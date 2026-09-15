# Site templates

Jinja2 templates and static assets used by [build.py](build.py) to generate
the static site published to GitHub Pages.

file|description
----|----
[canto.html](canto.html) | per-canto page: the canto's full Italian/Japanese text, side by side line by line, split into blocks by the commentary's sections — an annotated block shows that section's heading and commentary prose below its lines, an unannotated block (no commentary covers those lines) shows the lines alone, dimmed
[part_index.html](part_index.html) | per-canticle index page (`{canticle}/index.html`): links to every canto, with its commentary's title
[index.html](index.html) | landing page
[_sidebar.html](_sidebar.html) | shared sidebar/navigation include
[static/](static/) | CSS copied as-is into `dist/`

**`build.py` reads the Italian source from dante-corpus and, per canto, the
sibling `astra/{canticle}/NN.md` (commentary) and `astra/{canticle}/NN.txt`
(translation, one line per verse).** It never touches `astra/README.md` or
any other model's output directory (`fable/`, `gemma4-26b/`).

Each `## ` section in a commentary file (other than the closing `## 結び`
section) ends its heading with the line range it covers, e.g.
`## 1. 人生の半ばの「暗い森」……（1～3行）`. Across every `astra/*/*.md` file
these ranges tile the canto's lines with no gaps and no overlap, so
`build.py` uses them directly as the page's block boundaries — there is no
separate segmentation data to keep in sync. A canto whose headings don't
tile cleanly (a future model's output, say) falls back to one unannotated
block holding the whole text, with a warning at build time, rather than
mis-attributing commentary to the wrong lines.

Each block's commentary prose has its quote blocks (the `> N text` /
`> （trans）` pairs already shown in the bilingual table) stripped before
being rendered from Markdown, so nothing is duplicated on the page.

Line numbers (`#L12`) and section headings (`#s1`) are anchors, so other
cantos or off-site commentary can link straight to a specific line or
section.

## Build and Deploy

### Local build

```bash
# Build the HTML pages into dist/
make build

# Serve dist/ locally for a preview (localhost:8000)
make serve

# Remove build artifacts
make clean-dist
```

### Deploying to GitHub Pages

```bash
# Build, then push dist/ to the gh-pages branch
make deploy
```

`deploy.sh` checks out the `gh-pages` branch into `.gh-pages-worktree/` via
`git worktree`, replaces its contents with `dist/`, and commits and pushes.
It is a no-op when there is nothing to deploy.

### First-time setup

The `gh-pages` branch is created automatically on the first `make deploy`.

In the GitHub UI:

1. Open **Settings → Pages** on the repository
2. Set **Source** to `Deploy from a branch`
3. Set **Branch** to `gh-pages` / `/ (root)` and **Save**
