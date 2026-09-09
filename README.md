# dante-commentary

Generates a Japanese commentary article (Markdown) for a canto of Dante's
*Divina Commedia*, explaining its allegory and background with spot quotations
from the Italian source. The source text is fetched via
[dante_corpus](https://github.com/7shi/dante-corpus) and sent to an LLM
through [llm7shi](https://github.com/7shi/llm7shi).

## Dependency Projects

This project depends on the following companion repository:

- [dante-corpus](https://github.com/7shi/dante-corpus) - The shared corpus library and thin CLI. Serves the normalized Italian source text, tokens, and the quote-span tree as a queryable "DB" through its `dante_corpus` API. **Required** — this project reads canto text from it via an editable path dependency.

### Preparation

Because `dante-commentary` consumes `dante-corpus` via an editable path dependency (`../dante-corpus`), both repositories must share one parent directory. Ensure you have `uv` installed, then clone both into the same directory:

```bash
git clone https://github.com/7shi/dante-corpus.git
git clone https://github.com/7shi/dante-commentary.git
make -C dante-corpus
cd dante-commentary
uv sync
```

The resulting layout:

```
your-workspace/
├── dante-corpus/       # source text, tokens (read via the dante_corpus API)
└── dante-commentary/   # this repo
```

## Files

- `main.py` — generates the article
- `fable/` — sample output

## Usage

```bash
uv run python main.py [canticle] [-c CANTO] [-m MODEL] [--out-dir DIR]
```

| Argument | Description | Default |
|---|---|---|
| `canticle` | `inferno`, `purgatorio`, or `paradiso` | `inferno` |
| `-c`, `--canto` | Canto number | `1` |
| `-m`, `--model` | Model name with optional vendor prefix (e.g. `openai:gpt-4.1-mini`) | `ollama:gemma4:26b-a4b-it-qat` |
| `--out-dir` | Output directory | `test` |

The article is saved to `<out-dir>/<canticle>/<NN>.md` (e.g. `test/inferno/01.md`).

**Examples**

```bash
uv run python main.py inferno -c 1 -m openai:gpt-6-astra --out-dir astra
```
