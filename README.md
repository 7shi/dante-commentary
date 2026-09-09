# dante-commentary

ダンテ『神曲』の各歌について、寓意や背景を解説し、イタリア語原文からの引用を交えた日本語の解説記事（Markdown）を生成します。続けて、その歌の全行の対訳（原文と日本語訳を1行ずつ交互に並べたテキスト）も生成します。原典テキストは
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

- `scripts/generate.py` — 記事と対訳を生成する
- `fable/`、`astra/`、`gemma4-26b/` — モデルごとのサンプル出力

## 使い方

```bash
uv run scripts/generate.py [canticle] [-c CANTO] [-m MODEL] [-r ROUNDS] [--no-think] [--out-dir DIR]
```

| 引数 | 説明 | デフォルト |
|---|---|---|
| `canticle` | `inferno`、`purgatorio`、`paradiso` のいずれか | `inferno` |
| `-c`, `--canto` | 歌の番号 | `1` |
| `-m`, `--model` | ベンダープレフィックス付きのモデル名（例: `openai:gpt-4.1-mini`） | `ollama:gemma4:26b-a4b-it-qat` |
| `-r`, `--rounds` | 対訳を補完する最大ラウンド数 | `5` |
| `--no-think` | thinkingを無効にする（`include_thoughts=False`） | 有効 |
| `--out-dir` | 出力ディレクトリ | `test` |

出力は以下の2つです（例: `test/inferno/01.md`、`test/inferno/01.txt`）。

- `<out-dir>/<canticle>/<NN>.md` — 解説記事
- `<out-dir>/<canticle>/<NN>.txt` — 対訳。原文と日本語訳を1行ずつ交互に並べたもの

**実行例**

```bash
uv run scripts/generate.py inferno -c 1 -m openai:gpt-6-astra --out-dir astra
```

## 対訳の生成

対訳は次の手順で作られます。

1. 解説記事の引用ブロックから `> 行番号 原文` / `> （日本語訳）` の対を抽出する。引用された原文がコーパスの当該行と完全に一致しない場合（部分引用や誤記）は、誤った訳が付かないよう破棄する
2. 全行を交互形式に並べ、まだ訳のない行にプレースホルダーを置いたテキストをモデルへ渡し、その行だけを訳させる
3. 返ってきた訳を検査し、通ったものを反映する。埋まらなかった行が残っていれば、2へ戻って繰り返す（最大 `--rounds` 回）

補完された訳は、次のいずれかに該当する場合に採用せず、未訳のまま次のラウンドへ回します。

- プレースホルダーがそのまま残っている
- 原文と一致している（訳さずに複写している）
- 日本語文字を含まない

ファイルは各ラウンドの終了時に保存されます。既に `<NN>.txt` があればそこから読み込んで、未訳の行だけを補完するので、中断しても再実行すれば続きから進みます。`<NN>.md` があれば解説記事の生成は行いません。

小さめのローカルモデルでは、thinkingが終わらない、プレースホルダーをそのまま出力する、原文を複写するといった失敗が起こります。実例と対処は [gemma4-26b/README.md](gemma4-26b/README.md) を参照してください。
