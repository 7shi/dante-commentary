# dante-commentary

ダンテ『神曲』の各歌について、寓意や背景を解説し、イタリア語原文からの引用を交えた日本語の解説記事（Markdown）を生成します。原典テキストは
[dante_corpus](https://github.com/7shi/dante-corpus) 経由で取得し、
[llm7shi](https://github.com/7shi/llm7shi) を通じてLLMに送信します。

## 依存プロジェクト

このプロジェクトは以下の姉妹リポジトリに依存しています：

- [dante-corpus](https://github.com/7shi/dante-corpus) - 共通のコーパスライブラリと薄いCLI。正規化されたイタリア語原文、トークン、引用範囲ツリーを `dante_corpus` API を通じて問い合わせ可能な「DB」として提供します。**必須** — 本プロジェクトはeditable path dependencyとして各歌のテキストをここから読み込みます。

### 準備

`dante-commentary` は `dante-corpus` をeditable path dependency（`../dante-corpus`）として利用するため、両方のリポジトリを同じ親ディレクトリに置く必要があります。`uv` がインストールされていることを確認した上で、両方を同じディレクトリにクローンしてください：

```bash
git clone https://github.com/7shi/dante-corpus.git
git clone https://github.com/7shi/dante-commentary.git
make -C dante-corpus
cd dante-commentary
uv sync
```

結果として以下のような構成になります：

```
your-workspace/
├── dante-corpus/       # 原文テキスト、トークン（dante_corpus API経由で読み込み）
└── dante-commentary/   # このリポジトリ
```

## ファイル構成

- `main.py` — 記事を生成する
- `fable/` — サンプル出力

## 使い方

```bash
uv run main.py [canticle] [-c CANTO] [-m MODEL] [--out-dir DIR]
```

| 引数 | 説明 | デフォルト |
|---|---|---|
| `canticle` | `inferno`、`purgatorio`、`paradiso` のいずれか | `inferno` |
| `-c`, `--canto` | 歌の番号 | `1` |
| `-m`, `--model` | ベンダープレフィックス付きのモデル名（例: `openai:gpt-4.1-mini`） | `ollama:gemma4:26b-a4b-it-qat` |
| `--out-dir` | 出力ディレクトリ | `test` |

記事は `<out-dir>/<canticle>/<NN>.md`（例: `test/inferno/01.md`）に保存されます。

**実行例**

```bash
uv run main.py inferno -c 1 -m openai:gpt-6-astra --out-dir astra
```
