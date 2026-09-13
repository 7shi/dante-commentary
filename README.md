# dante-commentary

ダンテ『神曲』の各カントについて、寓意や背景を解説し、イタリア語原文からの引用を交えた日本語の解説記事（Markdown）を生成します。さらに、そのカントの全行に対応する日本語の翻訳テキスト（行ごとに1行の訳文）も生成します。

原典テキストは [dante-corpus](https://github.com/7shi/dante-corpus) 経由で取得し、[llm7shi](https://github.com/7shi/llm7shi) を通じてLLMにリクエストを送信します。

## 依存プロジェクト

本プロジェクトは以下の姉妹リポジトリに関連しています。

- [dante-corpus](https://github.com/7shi/dante-corpus) — 共通のコーパスライブラリおよび軽量CLI。正規化されたイタリア語原文、形態素トークン、引用範囲ツリーを `dante_corpus` API を通じて問い合わせ可能なデータベースとして提供します。**【必須】** 本プロジェクトは editable path dependency として各カントのテキストをここから読み込みます。
- [dante-gemini-25](https://github.com/7shi/dante-gemini-25) — Gemini 2.5 Pro による『神曲』全篇の英訳・和訳プロジェクト。翻訳をセグメント単位で行うための場面境界データを持っています。本プロジェクトにはそのデータが `segments/` としてすでに取り込まれているため、**実行時には不要**です（詳細は[セグメント分割](#セグメント分割)を参照）。

### 準備

`dante-commentary` は `dante-corpus` を editable path dependency（`../dante-corpus`）として利用するため、両リポジトリを同一の親ディレクトリ直下に並べて配置する必要があります。`uv` がインストールされていることを確認した上で、次のようにセットアップしてください。

```bash
git clone https://github.com/7shi/dante-corpus.git
git clone https://github.com/7shi/dante-commentary.git
make -C dante-corpus
cd dante-commentary
uv sync
```

ディレクトリ構成は以下のようになります。

```
your-workspace/
├── dante-corpus/       # 原文テキスト、トークン（dante_corpus API経由で読み込み）
└── dante-commentary/   # 本リポジトリ
```

## ファイル構成

- `scripts/generate.py` — 解説記事および翻訳テキストの生成スクリプト（カント単位で処理し、セグメント分割は不使用）
- `scripts/fix_txt.py` — 翻訳テキストの鍵括弧を原文に合わせて補正するスクリプト（セグメント単位の後処理）
- `scripts/normalize_md.py` — 解説記事の引用ブロック記法を正規の形式に整形するスクリプト（後処理）
- `scripts/check_style.py` — 解説記事が「です・ます調」か「だ・である調」かを判定するスクリプト
- `scripts/check_quote_blocks.py` — 解説記事の各 `##` セクションに含まれる引用ブロック数を検査するスクリプト
- `segments/` — 各カントを場面の切れ目で分割した境界データ（`fix_txt.py` で使用。`inferno.jsonl`、`purgatorio.jsonl`、`paradiso.jsonl`）
- `fable/`、`astra/`、`gemma4-26b/` — モデル別のサンプル出力

各スクリプトのコマンドライン引数や処理内容の詳細は [scripts/README.md](scripts/README.md) を参照してください。
